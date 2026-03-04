"""Test Docker lifecycle automation.

This test verifies the full Docker lifecycle:
1. Build images
2. Run containers
3. Verify health
4. Shutdown and cleanup
"""

import socket
import subprocess

import pytest

try:
    from python_on_whales import DockerClient
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


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
    required_ports = [5432, 11434, 8000]
    return [p for p in required_ports if is_port_in_use(p)]


def check_test_port_availability() -> list[int]:
    """Check which test ports are in use (5433, 11435, 8001)."""
    test_ports = [5433, 11435, 8001]
    return [p for p in test_ports if is_port_in_use(p)]


def get_compose_file() -> Path:
    """Get the compose file to use.
    
    Prefers docker-compose.test.yml with alternative ports.
    """
    test_compose = PROJECT_ROOT / "docker-compose.test.yml"
    if test_compose.exists():
        return test_compose
    return PROJECT_ROOT / "docker-compose.yml"


@pytest.mark.docker
class TestDockerLifecycle:
    """Test full Docker lifecycle automation."""

    def test_lifecycle_build_run_shutdown(self):
        """Full lifecycle: build → run → health check → shutdown."""
        if not DOCKER_AVAILABLE:
            pytest.skip("python-on-whales not installed")
        if not docker_is_running():
            pytest.skip("Docker daemon not running")

        # Determine which compose file and ports to use
        compose_file = get_compose_file()
        using_test_compose = "test" in compose_file.name
        
        if using_test_compose:
            blocked_ports = check_test_port_availability()
        else:
            blocked_ports = check_port_availability()
            
        if blocked_ports:
            pytest.skip(
                f"Required ports already in use: {blocked_ports}. "
                "Stop local services or run tests in isolated environment."
            )

        docker = DockerClient(compose_files=[compose_file])

        if not compose_file.exists():
            pytest.skip(f"docker-compose file not found at {compose_file}")

        # Step 1: Build images
        import os
        original_cwd = os.getcwd()
        os.chdir(PROJECT_ROOT)

        try:
            docker.compose.build()
            print("✓ Images built successfully")

            # Step 2: Run containers
            docker.compose.up(
                services=["postgres"],
                detach=True,
            )
            print("✓ Containers started")

            # Step 3: Verify containers are running
            containers = docker.compose.ps()
            assert len(containers) > 0, "No containers running"
            print(f"✓ {len(containers)} container(s) running")

            # Step 4: Health check
            import time
            time.sleep(3)  # Wait for postgres to initialize
            
            # Use container exec instead of compose execute to capture output properly
            containers = docker.compose.ps()
            postgres_container = None
            for c in containers:
                if "postgres" in str(c.name):
                    postgres_container = c
                    break
            
            if postgres_container is None:
                pytest.fail("PostgreSQL container not found")
            
            # Use docker container exec directly via subprocess
            import subprocess
            health_check = subprocess.run(
                ["docker", "exec", postgres_container.name, "pg_isready", "-U", "simpa"],
                capture_output=True,
                text=True,
            )
            assert health_check.returncode == 0, f"Health check failed: {health_check.stderr}"
            print("✓ Health check passed")

        finally:
            # Step 5: Shutdown and cleanup
            docker.compose.down(volumes=True)
            print("✓ Containers and volumes cleaned up")
            os.chdir(original_cwd)

    def test_docker_build_production_target(self):
        """Test building production Docker target."""
        if not DOCKER_AVAILABLE:
            pytest.skip("python-on-whales not installed")
        if not docker_is_running():
            pytest.skip("Docker daemon not running")

        docker = DockerClient()
        dockerfile = PROJECT_ROOT / "Dockerfile"

        if not dockerfile.exists():
            pytest.skip("Dockerfile not found")

        try:
            # Build production stage
            docker.build(
                PROJECT_ROOT,
                file=dockerfile,
                target="production",
                tags=["simpa:test-lifecycle"],
            )
            print("✓ Production image built")

            # Verify image exists
            images = docker.image.list("simpa:test-lifecycle")
            assert len(images) > 0, "Image not found after build"
            print("✓ Image exists in registry")

        finally:
            # Cleanup
            try:
                docker.image.remove("simpa:test-lifecycle", force=True)
                print("✓ Test image cleaned up")
            except Exception:
                pass

    def test_container_auto_cleanup_on_failure(self):
        """Verify containers are cleaned up even if test fails."""
        if not DOCKER_AVAILABLE:
            pytest.skip("python-on-whales not installed")
        if not docker_is_running():
            pytest.skip("Docker daemon not running")

        # Determine which compose file and ports to use
        compose_file = get_compose_file()
        using_test_compose = "test" in compose_file.name
        
        if using_test_compose:
            blocked_ports = check_test_port_availability()
        else:
            blocked_ports = check_port_availability()
            
        if blocked_ports:
            pytest.skip(
                f"Required ports already in use: {blocked_ports}. "
                "Stop local services or run tests in isolated environment."
            )

        docker = DockerClient(compose_files=[compose_file])

        if not compose_file.exists():
            pytest.skip(f"docker-compose file not found at {compose_file}")

        import os
        original_cwd = os.getcwd()
        os.chdir(PROJECT_ROOT)

        container_name = None
        try:
            # Start a container
            docker.compose.up(
                services=["postgres"],
                detach=True,
            )

            # Get container info
            containers = docker.compose.ps()
            if containers:
                container_name = str(containers[0].name)

            # Simulate test failure scenario
            raise RuntimeError("Simulated test failure")

        except RuntimeError:
            # Cleanup should still happen in finally
            pass
        finally:
            docker.compose.down(volumes=True)
            os.chdir(original_cwd)

        # Verify cleanup worked
        remaining = docker.compose.ps()
        # Filter out any unrelated containers
        test_containers = [c for c in remaining if "simpa" in str(c.name)]
        assert len(test_containers) == 0, "Containers not cleaned up properly"
        print("✓ Cleanup verified after simulated failure")
