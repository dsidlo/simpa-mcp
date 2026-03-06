import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { spawn, ChildProcess } from "child_process";
import * as readline from "readline";
import * as path from "path";
import * as os from "os";

interface PendingRequest {
  resolve: (value: any) => void;
  reject: (reason: any) => void;
  method: string;
}

export default function (pi: ExtensionAPI) {
  let simpaProcess: ChildProcess | null = null;
  let pendingRequests = new Map<string, PendingRequest>();
  let requestId = 0;
  let ready = false;
  let readyPromise: Promise<void> | null = null;

  // Configuration
  const SIMPA_ROOT = process.env.SIMPA_ROOT || path.join(os.homedir(), ".pi");
  const MODULE = "simpa.jsonrpc_server";

  // Verify simpa is installed
  function verifySimpaInstallation(): boolean {
    try {
      const jsonrpcPath = path.join(SIMPA_ROOT, "simpa", "jsonrpc_server.py");
      require("fs").accessSync(jsonrpcPath);
      return true;
    } catch {
      return false;
    }
  }

  function getRequestId(): string {
    return `${++requestId}-${Date.now()}`;
  }

  function ensureProcess(): Promise<void> {
    if (simpaProcess && !simpaProcess.killed && ready) {
      return Promise.resolve();
    }

    if (readyPromise) {
      return readyPromise;
    }

    readyPromise = new Promise((resolve, reject) => {
      if (!verifySimpaInstallation()) {
        reject(new Error(
          `SIMPA not found at ${SIMPA_ROOT}/simpa. ` +
          `Please ensure simpa is installed in ~/.pi/simpa`
        ));
        return;
      }

      // Use uv run from the ~/.pi directory
      const env = { 
        ...process.env, 
        PYTHONPATH: SIMPA_ROOT,
        UV_PYTHON: path.join(SIMPA_ROOT, ".venv", "bin", "python")
      };

      simpaProcess = spawn("uv", ["run", "-m", MODULE], {
        stdio: ["pipe", "pipe", "pipe"],
        cwd: SIMPA_ROOT,
        env,
      });

      // Handle stderr (logging and ready signal)
      const stderrReader = readline.createInterface({ input: simpaProcess.stderr! });
      stderrReader.on("line", (line: string) => {
        if (line.includes("ready")) {
          ready = true;
          resolve();
        }
      });

      // Handle stdout (JSON-RPC responses)
      const stdoutReader = readline.createInterface({ input: simpaProcess.stdout! });
      stdoutReader.on("line", (line: string) => {
        try {
          const response = JSON.parse(line);
          handleResponse(response);
        } catch {
          // Ignore non-JSON lines
        }
      });

      simpaProcess.on("error", (err) => {
        ready = false;
        readyPromise = null;
        reject(new Error(`Failed to start SIMPA: ${err.message}. Ensure 'uv' is installed.`));
      });

      simpaProcess.on("exit", (code) => {
        ready = false;
        simpaProcess = null;
        readyPromise = null;
      });

      // Timeout after 30 seconds
      setTimeout(() => {
        if (!ready) {
          reject(new Error("Timeout waiting for SIMPA server to start (30s). Check logs."));
        }
      }, 30000);
    });

    return readyPromise;
  }

  function handleResponse(response: any) {
    const id = response.id;
    const pending = pendingRequests.get(id);

    if (!pending) return;

    pendingRequests.delete(id);

    if (response.error) {
      pending.reject(new Error(`${response.error.message} (code: ${response.error.code})`));
    } else {
      pending.resolve(response.result);
    }
  }

  async function callMethod(method: string, params: any): Promise<any> {
    await ensureProcess();

    const id = getRequestId();
    const request = { jsonrpc: "2.0", id, method, params };
    const requestJson = JSON.stringify(request);

    return new Promise((resolve, reject) => {
      pendingRequests.set(id, { resolve, reject, method });

      // Send to stdin with explicit newline
      const requestLine = requestJson + "\n";
      simpaProcess!.stdin!.write(requestLine);

      // Timeout after 30 seconds
      setTimeout(() => {
        if (pendingRequests.has(id)) {
          pendingRequests.delete(id);
          reject(new Error(`Request timeout: ${method}`));
        }
      }, 30000);
    });
  }

  // Register tools

  pi.registerTool({
    name: "simpa_refine_prompt",
    label: "Refine Prompt (SIMPA)",
    description: "Refine prompts using SIMPA's intelligent prompt refinement",
    parameters: Type.Object({
      agent_type: Type.String({ description: "Type of agent (e.g., developer, architect)" }),
      original_prompt: Type.String({ description: "The original prompt to refine" }),
      project_id: Type.Optional(Type.String({ description: "Project ID to associate with this prompt" })),
      context: Type.Optional(Type.Object({}, { description: "Additional context for refinement" })),
      main_language: Type.Optional(Type.String({ description: "Primary programming language" })),
      other_languages: Type.Optional(Type.Array(Type.String(), { description: "Additional programming languages" })),
      domain: Type.Optional(Type.String({ description: "Domain category (e.g., backend, frontend)" })),
      tags: Type.Optional(Type.Array(Type.String(), { description: "Tags for categorization" })),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("refine_prompt", params);

      let text: string;
      if (result.refined_prompt?.startsWith("ERROR:")) {
        text = result.refined_prompt;
      } else {
        text = "**Refined Prompt**\n\n" +
          result.refined_prompt + "\n\n---\n" +
          "**Source:** " + result.source + " | **Action:** " + result.action + "\n" +
          "**Prompt Key:** " + result.prompt_key;
        if (result.usage_count !== undefined) {
          text += " | **Usage:** " + result.usage_count;
        }
        if (result.average_score !== undefined && result.average_score !== null) {
          text += " | **Avg Score:** " + result.average_score.toFixed(2);
        }
      }

      return {
        content: [{ type: "text", text }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_update_results",
    label: "Update Prompt Results (SIMPA)",
    description: "Update prompt performance metrics after agent execution",
    parameters: Type.Object({
      prompt_key: Type.String({ description: "UUID of the prompt to update" }),
      action_score: Type.Number({ minimum: 1, maximum: 5, description: "Performance score" }),
      files_modified: Type.Optional(Type.Array(Type.String(), { description: "Modified files" })),
      files_added: Type.Optional(Type.Array(Type.String(), { description: "Added files" })),
      files_deleted: Type.Optional(Type.Array(Type.String(), { description: "Deleted files" })),
      diffs: Type.Optional(Type.Object({}, { description: "Diff content per file" })),
      validation_results: Type.Optional(Type.Object({}, { description: "Validation results" })),
      executed_by_agent: Type.Optional(Type.String({ description: "Agent that executed the prompt" })),
      execution_duration_ms: Type.Optional(Type.Integer({ description: "Execution duration in ms" })),
      test_passed: Type.Optional(Type.Boolean({ description: "Whether tests passed" })),
      lint_score: Type.Optional(Type.Number({ minimum: 0, maximum: 1, description: "Lint score" })),
      security_scan_passed: Type.Optional(Type.Boolean({ description: "Whether security scan passed" })),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("update_prompt_results", params);
      return {
        content: [{
          type: "text",
          text: "Updated prompt results. Usage count: " + result.usage_count + ", Average score: " + result.average_score.toFixed(2)
        }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_create_project",
    label: "Create Project (SIMPA)",
    description: "Create a new project in SIMPA for organizing prompts",
    parameters: Type.Object({
      project_name: Type.String({ description: "Name of the project" }),
      description: Type.Optional(Type.String({ description: "Project description" })),
      main_language: Type.Optional(Type.String({ description: "Primary programming language" })),
      other_languages: Type.Optional(Type.Array(Type.String(), { description: "Additional programming languages" })),
      library_dependencies: Type.Optional(Type.Array(Type.String(), { description: "Library dependencies" })),
      project_structure: Type.Optional(Type.Object({}, { description: "Project structure hints" })),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("create_project", params);
      return {
        content: [{
          type: "text",
          text: "Created project \"" + result.project_name + "\" with ID: " + result.project_id
        }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_get_project",
    label: "Get Project (SIMPA)",
    description: "Get project details by ID or name",
    parameters: Type.Object({
      project_id: Type.Optional(Type.String({ description: "Project UUID" })),
      project_name: Type.Optional(Type.String({ description: "Project name" })),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("get_project", params);
      return {
        content: [{
          type: "text",
          text: "Project: " + result.project_name + "\nLanguage: " + (result.main_language || 'N/A') + "\nPrompts: " + result.prompt_count
        }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_list_projects",
    label: "List Projects (SIMPA)",
    description: "List all projects in SIMPA",
    parameters: Type.Object({
      main_language: Type.Optional(Type.String({ description: "Filter by programming language" })),
      limit: Type.Optional(Type.Number({ default: 50, description: "Maximum results" })),
      offset: Type.Optional(Type.Number({ default: 0, description: "Pagination offset" })),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("list_projects", params);
      const projects = result.projects.map((p: any) => {
        let line = "- " + p.project_name + " (" + (p.main_language || 'N/A') + ") - " + p.prompt_count + " prompts";
        if (p.description) {
          line += "\n  " + p.description;
        }
        return line;
      }).join('\n');

      return {
        content: [{
          type: "text",
          text: "Found " + result.total_count + " projects:\n" + (projects || 'No projects found')
        }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_activate_prompt",
    label: "Activate Prompt (SIMPA)",
    description: "Activate a previously deactivated prompt",
    parameters: Type.Object({
      prompt_key: Type.String({ description: "UUID of the prompt to activate" }),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("activate_prompt", params);
      return {
        content: [{ type: "text", text: result.message }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_deactivate_prompt",
    label: "Deactivate Prompt (SIMPA)",
    description: "Deactivate a prompt so it won't be used in searches",
    parameters: Type.Object({
      prompt_key: Type.String({ description: "UUID of the prompt to deactivate" }),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("deactivate_prompt", params);
      return {
        content: [{ type: "text", text: result.message }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "simpa_health",
    label: "SIMPA Health Check",
    description: "Check SIMPA service health",
    parameters: Type.Object({}),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const result = await callMethod("health_check", {});
      return {
        content: [{
          type: "text",
          text: "SIMPA status: " + result.status + " (" + result.version + ")\nTimestamp: " + result.timestamp
        }],
        details: result,
      };
    },
  });

  // Register slash commands
  pi.registerCommand("simpa_health", {
    description: "Check SIMPA service health",
    handler: async (_args, ctx) => {
      try {
        const result = await callMethod("health_check", {});
        ctx.ui.notify("SIMPA: " + result.status + " v" + result.version, "success");
      } catch (err: any) {
        ctx.ui.notify("SIMPA error: " + err.message, "error");
      }
    },
  });

  pi.registerCommand("simpa_list_projects", {
    description: "List all projects in SIMPA",
    handler: async (_args, ctx) => {
      try {
        const result = await callMethod("list_projects", {});
        const projects = result.projects.map((p: any) =>
          p.project_name + " (" + (p.main_language || 'N/A') + ")"
        ).join(', ');
        ctx.ui.notify("Projects: " + (projects || 'None'), "info");
      } catch (err: any) {
        ctx.ui.notify("SIMPA error: " + err.message, "error");
      }
    },
  });

  // Cleanup on shutdown
  pi.on("session_shutdown", async () => {
    if (simpaProcess) {
      simpaProcess.stdin?.end();
      simpaProcess.kill();
      simpaProcess = null;
    }
    pendingRequests.clear();
    ready = false;
    readyPromise = null;
  });
}
