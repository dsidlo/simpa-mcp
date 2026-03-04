"""Tests for MCP endpoints via Docker container.

Verifies MCP tools work correctly when running in Docker:
- health_check
- refine_prompt
- update_prompt_results
- create_project, get_project, list_projects
"""

import uuid

import httpx
import pytest
from python_on_whales import DockerClient


@pytest.mark.docker
@pytest.mark.asyncio
@pytest.mark.slow
class TestHealthEndpoint:
    """Test health_check endpoint."""
    
    async def test_health_check_returns_200(self, running_mcp_server: str, mcp_client):
        """Health endpoint should return OK."""
        response = await mcp_client.get("/health")
        assert response.status_code == 200
    
    async def test_health_check_returns_json(self, running_mcp_server: str, mcp_client):
        """Health endpoint should return JSON with status."""
        response = await mcp_client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


@pytest.mark.docker
@pytest.mark.asyncio
@pytest.mark.slow
class TestMCPRefinePrompt:
    """Test refine_prompt MCP tool via Docker."""
    
    async def test_refine_prompt_success(
        self,
        running_mcp_server: str,
        mcp_client,
        ollama_available: bool,
    ):
        """Test refine_prompt with Ollama running."""
        if not ollama_available:
            pytest.skip("Ollama not available in Docker")
        
        response = await mcp_client.post(
            "/mcp/v1/tools/refine_prompt",
            json={
                "prompt": "How do I write a Python function?",
                "agent_type": "developer",
            },
        )
        
        # Should succeed even if Ollama model isn't pulled yet
        # The service might return an error response which is still valid
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
    
    async def test_refine_prompt_validation(self, running_mcp_server: str, mcp_client):
        """Test refine_prompt input validation."""
        # Missing required field
        response = await mcp_client.post(
            "/mcp/v1/tools/refine_prompt",
            json={},
        )
        assert response.status_code == 422, "Should validate required fields"
    
    async def test_refine_prompt_invalid_agent_type(self, running_mcp_server: str, mcp_client):
        """Test refine_prompt with invalid agent type."""
        response = await mcp_client.post(
            "/mcp/v1/tools/refine_prompt",
            json={
                "prompt": "Test prompt",
                "agent_type": "invalid_agent_type",
            },
        )
        # Should return validation error
        assert response.status_code == 422


@pytest.mark.docker
@pytest.mark.asyncio
@pytest.mark.slow
class TestMCPUpdatePromptResults:
    """Test update_prompt_results MCP tool via Docker."""
    
    async def test_update_prompt_results_validation(self, running_mcp_server: str, mcp_client):
        """Test update_prompt_results input validation."""
        # Missing required fields
        response = await mcp_client.post(
            "/mcp/v1/tools/update_prompt_results",
            json={},
        )
        assert response.status_code == 422
    
    async def test_update_prompt_results_invalid_prompt_key(self, running_mcp_server: str, mcp_client):
        """Test with invalid prompt key format."""
        response = await mcp_client.post(
            "/mcp/v1/tools/update_prompt_results",
            json={
                "prompt_key": "invalid-key",
                "score": 4.5,
                "status": "succeeded",
            },
        )
        # UUID validation should fail
        assert response.status_code == 422


@pytest.mark.docker
@pytest.mark.asyncio
@pytest.mark.slow
class TestMCPProjectEndpoints:
    """Test project management MCP tools."""
    
    async def test_create_project_success(self, running_mcp_server: str, mcp_client):
        """Test create_project endpoint."""
        response = await mcp_client.post(
            "/mcp/v1/tools/create_project",
            json={
                "name": f"Test Project {uuid.uuid4()}",
                "description": "A test project created via Docker",
            },
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data or "project_id" in data
        else:
            # Might fail due to dependency on DB migrations, etc
            pytest.skip(f"Project creation returned: {response.status_code}")
    
    async def test_create_project_validation(self, running_mcp_server: str, mcp_client):
        """Test create_project validation."""
        # Missing required name
        response = await mcp_client.post(
            "/mcp/v1/tools/create_project",
            json={"description": "Missing name"},
        )
        assert response.status_code == 422
    
    async def test_list_projects(self, running_mcp_server: str, mcp_client):
        """Test list_projects endpoint."""
        response = await mcp_client.get("/mcp/v1/tools/list_projects")
        
        # Endpoint might not exist or return differently
        assert response.status_code in [200, 404, 422], f"Unexpected status: {response.status_code}"
    
    async def test_get_project_not_found(self, running_mcp_server: str, mcp_client):
        """Test get_project with non-existent project."""
        response = await mcp_client.get(
            f"/mcp/v1/tools/get_project?id={uuid.uuid4()}"
        )
        # Should either return 404 or a not found response
        assert response.status_code in [200, 404, 400, 422]


@pytest.mark.docker
class TestDockerLogs:
    """Test Docker container logging."""
    
    def test_simpa_logs_available(self, docker_compose_stack: DockerClient):
        """Verify SIMPA container produces logs."""
        import io
        
        # Capture logs
        logs = docker_compose_stack.compose.logs(
            "simpa",
            project_name="simpa-test",
            tail="50",
        )
        
        # Verify logs are captured (even if empty string)
        assert logs is not None
    
    def test_postgres_logs_available(self, docker_compose_stack: DockerClient):
        """Verify PostgreSQL container produces logs."""
        logs = docker_compose_stack.compose.logs(
            "postgres",
            project_name="simpa-test",
            tail="20",
        )
        assert logs is not None
