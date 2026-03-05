#!/usr/bin/env python3
"""SIMPA MCP Server entry point."""

import argparse
import os
import sys
from pathlib import Path

# CRITICAL: Must parse --env arg VERY EARLY (before any imports that use environment)
def _load_env_file():
    """Parse --env argument and load .env file before other imports."""
    # Pre-parse just the --env arg
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env", type=str, default=None, dest="env_file")
    args, _ = parser.parse_known_args()
    
    # Determine which .env file to load
    if args.env_file:
        # User specified a custom .env file
        env_path = Path(args.env_file).expanduser().resolve()
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path, override=True)
            # Store the path for logging later
            os.environ["_SIMPA_ENV_FILE"] = str(env_path)
        else:
            print(f"Warning: Specified --env file not found: {env_path}", file=sys.stderr)
    elif (Path.home() / ".env").exists():
        # Default: load ~/.env if it exists
        from dotenv import load_dotenv
        load_dotenv(Path.home() / ".env")
        os.environ["_SIMPA_ENV_FILE"] = str(Path.home() / ".env")
    
    return args.env_file


# Load .env file BEFORE any other imports
_custom_env_file = _load_env_file()

# Now safe to set other environment variables
os.environ["LITELLM_LOG"] = "ERROR"  # Silence LiteLLM to prevent stdout pollution
os.environ["FASTMCP_SHOW_SERVER_BANNER"] = "false"  # Silence FastMCP banner

import asyncio

# Must configure logging BEFORE any imports that might use the database
def setup_logging_early():
    """Parse just enough args to configure logging early."""
    # Pre-parse just the logging args
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log-level", type=str, default="info", dest="log_level")
    parser.add_argument("--log-file", type=str, default="/tmp/simpa-mcp.log")
    parser.add_argument("--log-console", action="store_true")
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument("--project-id-required", action="store_true")
    
    # Parse known args only
    args, _ = parser.parse_known_args()
    
    # Setup logging
    from simpa.utils.logging import setup_logging
    console_output = args.log_console
    setup_logging(
        level=args.log_level,
        log_file=args.log_file,
        console_output=console_output,
    )
    
    # CRITICAL: Suppress FastMCP/MCP loggers that write to stdout
    # These MUST be suppressed for MCP stdio mode to work
    import logging
    logging.getLogger("fastmcp").setLevel(logging.ERROR)
    logging.getLogger("fastmcp.server").setLevel(logging.ERROR)
    logging.getLogger("mcp").setLevel(logging.ERROR)
    logging.getLogger("mcp.server").setLevel(logging.ERROR)
    
    return args


# Configure logging before any other imports
_early_args = setup_logging_early()

# Now we can import the rest
from simpa.db.engine import init_db
from simpa.mcp_server import main as mcp_main
from simpa.utils.logging import get_logger

logger = get_logger(__name__)


async def init_database():
    """Initialize the database."""
    logger.info("initializing_database")
    await init_db()
    logger.info("database_initialization_complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SIMPA - Self-Improving Meta Prompt Agent"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize the database and exit",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=None,
        help="MCP transport protocol (overrides config)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["trace", "debug", "info", "warn", "error", "fatal"],
        default="info",
        metavar="LEVEL",
        dest="log_level",
        help="Log level (trace, debug, info, warn, error, fatal) - default: info",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="/tmp/simpa-mcp.log",
        metavar="PATH",
        help="Path to log file - default: /tmp/simpa-mcp.log",
    )
    parser.add_argument(
        "--log-console",
        action="store_true",
        help="Also log to console (stderr) - NOT recommended for MCP stdio mode",
    )
    parser.add_argument(
        "--project-id-required",
        action="store_true",
        dest="project_id_required",
        help="Require project_id for all prompt refinement requests",
    )
    parser.add_argument(
        "--env",
        type=str,
        default="~/.env",
        metavar="PATH",
        help="Path to .env file - default:~/.env (also checks ./.env)",
    )

    args = parser.parse_args()
    
    # Log which env file is being used
    env_file = os.environ.get("_SIMPA_ENV_FILE", "~/.env")
    if not Path(env_file).exists() and Path(".env").exists():
        env_file = "./.env"
    
    # Log startup with env file info
    logger.info(
        "simpa_mcp_server_starting",
        transport=args.transport or "stdio",
        log_level=args.log_level,
        log_file=args.log_file,
        env_file=env_file if Path(env_file).exists() else "none",
    )

    # Override transport if provided
    if args.transport:
        from simpa.config import settings
        settings.mcp_transport = args.transport
        logger.trace("transport_overridden", transport=args.transport)

    # Handle database initialization mode
    if args.init_db:
        logger.info("init_db_mode")
        asyncio.run(init_database())
        sys.exit(0)

    # Enable strict project_id requirement if flag provided
    if args.project_id_required:
        from simpa.config import settings
        settings.require_project_id = True
        logger.info("project_id_required_enabled")

    # Run the MCP server
    logger.info("starting_mcp_server")
    try:
        mcp_main()
    except Exception as e:
        logger.error("mcp_server_failed", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    main()
