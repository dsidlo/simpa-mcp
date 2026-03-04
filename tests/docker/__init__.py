"""Docker integration tests for SIMPA MCP Server.

These tests verify:
1. Docker image builds successfully (multi-stage)
2. Docker compose stack starts and services are healthy
3. MCP endpoints work via the running Docker container
4. Production image meets security requirements

Requirements:
- Docker daemon running
- docker-compose available
- python-on-whales installed

Run with: pytest tests/docker/ -v
"""
