#!/usr/bin/env python3
"""SIMPA MCP Server startup script that reads configuration from mcp.json.

This script reads the mcp.json configuration and starts the SIMPA MCP server
with the appropriate environment variables and command-line arguments.

Environment Variable Overrides:
    MCP_CONFIG_FILE: Path to mcp.json (default: ~/.pi/agent/mcp.json)
    SIMPA_LOG_LEVEL: Override log level (trace, debug, info, warn, error)
    SIMPA_LOG_FILE: Override log file path
    SIMPA_TRANSPORT: Override transport (stdio, sse)
    SIMPA_PROJECT_REQUIRED: Set to "true" to require project_id
    Any config setting from Settings class can be overridden via env var
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def find_mcp_json() -> Path:
    """Find the mcp.json configuration file.
    
    Searches in order:
    1. MCP_CONFIG_FILE environment variable
    2. ~/.pi/agent/mcp.json
    3. ./.pi/agent/mcp.json
    4. ./mcp.json
    """
    # Check environment variable first
    if env_path := os.getenv("MCP_CONFIG_FILE"):
        path = Path(env_path)
        if path.exists():
            return path.resolve()
        raise FileNotFoundError(f"MCP_CONFIG_FILE not found: {env_path}")
    
    # Search standard locations
    search_paths = [
        Path.home() / ".pi" / "agent" / "mcp.json",
        Path.cwd() / ".pi" / "agent" / "mcp.json",
        Path.cwd() / "mcp.json",
    ]
    
    for path in search_paths:
        if path.exists():
            return path.resolve()
    
    raise FileNotFoundError(
        "mcp.json not found. Searched:\n" + 
        "\n".join(f"  - {p}" for p in search_paths)
    )


def load_mcp_config(config_path: Path) -> dict[str, Any]:
    """Load and parse mcp.json file."""
    with open(config_path) as f:
        return json.load(f)


def extract_simpa_config(config: dict) -> dict[str, Any]:
    """Extract SIMPA MCP server configuration from mcp.json."""
    servers = config.get("mcpServers", {})
    simpa = servers.get("simpa-mcp")
    
    if not simpa:
        raise ValueError("simpa-mcp server configuration not found in mcp.json")
    
    return {
        "command": simpa.get("command"),
        "args": simpa.get("args", []),
        "env": simpa.get("env", {}),
    }


def parse_args_from_command(cmd_string: str) -> list[str]:
    """Extract CLI arguments from the command string.
    
    Args:
        cmd_string: The shell command from mcp.json args
        
    Returns:
        List of arguments after 'src/main.py'
    """
    import shlex
    
    # Parse the command string
    try:
        parts = shlex.split(cmd_string)
    except ValueError:
        # Fallback to simple split if shlex fails
        parts = cmd_string.split()
    
    # Find 'src/main.py' and extract args after it
    try:
        idx = parts.index("src/main.py")
        return parts[idx + 1:]
    except ValueError:
        # src/main.py not found, return empty list
        return []


def build_environment(base_env: dict[str, str]) -> dict[str, str]:
    """Build environment variables for the subprocess.
    
    Priority (highest to lowest):
    1. Explicit environment overrides (SIMPA_* variables)
    2. Current os.environ values
    3. Values from mcp.json
    """
    env = os.environ.copy()
    
    # Apply base environment from mcp.json (lower priority)
    for key, value in base_env.items():
        if key not in env:
            env[key] = value
    
    # Apply SIMPA-specific overrides
    if log_level := os.getenv("SIMPA_LOG_LEVEL"):
        env["LOG_LEVEL"] = log_level.upper()
    
    if log_file := os.getenv("SIMPA_LOG_FILE"):
        env["LOG_FILE"] = log_file
    
    if transport := os.getenv("SIMPA_TRANSPORT"):
        env["MCP_TRANSPORT"] = transport
    
    # Allow any Settings field to be overridden via SIMPA_* vars
    # Map SIMPA_DB_URL -> DATABASE_URL, etc.
    mapping = {
        "SIMPA_DB_URL": "DATABASE_URL",
        "SIMPA_EMBEDDING_MODEL": "EMBEDDING_MODEL",
        "SIMPA_EMBEDDING_PROVIDER": "EMBEDDING_PROVIDER",
        "SIMPA_LLM_MODEL": "LLM_MODEL",
        "SIMPA_LLM_TEMPERATURE": "LLM_TEMPERATURE",
        "SIMPA_OLLAMA_URL": "OLLAMA_BASE_URL",
    }
    
    for simpa_var, config_var in mapping.items():
        if value := os.getenv(simpa_var):
            env[config_var] = value
    
    return env


def build_command(base_args: list[str]) -> list[str]:
    """Build the command to execute with optional overrides.
    
    Args:
        base_args: Base arguments from mcp.json
        
    Returns:
        Full command list for subprocess
    """
    # Start with uv run python src/main.py
    cmd = ["uv", "run", "python", "src/main.py"]
    
    # Parse existing args to identify which ones are set
    existing = set()
    for i, arg in enumerate(base_args):
        if arg.startswith("--"):
            existing.add(arg)
            # Also capture the value if it's not another flag
            if i + 1 < len(base_args) and not base_args[i + 1].startswith("-"):
                existing.add(base_args[i + 1])
    
    # Apply environment overrides
    overrides = []
    
    if log_level := os.getenv("SIMPA_LOG_LEVEL"):
        if "--log-level" not in existing:
            overrides.extend(["--log-level", log_level])
    
    if log_file := os.getenv("SIMPA_LOG_FILE"):
        if "--log-file" not in existing:
            overrides.extend(["--log-file", log_file])
    
    if os.getenv("SIMPA_PROJECT_REQUIRED", "").lower() == "true":
        if "--project-id-required" not in existing:
            overrides.append("--project-id-required")
    
    if transport := os.getenv("SIMPA_TRANSPORT"):
        if "--transport" not in existing:
            overrides.extend(["--transport", transport])
    
    # Build final command: base args + overrides (overrides win if there are conflicts)
    # We need to handle duplicates - overrides should replace base values
    final_args = []
    skip_next = False
    
    for i, arg in enumerate(base_args):
        if skip_next:
            skip_next = False
            continue
        
        # Check if this arg is being overridden
        if arg == "--log-level" and os.getenv("SIMPA_LOG_LEVEL"):
            final_args.extend(["--log-level", os.getenv("SIMPA_LOG_LEVEL")])
            skip_next = True
        elif arg == "--log-file" and os.getenv("SIMPA_LOG_FILE"):
            final_args.extend(["--log-file", os.getenv("SIMPA_LOG_FILE")])
            skip_next = True
        elif arg == "--transport" and os.getenv("SIMPA_TRANSPORT"):
            final_args.extend(["--transport", os.getenv("SIMPA_TRANSPORT")])
            skip_next = True
        elif arg == "--project-id-required" and os.getenv("SIMPA_PROJECT_REQUIRED", "").lower() == "false":
            # Skip adding this flag
            pass
        else:
            final_args.append(arg)
    
    # Add any overrides that weren't in base_args
    for i in range(0, len(overrides), 2):
        if overrides[i] not in existing:
            final_args.extend(overrides[i:i+2] if i+1 < len(overrides) else [overrides[i]])
    
    return cmd + final_args


def print_config(env: dict[str, str], cmd: list[str]) -> None:
    """Print configuration summary."""
    print("=" * 60)
    print("SIMPA MCP Server Configuration")
    print("=" * 60)
    
    print("\nEnvironment Variables:")
    key_vars = [
        "DATABASE_URL",
        "EMBEDDING_MODEL", 
        "EMBEDDING_PROVIDER",
        "LLM_MODEL",
        "LOG_LEVEL",
        "MCP_TRANSPORT",
    ]
    for var in key_vars:
        if value := env.get(var):
            # Mask sensitive values
            display = value
            if "password" in var.lower() or "api_key" in var.lower():
                display = "***"
            elif "://" in value:
                # Mask password in URL
                import re
                display = re.sub(r":([^@]+)@", ":***@", value)
            print(f"  {var}: {display}")
    
    print(f"\nCommand: {' '.join(cmd)}")
    print("=" * 60)
    print()


def main() -> int:
    """Main entry point."""
    # Find and load mcp.json
    try:
        config_path = find_mcp_json()
        # Debug: print(f"Loading configuration from: {config_path}", file=sys.stderr)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    try:
        config = load_mcp_config(config_path)
        simpa_config = extract_simpa_config(config)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing mcp.json: {e}", file=sys.stderr)
        return 1
    
    # Extract CLI args from the command string
    # The args contain: ["-c", "cd /path && uv run python src/main.py ..."]
    cmd_string = ""
    for i, arg in enumerate(simpa_config["args"]):
        if arg == "-c" and i + 1 < len(simpa_config["args"]):
            cmd_string = simpa_config["args"][i + 1]
            break
    
    # Parse args from command string
    cli_args = parse_args_from_command(cmd_string)
    
    # Build environment and command
    env = build_environment(simpa_config["env"])
    cmd = build_command(cli_args)
    
    # NOTE: Debug output disabled - MCP stdio protocol requires ONLY JSON-RPC on stdout
    # print_config(env, cmd)
    
    # Change to script directory (where src/main.py is located)
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)
    
    # Execute the server
    try:
        result = subprocess.run(cmd, env=env, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nShutdown requested", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
