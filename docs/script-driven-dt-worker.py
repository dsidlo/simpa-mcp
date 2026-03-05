#!/usr/bin/env python3
"""
Script-Driven DT-Worker Agent Driver

A deterministic script to drive the DT-Worker (DyTopo Worker) agent through
the SIMPA-MCP service. This script reads task specifications and coordinates
with the MCP server to execute DT-Worker tasks.

Usage:
    python script-driven-dt-worker.py --task "Implement feature X" --agent-type developer
    python script-driven-dt-worker.py --file task_spec.json
    python script-driven-dt-worker.py --interactive

Environment:
    MCP_CONFIG_FILE: Path to mcp.json (default: ~/.pi/agent/mcp.json)
    SIMPA_LOG_LEVEL: Logging level (trace, debug, info, warn, error)
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Add src to path for direct imports
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR / "src"))

# Set environment before any imports
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["FASTMCP_SHOW_SERVER_BANNER"] = "false"

from pydantic import BaseModel, Field


class DTWorkerTask(BaseModel):
    """DT-Worker task specification."""
    task: str = Field(..., description="The task to perform")
    agent_type: str = Field(default="developer", description="DT agent type")
    main_language: str = Field(default="python", description="Primary programming language")
    project_id: str | None = Field(default=None, description="Project ID for context")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    tags: list[str] = Field(default_factory=list, description="Task tags")


class DTWorkerDriver:
    """Deterministic driver for DT-Worker agents via SIMPA-MCP."""
    
    def __init__(self, config_file: str | None = None):
        """Initialize the driver with MCP configuration."""
        self.config_file = config_file or self._find_mcp_json()
        self.config = self._load_mcp_config()
        self.server_env = self._extract_server_env()
        self._apply_environment()
    
    def _find_mcp_json(self) -> str:
        """Find the mcp.json configuration file."""
        paths = [
            os.getenv("MCP_CONFIG_FILE", ""),
            str(Path.home() / ".pi" / "agent" / "mcp.json"),
            str(Path.cwd() / ".pi" / "agent" / "mcp.json"),
            str(Path.cwd() / "mcp.json"),
        ]
        for path in paths:
            if path and Path(path).exists():
                return path
        raise FileNotFoundError(f"mcp.json not found. Searched: {paths}")
    
    def _load_mcp_config(self) -> dict:
        """Load mcp.json configuration."""
        with open(self.config_file) as f:
            return json.load(f)
    
    def _extract_server_env(self) -> dict[str, str]:
        """Extract environment variables for simpa-mcp from config."""
        servers = self.config.get("mcpServers", {})
        simpa = servers.get("simpa-mcp", {})
        return simpa.get("env", {})
    
    def _apply_environment(self) -> None:
        """Apply environment variables from config."""
        for key, value in self.server_env.items():
            if key not in os.environ:
                os.environ[key] = value
    
    async def refine_prompt(self, task: DTWorkerTask) -> dict[str, Any]:
        """Send refine_prompt request to SIMPA-MCP and return response."""
        # Import here after environment is set
        from simpa.mcp_server import RefinePromptRequest, refine_prompt
        from simpa.db.engine import AsyncSessionLocal, init_db
        from unittest.mock import AsyncMock, MagicMock
        
        # Initialize database if needed
        await init_db()
        
        # Create mock context
        ctx = self._create_mock_context()
        
        # Build request (project_id must be string, not UUID)
        request = RefinePromptRequest(
            original_prompt=task.task,
            agent_type=task.agent_type,
            main_language=task.main_language,
            project_id=task.project_id,
            context=task.context,
            tags=task.tags,
        )
        
        # Execute refinement
        response = await refine_prompt(request, ctx)
        
        return {
            "action": response.action,
            "prompt_key": response.prompt_key,
            "refined_prompt": response.refined_prompt,
            "confidence_score": response.confidence_score,
            "similar_prompts_found": response.similar_prompts_found,
        }
    
    def _create_mock_context(self) -> Any:
        """Create a mock MCP context for testing."""
        from unittest.mock import AsyncMock, MagicMock
        
        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768
        
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = """Refined prompt with clear requirements:

