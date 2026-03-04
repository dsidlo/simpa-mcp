"""Pytest fixtures for Docker tests."""

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Generator

import httpx
import pytest

try:
    from python_on_whales import DockerClient
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Ports that Docker containers need
REQUIRED_PORTS = [5432, 11434, 8000]

# Ports used by docker-compose.test.yml (alternative to avoid conflicts)
TEST_PORTS = [5433, 11435, 8001]


def docker_is_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except socket.error:
            return True


def check_port_availability() -> list[int]:
    """Check which required ports are in use."""
    return [p for p in REQUIRED_PORTS if is_port_in_use(p)]


@pytest.fixture(scope="session")
def docker_client() -> Generator:
    """Provide a Docker client."""
    if not DOCKER_AVAILABLE:
        pytest.skip("python-on-whales not installed")
    if not docker_is_running():
        pytest.skip("Docker daemon not running")
    
    client = DockerClient()
    yield client


@pytest.fixture(scope="session")
def compose_file() -> Path:
    """Path to the docker-compose file.
    
    Uses docker-compose.test.yml with alternative ports (5433, 11435, 8001)
    to avoid conflicts with local services. Falls back to docker-compose.yml.
    """
    test_compose = PROJECT_ROOT / "docker-compose.test.yml"
    if test_compose.exists():
        return test_compose
    return PROJECT_ROOT / "docker-compose.yml"


@pytest.fixture(scope="session")
def docker_compose_stack(compose_file: Path) -> Generator:
    """Start the full Docker compose stack for testing.
    
    Services: postgres, ollama, simpa
    
    Yields:
        DockerClient with compose up
    """
    if not DOCKER_AVAILABLE:
        pytest.skip("python-on-whales not installed")
    if not docker_is_running():
        pytest.skip("Docker daemon not running")
    if not compose_file.exists():
        pytest.skip(f"docker-compose file not found at {compose_file}")
    
    # Determine which ports to check based on compose file used
    using_test_compose = "test" in compose_file.name
    ports_to_check = TEST_PORTS if using_test_compose else REQUIRED_PORTS
    
    # Check for port conflicts
    blocked_ports = [p for p in ports_to_check if is_port_in_use(p)]
    if blocked_ports:
        pytest.skip(
            f"Required ports already in use: {blocked_ports}. "
            "Stop local services or run tests in isolated environment."
        )
    
    # Create DockerClient with the specific compose file
    docker_client = DockerClient(compose_files=[compose_file])
    
    # Change to project directory for compose commands
    import os as os_module
    original_cwd = os_module.getcwd()
    os_module.chdir(PROJECT_ROOT)
    
    try:
        # Build images first
        docker_client.compose.build()
        
        # Start services
        docker_client.compose.up(
            services=["postgres", "ollama", "simpa"],
            detach=True,
        )
        
        # Wait for services to be healthy
        _wait_for_services(docker_client, timeout=120)
        yield docker_client
        
    finally:
        # Cleanup: remove containers and volumes
        try:
            docker_client.compose.down(volumes=True)
        except Exception:
            pass
        os_module.chdir(original_cwd)


def _wait_for_services(docker_client, timeout: int = 120) -> None:
    """Wait for all services to be healthy.
    
    Args:
        docker_client: Docker client instance
        timeout: Maximum wait time in seconds
    """
    import subprocess
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Check if containers are running
            containers = docker_client.compose.ps()
            
            if len(containers) >= 3:  # postgres, ollama, simpa
                # Get the simpa container name
                simpa_container = None
                for c in containers:
                    if "simpa" in str(c.name).lower():
                        simpa_container = c.name
                        break
                
                if simpa_container:
                    # Try to run a simple command in simpa using docker exec
                    result = subprocess.run(
                        ["docker", "exec", simpa_container, "python", "-c", "print('healthy')"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        time.sleep(2)
                        return
        except Exception:
            pass
        
        time.sleep(2)
    
    raise TimeoutError(f"Services did not become healthy within {timeout}s")


@pytest.fixture(scope="session")
def running_mcp_server(docker_compose_stack, compose_file: Path) -> str:
    """Get the base URL for the running MCP server.
    
    Returns:
        Base URL for HTTP requests (e.g., "http://localhost:8000" or "http://localhost:8001")
    """
    if docker_compose_stack is None:
        pytest.skip("Docker not available")
    # Use port 8001 if using test compose file, otherwise 8000
    port = 8001 if "test" in compose_file.name else 8000
    return f"http://localhost:{port}"


@pytest.fixture(scope="session")
def mcp_client(running_mcp_server: str) -> Generator[httpx.AsyncClient, None, None]:
    """Provide an HTTP client for MCP endpoint testing.
    
    Yields:
        Async HTTP client configured for MCP server
    """
    client = httpx.AsyncClient(
        base_url=running_mcp_server,
        timeout=30.0,
    )
    yield client


@pytest.fixture
def ollama_available(compose_file: Path) -> bool:
    """Check if Ollama service is available."""
    # Use port 11435 if using test compose file, otherwise 11434
    port = 11435 if "test" in compose_file.name else 11434
    try:
        response = httpx.get(f"http://localhost:{port}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False
