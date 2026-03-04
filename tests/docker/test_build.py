"""Tests for Docker image builds.

Verifies:
- Multi-stage Dockerfile builds successfully
- Builder, development, and production targets work
- Image security and size constraints
"""

import subprocess

import pytest
from python_on_whales import DockerClient


@pytest.mark.docker
class TestDockerBuild:
    """Test Docker image builds."""
    
    def test_dockerfile_exists(self, docker_client: DockerClient):
        """Verify Dockerfile exists."""
        import os
        assert os.path.exists("Dockerfile"), "Dockerfile not found"
    
    def test_dockerfile_builds_development(self, docker_client: DockerClient):
        """Test Dockerfile development target builds successfully."""
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        dockerfile = project_root / "Dockerfile"
        
        # Build development stage
        result = docker_client.build(
            project_root,
            file=dockerfile,
            target="development",
            tags=["simpa:test-dev"],
        )
        assert result is not None, "Development build failed"
        
        # Verify image exists
        images = docker_client.image.list("simpa:test-dev")
        assert len(images) > 0, "Development image not found"
    
    def test_dockerfile_builds_production(self, docker_client: DockerClient):
        """Test Dockerfile production target builds successfully."""
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        dockerfile = project_root / "Dockerfile"
        
        # Build production stage
        result = docker_client.build(
            project_root,
            file=dockerfile,
            target="production",
            tags=["simpa:test-prod"],
        )
        assert result is not None, "Production build failed"
        
        # Verify image exists
        images = docker_client.image.list("simpa:test-prod")
        assert len(images) > 0, "Production image not found"
    
    def test_production_image_has_non_root_user(self, docker_client: DockerClient):
        """Verify production image runs as non-root user."""
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        dockerfile = project_root / "Dockerfile"
        
        # Build production image if not exists
        images = docker_client.image.list("simpa:test-prod")
        if not images:
            docker_client.build(
                project_root,
                file=dockerfile,
                target="production",
                tags=["simpa:test-prod"],
            )
        
        # Run container with entrypoint override to skip migrations
        output = docker_client.run(
            "simpa:test-prod",
            ["id", "-u"],
            remove=True,
            entrypoint="",
            envs={"SKIP_MIGRATIONS": "true"},
        )
        
        # Should not be 0 (root)
        user_id = output.strip()
        assert user_id != "0", f"Production image runs as root user (uid: {user_id})"
        
    def test_production_image_security_scan(self, docker_client: DockerClient):
        """Basic security checks on production image.
        
        Note: This is a basic check. For full security scanning,
        use trivy or grype in CI/CD pipeline.
        """
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        dockerfile = project_root / "Dockerfile"
        
        # Build production image if not exists
        images = docker_client.image.list("simpa:test-prod")
        if not images:
            docker_client.build(
                project_root,
                file=dockerfile,
                target="production",
                tags=["simpa:test-prod"],
            )
        
        # Check that common dev tools are not present
        try:
            docker_client.run(
                "simpa:test-prod",
                ["which", "gcc"],
                remove=True,
            )
            pytest.fail("gcc should not be present in production image")
        except Exception:
            # Expected - gcc not found
            pass


@pytest.mark.docker
class TestDockerComposeBuild:
    """Test Docker Compose build process."""
    
    def test_compose_file_exists(self, compose_file):
        """Verify docker-compose.yml exists."""
        assert compose_file.exists(), f"docker-compose.yml not found at {compose_file}"
    
    def test_compose_build(self, docker_client: DockerClient, compose_file):
        """Test docker-compose build."""
        from pathlib import Path
        import os as os_module
        
        project_root = compose_file.parent
        original_cwd = os_module.getcwd()
        
        try:
            os_module.chdir(project_root)
            # Build using compose (project_name not supported by python-on-whales)
            docker_client.compose.build()
            
            # Verify success (no exception thrown)
            assert True
        finally:
            os_module.chdir(original_cwd)