1. Analyze the task requirements thoroughly
2. Identify dependencies and prerequisites
3. Create implementation plan with steps
4. Execute implementation with TRACE logging
5. Verify against acceptance criteria
6. Report completion with evidence"""
        
        class LifespanContext:
            def __getitem__(self, key):
                if key == "embedding_service":
                    return mock_embedding
                elif key == "llm_service":
                    return mock_llm
                raise KeyError(key)
        
        class RequestContext:
            lifespan_context = LifespanContext()
        
        class Context:
            request_context = RequestContext()
        
        return Context()
    
    async def run_task(self, task_spec: DTWorkerTask) -> dict[str, Any]:
        """Execute a complete DT-Worker task."""
        print(f"=" * 70)
        print(f"DT-Worker Task: {task_spec.task[:50]}...")
        print(f"Agent Type: {task_spec.agent_type}")
        print(f"Language: {task_spec.main_language}")
        print(f"=" * 70)
        print()
        
        # Step 1: Refine the prompt
        print("[1/3] Refining prompt via SIMPA-MCP...")
        result = await self.refine_prompt(task_spec)
        
        print(f"Action: {result['action']}")
        print(f"Confidence: {result['confidence_score']:.2f}")
        print(f"Similar Prompts: {result['similar_prompts_found']}")
        print()
        
        print("[2/3] Refined Prompt:")
        print("-" * 70)
        print(result['refined_prompt'])
        print("-" * 70)
        print()
        
        # Step 2: Execute with DT-Worker logic (placeholder)
        print("[3/3] Executing with DT-Worker agent...")
        execution_result = await self._execute_with_worker(result['refined_prompt'], task_spec)
        
        return {
            "refinement": result,
            "execution": execution_result,
        }
    
    async def _execute_with_worker(
        self, refined_prompt: str, task: DTWorkerTask
    ) -> dict[str, Any]:
        """Execute the refined prompt with DT-Worker agent."""
        # This would integrate with actual DT-Worker execution
        # For now, return a placeholder result
        return {
            "status": "completed",
            "prompt_used": refined_prompt[:100] + "...",
            "worker_type": task.agent_type,
            "artifacts_generated": [],
        }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deterministic DT-Worker Agent Driver via SIMPA-MCP"
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        help="Task description to execute"
    )
    parser.add_argument(
        "--agent-type", "-a",
        type=str,
        default="developer",
        choices=["developer", "architect", "tester", "reviewer", "manager"],
        help="DT agent type"
    )
    parser.add_argument(
        "--language", "-l",
        type=str,
        default="python",
        help="Primary programming language"
    )
    parser.add_argument(
        "--project-id", "-p",
        type=str,
        default="334f7ad0-bea4-4a6d-a812-b9fd8db75aae",
        help="Project ID for context"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="JSON file containing task specification"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to mcp.json config file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for results (JSON)"
    )
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Initialize driver
    driver = DTWorkerDriver(config_file=args.config)
    
    # Load task from various sources
    if args.file:
        with open(args.file) as f:
            task_data = json.load(f)
        task = DTWorkerTask(**task_data)
    elif args.task:
        task = DTWorkerTask(
            task=args.task,
            agent_type=args.agent_type,
            main_language=args.language,
            project_id=args.project_id,
        )
    elif args.interactive:
        print("DT-Worker Interactive Mode")
        print("=" * 70)
        task_input = input("Enter task: ")
        agent_type = input(f"Agent type (default: developer): ") or "developer"
        language = input(f"Language (default: python): ") or "python"
        task = DTWorkerTask(
            task=task_input,
            agent_type=agent_type,
            main_language=language,
            project_id=args.project_id,
        )
    else:
        print("Error: No task provided. Use --task, --file, or --interactive")
        sys.exit(1)
    
    # Execute task
    try:
        result = await driver.run_task(task)
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\nResults saved to: {args.output}")
        else:
            print("\nFinal Result:")
            print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
