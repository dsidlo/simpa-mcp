#!/usr/bin/env python3
"""SIMPA MCP Server entry point."""

import argparse
import asyncio
import sys

from simpa.db.engine import init_db
from simpa.mcp_server import main as mcp_main


async def init_database():
    """Initialize the database."""
    print("Initializing SIMPA database...")
    await init_db()
    print("Database initialized successfully.")


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
    
    args = parser.parse_args()
    
    # Override transport if provided
    if args.transport:
        from simpa.config import settings
        settings.mcp_transport = args.transport
    
    if args.init_db:
        asyncio.run(init_database())
        sys.exit(0)
    
    # Run the MCP server
    mcp_main()


if __name__ == "__main__":
    main()
