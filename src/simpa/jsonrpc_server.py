#!/usr/bin/env python3
"""JSON-RPC server over stdio for SIMPA. (for pi extension integration)

This server reads JSON-RPC requests from stdin and writes responses to stdout.
It loads on first access and stays hot for multiple sessions.
"""

import asyncio
import sys
import json
import os
from typing import Any, Callable
from contextlib import asynccontextmanager

# Add the project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from simpa.config import settings
from simpa.service_api import (
    refine_prompt,
    update_prompt_results,
    create_project,
    get_project,
    list_projects,
    activate_prompt,
    deactivate_prompt,
    health_check,
)


class JSONRPCError(Exception):
    """JSON-RPC error with code and message."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JSONRPCServer:
    """JSON-RPC server over stdio."""

    def __init__(self):
        self.methods: dict[str, Callable] = {
            "refine_prompt": self._refine_prompt,
            "update_prompt_results": self._update_prompt_results,
            "create_project": self._create_project,
            "get_project": self._get_project,
            "list_projects": self._list_projects,
            "activate_prompt": self._activate_prompt,
            "deactivate_prompt": self._deactivate_prompt,
            "health_check": self._health_check,
        }

    async def _refine_prompt(self, params: dict) -> dict:
        """Refine a prompt."""
        result = await refine_prompt(
            agent_type=params["agent_type"],
            original_prompt=params["original_prompt"],
            project_id=params.get("project_id"),
            context=params.get("context"),
            main_language=params.get("main_language"),
            other_languages=params.get("other_languages"),
            domain=params.get("domain"),
            tags=params.get("tags"),
        )
        return result

    async def _update_prompt_results(self, params: dict) -> dict:
        """Update prompt results."""
        result = await update_prompt_results(
            prompt_key=params["prompt_key"],
            action_score=params["action_score"],
            files_modified=params.get("files_modified"),
            files_added=params.get("files_added"),
            files_deleted=params.get("files_deleted"),
            diffs=params.get("diffs"),
            validation_results=params.get("validation_results"),
            executed_by_agent=params.get("executed_by_agent"),
            execution_duration_ms=params.get("execution_duration_ms"),
            test_passed=params.get("test_passed"),
            lint_score=params.get("lint_score"),
            security_scan_passed=params.get("security_scan_passed"),
        )
        return result

    async def _create_project(self, params: dict) -> dict:
        """Create a project."""
        result = await create_project(
            project_name=params["project_name"],
            description=params.get("description"),
            main_language=params.get("main_language"),
            other_languages=params.get("other_languages"),
            library_dependencies=params.get("library_dependencies"),
            project_structure=params.get("project_structure"),
        )
        return result

    async def _get_project(self, params: dict) -> dict:
        """Get project by ID or name."""
        result = await get_project(
            project_id=params.get("project_id"),
            project_name=params.get("project_name"),
        )
        return result

    async def _list_projects(self, params: dict) -> dict:
        """List projects."""
        result = await list_projects(
            main_language=params.get("main_language"),
            limit=params.get("limit", 50),
            offset=params.get("offset", 0),
        )
        return result

    async def _activate_prompt(self, params: dict) -> dict:
        """Activate a prompt."""
        result = await activate_prompt(prompt_key=params["prompt_key"])
        return result

    async def _deactivate_prompt(self, params: dict) -> dict:
        """Deactivate a prompt."""
        result = await deactivate_prompt(prompt_key=params["prompt_key"])
        return result

    async def _health_check(self, params: dict) -> dict:
        """Health check."""
        result = await health_check()
        return result

    async def handle_request(self, request: dict) -> dict | None:
        """Handle a single JSON-RPC request."""
        # Validate request structure
        if not isinstance(request, dict):
            return self._error(None, INVALID_REQUEST, "Invalid Request")

        request_id = request.get("id")
        method_name = request.get("method")
        params = request.get("params", {})

        if not isinstance(method_name, str):
            return self._error(request_id, INVALID_REQUEST, "Method must be a string")

        method = self.methods.get(method_name)
        if not method:
            return self._error(
                request_id,
                METHOD_NOT_FOUND,
                f"Method not found: {method_name}"
            )

        try:
            result = await method(params)
            return self._success(request_id, result)
        except JSONRPCError as e:
            return self._error(request_id, e.code, e.message, e.data)
        except Exception as e:
            return self._error(request_id, INTERNAL_ERROR, str(e))

    def _success(self, id: Any, result: Any) -> dict:
        """Create success response."""
        return {
            "jsonrpc": "2.0",
            "id": id,
            "result": result
        }

    def _error(self, id: Any, code: int, message: str, data: Any = None) -> dict:
        """Create error response."""
        error = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": id,
            "error": error
        }

    async def run(self):
        """Main loop reading from stdin."""
        print("SIMPA JSON-RPC server ready", file=sys.stderr, flush=True)

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    # EOF - stdin closed
                    break

                line = line.decode().strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    response = self._error(None, PARSE_ERROR, f"Parse error: {e}")
                    self._send(response)
                    continue

                response = await self.handle_request(request)
                if response:  # None for notifications (id not present)
                    self._send(response)

        except asyncio.CancelledError:
            pass
        finally:
            print("SIMPA JSON-RPC server shutting down", file=sys.stderr, flush=True)

    def _send(self, response: dict):
        """Send response to stdout."""
        print(json.dumps(response), flush=True)


def main():
    """Entry point."""
    server = JSONRPCServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
