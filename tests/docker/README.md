# Docker Tests for SIMPA MCP Server

Automated Docker lifecycle testing for the SIMPA MCP Server.

## Overview

These tests automate the **full Docker lifecycle**:
1. **Build** - Build Docker images (multi-stage)
2. **Run** - Start containers via docker-compose
3. **Health Check** - Verify services are healthy
4. **Shutdown** - Clean up containers and volumes

## Test Structure

| File | Purpose |
|------|---------|
| `conftest.py` | Shared fixtures that manage Docker lifecycle |
| `__init__.py` | Test package initialization with docs |
| `test_lifecycle.py` | Core lifecycle automation tests |
| `test_build.py` | Docker image build tests |
| `test_startup.py` | Service startup and health tests |
| `test_mcp_endpoints.py` | MCP endpoint tests via container |

## Automated Lifecycle

The `docker_compose_stack` fixture (session-scoped) handles automation:

```python
# 1. Build
docker_client.compose.build()

# 2. Run
docker_client.compose.up(
    services=["postgres", "ollama", "simpa"],
    detach=True,
)

# 3. Health Check
_wait_for_services(docker_client)

# 4. Yield for tests
yield docker_client

# 5. Shutdown (in finally block)
docker_client.compose.down(volumes=True)
```

## Requirements

- Docker daemon running
- `python-on-whales>=0.60.0` (installed via `uv sync --extra dev`)
- docker-compose available

## Running Tests

```bash
# Run all Docker tests (requires Docker)
uv run pytest tests/docker -v

# Run with Docker markers explicitly
uv run pytest tests/docker -m docker -v

# Skip Docker tests (run everything else)
uv run pytest tests/ --ignore=tests/docker -v

# Run specific lifecycle test
uv run pytest tests/docker/test_lifecycle.py -v
```

## Test Categories

### Build Tests (`test_build.py`)
- Multi-stage Dockerfile builds
- Development and production targets
- Security checks (non-root user)
- Image size validation

### Startup Tests (`test_startup.py`)
- PostgreSQL container startup and health
- Ollama container startup
- SIMPA container startup
- Database connectivity verification
- Network connectivity between services

### MCP Endpoint Tests (`test_mcp_endpoints.py`)
- Health endpoint via running container
- refine_prompt tool execution
- Project management endpoints
- Container log verification

### Lifecycle Tests (`test_lifecycle.py`)
- Full build → run → health → shutdown cycle
- Production target build verification
- Automatic cleanup on test failure

## Environment Handling

Tests automatically skip if:
- `python-on-whales` not installed
- Docker daemon not running
- `docker-compose.yml` not found

This allows the test suite to run in CI/CD without Docker while still testing the Docker automation when available.

## Configuration

Add to `pytest.ini`:
```ini
markers =
    docker: marks tests that require Docker daemon
    slow: marks tests that take longer than 30 seconds
```

Or use `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "docker: marks tests that require Docker daemon",
    "slow: marks tests that take longer than 30 seconds",
]
```
