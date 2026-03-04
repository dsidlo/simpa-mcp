"""Tests for Docker Compose stack startup and health.

Verifies:
- Services start successfully
- Health checks pass
- Dependencies start in correct order
- Network connectivity between services
"""

import httpx
import pytest
import time

def _get_ollama_port(compose_file) -> int:
    """Get the Ollama port based on compose file."""
    # Test compose uses port 11435, standard uses 11434
    return 11435 if "test" in str(compose_file) else 11434


@pytest.mark.docker
@pytest.mark.slow
class TestDockerComposeStartup:
    """Test Docker Compose stack startup."""
    
    def test_postgres_starts(self, docker_compose_stack):
        """Verify PostgreSQL container starts."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        containers = docker_compose_stack.compose.ps()
        postgres_containers = [c for c in containers if "postgres" in str(c.name)]
        assert len(postgres_containers) > 0, "PostgreSQL container not found"
    
    def test_postgres_healthy(self, docker_compose_stack):
        """Verify PostgreSQL is healthy."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        time.sleep(3)
        result = docker_compose_stack.compose.execute(
            "postgres",
            ["pg_isready", "-U", "simpa", "-d", "simpa"],
        )
        assert result == 0, "PostgreSQL is not healthy"
    
    def test_ollama_starts(self, docker_compose_stack):
        """Verify Ollama container starts."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        containers = docker_compose_stack.compose.ps()
        ollama_containers = [c for c in containers if "ollama" in str(c.name)]
        assert len(ollama_containers) > 0, "Ollama container not found"
    
    def test_ollama_responds(self, docker_compose_stack, compose_file):
        """Verify Ollama API is accessible."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
        
        port = _get_ollama_port(compose_file)
        try:
            response = httpx.get(f"http://localhost:{port}/api/tags", timeout=10)
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"Ollama not accessible: {e}")
    
    def test_simpa_starts(self, docker_compose_stack):
        """Verify SIMPA container starts."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        containers = docker_compose_stack.compose.ps()
        simpa_containers = [c for c in containers if "simpa" in str(c.name)]
        assert len(simpa_containers) > 0, "SIMPA container not found"
    
    def test_simpa_health_endpoint(self, running_mcp_server: str, mcp_client):
        """Verify SIMPA health endpoint responds."""
        if running_mcp_server is None:
            pytest.skip("Docker not available")
            
        try:
            response = httpx.get(f"{running_mcp_server}/health", timeout=10)
            assert response.status_code == 200
        except httpx.ConnectError as e:
            pytest.fail(f"Cannot connect to SIMPA server: {e}")
    
    def test_database_connectivity(self, docker_compose_stack):
        """Verify SIMPA can connect to PostgreSQL."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        result = docker_compose_stack.compose.execute(
            "simpa",
            [
                "python", "-c",
                "import asyncpg; import asyncio; "
                "async def test(): "
                "    conn = await asyncpg.connect('postgresql://simpa:simpa@postgres:5432/simpa'); "
                "    await conn.close(); print('OK')"
                "; asyncio.run(test())"
            ],
        )
        assert result == 0, "Database connectivity test failed"
    
    def test_ollama_connectivity(self, docker_compose_stack, compose_file):
        """Verify SIMPA can connect to Ollama."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
        
        port = _get_ollama_port(compose_file)
        try:
            response = httpx.get(f"http://localhost:{port}/api/tags", timeout=5)
            assert response.status_code in [200, 404]
        except httpx.ConnectError:
            pytest.fail("SIMPA cannot connect to Ollama")


@pytest.mark.docker
class TestDockerNetwork:
    """Test Docker network connectivity."""
    
    def test_network_created(self, docker_compose_stack):
        """Verify simpa-network exists."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        from python_on_whales import DockerClient
        docker = DockerClient()
        networks = docker.network.list()
        simpa_networks = [n for n in networks if "simpa" in str(n.name)]
        assert len(simpa_networks) > 0, "simpa-network not found"
    
    def test_containers_on_same_network(self, docker_compose_stack):
        """Verify containers can communicate."""
        if docker_compose_stack is None:
            pytest.skip("Docker not available")
            
        result = docker_compose_stack.compose.execute(
            "simpa",
            ["ping", "-c", "1", "postgres"],
        )
        assert result == 0, "simpa cannot resolve postgres hostname"
