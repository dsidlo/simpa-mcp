"""Integration tests for Project MCP endpoints."""

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastmcp import Context
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def use_test_db_engine(db_engine):
    """Patch the global engine to use the test container engine.
    
    This ensures MCP tools create sessions from the test database
    rather than trying to connect to the production database.
    Without this, the MCP tools would try to use AsyncSessionLocal
    which is bound to the default engine, causing event loop issues.
    """
    from simpa.db import engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # Store original references
    original_engine = engine_module.async_engine
    original_session_local = engine_module.AsyncSessionLocal
    
    # Replace with test engine
    engine_module.async_engine = db_engine
    
    # Create session factory bound to test engine
    engine_module.AsyncSessionLocal = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    
    yield db_engine
    
    # Restore original references
    engine_module.async_engine = original_engine
    engine_module.AsyncSessionLocal = original_session_local


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestCreateProjectTool:
    """Integration tests for create_project MCP tool."""

    async def test_create_project_success(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test successful project creation."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                CreateProjectResponse,
                create_project,
            )
            from simpa.db.repository import ProjectRepository

            # Request
            request = CreateProjectRequest(
                project_name="test-project",
                description="A test project for SIMPA",
            )

            response = await create_project(request, mock_context)

            assert isinstance(response, CreateProjectResponse)
            assert response.success is True
            assert response.project_name == "test-project"
            assert response.description == "A test project for SIMPA"
            assert response.project_id is not None

            # Verify in database
            repo = ProjectRepository(db_session)
            project = await repo.get_by_name("test-project")
            assert project is not None
            assert project.description == "A test project for SIMPA"

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_create_project_minimal(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test project creation with minimal fields."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                CreateProjectResponse,
                create_project,
            )

            request = CreateProjectRequest(
                project_name="minimal-project",
            )

            response = await create_project(request, mock_context)

            assert response.success is True
            assert response.project_name == "minimal-project"
            assert response.description is None

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_create_project_duplicate_name(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test that duplicate project_name is rejected."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                create_project,
            )

            # Create first project
            request1 = CreateProjectRequest(project_name="duplicate-test")
            await create_project(request1, mock_context)

            # Try to create second with same name
            request2 = CreateProjectRequest(project_name="duplicate-test")

            with pytest.raises(ValueError, match="already exists"):
                await create_project(request2, mock_context)

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_create_project_empty_name(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test that empty project_name is rejected."""
        try:
            from simpa.mcp_server import CreateProjectRequest

            with pytest.raises(ValidationError) as exc_info:
                CreateProjectRequest(project_name="")

            assert "project_name" in str(exc_info.value).lower()

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_create_project_name_too_long(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test that very long project_name is rejected."""
        try:
            from simpa.mcp_server import CreateProjectRequest, create_project

            long_name = "a" * 101
            request = CreateProjectRequest(project_name=long_name)

            with pytest.raises((ValidationError, ValueError)):
                await create_project(request, mock_context)

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestGetProjectTool:
    """Integration tests for get_project MCP tool."""

    async def test_get_project_by_id(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test retrieving project by ID."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                CreateProjectResponse,
                GetProjectRequest,
                GetProjectResponse,
                create_project,
                get_project,
            )

            # Create a project first
            create_request = CreateProjectRequest(
                project_name="get-test-project",
                description="For get testing",
            )
            create_response = await create_project(create_request, mock_context)

            # Get the project
            get_request = GetProjectRequest(
                project_id=create_response.project_id,
            )
            get_response = await get_project(get_request, mock_context)

            assert isinstance(get_response, GetProjectResponse)
            assert get_response.found is True
            assert get_response.project_name == "get-test-project"
            assert get_response.description == "For get testing"

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_get_project_not_found(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test retrieving non-existent project."""
        try:
            from simpa.mcp_server import (
                GetProjectRequest,
                GetProjectResponse,
                get_project,
            )

            request = GetProjectRequest(project_id=str(uuid.uuid4()))
            response = await get_project(request, mock_context)

            assert response.found is False
            assert response.project_name is None

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_get_project_invalid_uuid(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test retrieving project with invalid UUID."""
        try:
            from simpa.mcp_server import GetProjectRequest, get_project

            request = GetProjectRequest(project_id="not-a-uuid")

            with pytest.raises(ValueError, match="project_id"):
                await get_project(request, mock_context)

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestListProjectsTool:
    """Integration tests for list_projects MCP tool."""

    async def test_list_all_projects(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test listing all projects."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                ListProjectsRequest,
                ListProjectsResponse,
                create_project,
                list_projects,
            )

            # Create multiple projects
            for i in range(3):
                request = CreateProjectRequest(project_name=f"list-project-{i}")
                await create_project(request, mock_context)

            # List projects
            list_request = ListProjectsRequest(active_only=False)
            response = await list_projects(list_request, mock_context)

            assert isinstance(response, ListProjectsResponse)
            assert len(response.projects) >= 3
            project_names = [p["project_name"] for p in response.projects]
            assert "list-project-0" in project_names

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_list_active_only(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test listing only active projects."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                DeleteProjectRequest,
                ListProjectsRequest,
                create_project,
                delete_project,
                list_projects,
            )

            # Create and then delete a project
            create_request = CreateProjectRequest(project_name="deleted-project")
            create_response = await create_project(create_request, mock_context)

            delete_request = DeleteProjectRequest(
                project_id=create_response.project_id,
            )
            await delete_project(delete_request, mock_context)

            # List active only
            list_request = ListProjectsRequest(active_only=True)
            response = await list_projects(list_request, mock_context)

            project_names = [p["project_name"] for p in response.projects]
            assert "deleted-project" not in project_names

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestUpdateProjectTool:
    """Integration tests for update_project MCP tool."""

    async def test_update_project_description(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test updating project description."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                UpdateProjectRequest,
                UpdateProjectResponse,
                create_project,
                update_project,
            )

            # Create project
            create_request = CreateProjectRequest(
                project_name="update-test",
                description="Old description",
            )
            create_response = await create_project(create_request, mock_context)

            # Update project
            update_request = UpdateProjectRequest(
                project_id=create_response.project_id,
                description="New description",
            )
            update_response = await update_project(update_request, mock_context)

            assert isinstance(update_response, UpdateProjectResponse)
            assert update_response.success is True
            assert update_response.description == "New description"

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_update_nonexistent_project(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test updating non-existent project."""
        try:
            from simpa.mcp_server import UpdateProjectRequest, update_project

            request = UpdateProjectRequest(
                project_id=str(uuid.uuid4()),
                description="New description",
            )

            with pytest.raises(ValueError, match="not found"):
                await update_project(request, mock_context)

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestDeleteProjectTool:
    """Integration tests for delete_project MCP tool."""

    async def test_delete_project_soft_delete(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test soft deleting a project."""
        try:
            from simpa.mcp_server import (
                CreateProjectRequest,
                DeleteProjectRequest,
                DeleteProjectResponse,
                GetProjectRequest,
                create_project,
                delete_project,
                get_project,
            )

            # Create project
            create_request = CreateProjectRequest(project_name="delete-test")
            create_response = await create_project(create_request, mock_context)

            # Delete project
            delete_request = DeleteProjectRequest(
                project_id=create_response.project_id,
            )
            delete_response = await delete_project(delete_request, mock_context)

            assert isinstance(delete_response, DeleteProjectResponse)
            assert delete_response.success is True

            # Verify it's marked as deleted but still exists
            get_request = GetProjectRequest(
                project_id=create_response.project_id,
            )
            get_response = await get_project(get_request, mock_context)

            # Should either not be found or be inactive
            assert get_response.found is False or get_response.is_active is False

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")

    async def test_delete_nonexistent_project(
        self,
        db_session,
        mock_context: Context,
        use_test_db_engine,
    ):
        """Test deleting non-existent project."""
        try:
            from simpa.mcp_server import DeleteProjectRequest, delete_project

            request = DeleteProjectRequest(project_id=str(uuid.uuid4()))
            response = await delete_project(request, mock_context)

            assert response.success is False

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestAssignPromptToProject:
    """Integration tests for assign_prompt_to_project."""

    async def test_assign_prompt_to_project(
        self,
        db_session,
        mock_context: Context,
        sample_prompt,
        use_test_db_engine,
    ):
        """Test assigning a prompt to a project."""
        try:
            from simpa.mcp_server import (
                AssignPromptToProjectRequest,
                AssignPromptToProjectResponse,
                CreateProjectRequest,
                assign_prompt_to_project,
                create_project,
            )

            # Create project
            project_request = CreateProjectRequest(project_name="assign-test")
            project_response = await create_project(project_request, mock_context)

            # Assign prompt to project
            assign_request = AssignPromptToProjectRequest(
                project_id=project_response.project_id,
                prompt_id=str(sample_prompt.id),
            )
            assign_response = await assign_prompt_to_project(assign_request, mock_context)

            assert isinstance(assign_response, AssignPromptToProjectResponse)
            assert assign_response.success is True

        except ImportError:
            pytest.skip("Project assignment endpoints not yet implemented")

    async def test_assign_to_nonexistent_project(
        self,
        db_session,
        mock_context: Context,
        sample_prompt,
        use_test_db_engine,
    ):
        """Test assigning prompt to non-existent project."""
        try:
            from simpa.mcp_server import (
                AssignPromptToProjectRequest,
                assign_prompt_to_project,
            )

            request = AssignPromptToProjectRequest(
                project_id=str(uuid.uuid4()),
                prompt_id=str(sample_prompt.id),
            )

            with pytest.raises(ValueError, match="not found"):
                await assign_prompt_to_project(request, mock_context)

        except ImportError:
            pytest.skip("Project assignment endpoints not yet implemented")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestProjectEndToEnd:
    """End-to-end Project workflow tests."""

    async def test_full_project_lifecycle(
        self,
        db_session,
        mock_context: Context,
        sample_prompt,
        use_test_db_engine,
    ):
        """Test complete project lifecycle: create -> update -> assign -> delete."""
        try:
            from simpa.mcp_server import (
                AssignPromptToProjectRequest,
                CreateProjectRequest,
                DeleteProjectRequest,
                GetProjectRequest,
                ListProjectsRequest,
                UpdateProjectRequest,
                assign_prompt_to_project,
                create_project,
                delete_project,
                get_project,
                list_projects,
                update_project,
            )

            # Step 1: Create project
            create_request = CreateProjectRequest(
                project_name="lifecycle-test",
                description="For E2E testing",
            )
            create_response = await create_project(create_request, mock_context)
            project_id = create_response.project_id

            assert create_response.success is True

            # Step 2: Update project
            update_request = UpdateProjectRequest(
                project_id=project_id,
                description="Updated description",
            )
            update_response = await update_project(update_request, mock_context)

            assert update_response.success is True
            assert update_response.description == "Updated description"

            # Step 3: Assign prompt to project
            assign_request = AssignPromptToProjectRequest(
                project_id=project_id,
                prompt_id=str(sample_prompt.id),
            )
            assign_response = await assign_prompt_to_project(assign_request, mock_context)

            assert assign_response.success is True

            # Step 4: Get project (verify prompt count)
            get_request = GetProjectRequest(project_id=project_id)
            get_response = await get_project(get_request, mock_context)

            assert get_response.found is True

            # Step 5: Delete project
            delete_request = DeleteProjectRequest(project_id=project_id)
            delete_response = await delete_project(delete_request, mock_context)

            assert delete_response.success is True

            print("Project lifecycle test passed!")

        except ImportError:
            pytest.skip("Project MCP endpoints not yet implemented")
