"""Integration tests for --project-id-required flag functionality."""

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastmcp import Context

from simpa.mcp_server import (
    RefinePromptRequest,
    RefinePromptResponse,
    UpdatePromptResultsRequest,
    UpdatePromptResultsResponse,
    create_project,
    get_project,
    list_projects,
    refine_prompt,
    update_prompt_results,
)
from simpa.db.models import Project, RefinedPrompt
from simpa.db.repository import PromptHistoryRepository, ProjectRepository, RefinedPromptRepository
from simpa.config import settings


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestProjectIdRequiredFlag:
    """Integration tests for --project-id-required flag behavior."""

    async def test_project_id_required_no_project_provided_no_projects_exist(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test that when --project-id-required is set and no projects exist, agent is guided to create one."""
        # Enable strict project mode
        original_require = settings.require_project_id
        settings.require_project_id = True
        
        try:
            # Mock embedding service
            mock_context.request_context.lifespan_context[
                "embedding_service"
            ].embed.return_value = [0.1] * 768
            
            # Request without project_id
            request = RefinePromptRequest(
                original_prompt="Write a Python function to sort a list",
                agent_type="developer",
                main_language="python",
            )
            
            response = await refine_prompt(request, mock_context)
            
            # Response should be an error with instructions
            assert isinstance(response, RefinePromptResponse)
            assert "ERROR:" in response.refined_prompt
            assert "no projects exist" in response.refined_prompt or "create a project" in response.refined_prompt.lower()
            assert response.action == "new"
            assert response.confidence_score == 0.0
            
        finally:
            settings.require_project_id = original_require

    async def test_project_id_required_no_project_provided_existing_projects(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test that when --project-id-required is set and projects exist, agent gets list to choose from."""
        # Enable strict project mode
        original_require = settings.require_project_id
        settings.require_project_id = True
        
        try:
            # Create some projects first
            project_repo = ProjectRepository(db_session)
            project1 = await project_repo.create(
                project_name="Web App",
                main_language="python",
                description="A web application project",
            )
            project2 = await project_repo.create(
                project_name="Mobile API",
                main_language="javascript",
                description="Mobile backend API",
            )
            await db_session.commit()
            
            # Mock embedding service
            mock_context.request_context.lifespan_context[
                "embedding_service"
            ].embed.return_value = [0.1] * 768
            
            # Request without project_id
            request = RefinePromptRequest(
                original_prompt="Write a Python function to sort a list",
                agent_type="developer",
                main_language="python",
            )
            
            response = await refine_prompt(request, mock_context)
            
            # Response should be an error with list of projects
            assert isinstance(response, RefinePromptResponse)
            assert "ERROR:" in response.refined_prompt
            assert "Web App" in response.refined_prompt or project1.project_name in response.refined_prompt
            assert "Mobile API" in response.refined_prompt or project2.project_name in response.refined_prompt
            assert response.action == "new"
            assert response.confidence_score == 0.0
            
        finally:
            settings.require_project_id = original_require

    async def test_project_id_required_with_project_provided(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test that when --project-id-required is set and project_id is provided, refinement works normally."""
        # Enable strict project mode
        original_require = settings.require_project_id
        settings.require_project_id = True
        
        try:
            # Create a project first
            project_repo = ProjectRepository(db_session)
            project = await project_repo.create(
                project_name="Test Project",
                main_language="python",
                description="Test project for prompt refinement",
            )
            await db_session.commit()
            
            # Mock embedding service
            mock_context.request_context.lifespan_context[
                "embedding_service"
            ].embed.return_value = [0.1] * 768
            
            # Mock LLM service
            mock_context.request_context.lifespan_context[
                "llm_service"
            ].complete.return_value = "Refined: Write a Python function that takes a list of integers and returns a sorted copy."
            
            # Request with project_id
            request = RefinePromptRequest(
                original_prompt="Write a Python function to sort a list",
                agent_type="developer",
                main_language="python",
                project_id=str(project.id),
            )
            
            response = await refine_prompt(request, mock_context)
            
            # Normal refinement should occur
            assert isinstance(response, RefinePromptResponse)
            assert "ERROR:" not in response.refined_prompt
            assert response.action in ("new", "refine")
            assert response.confidence_score != 0.0
            
            # Verify project_id was stored in the refined prompt
            prompt_repo = RefinedPromptRepository(db_session)
            prompt_uuid = uuid.UUID(response.prompt_key)
            stored_prompt = await prompt_repo.get_by_prompt_key(prompt_uuid)
            assert stored_prompt is not None
            assert stored_prompt.project_id == project.id
            
        finally:
            settings.require_project_id = original_require

    async def test_project_id_required_disabled_allows_anonymous_prompts(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test that when --project-id-required is NOT set, prompts can be created without project_id."""
        # Ensure strict mode is disabled
        original_require = settings.require_project_id
        settings.require_project_id = False
        
        try:
            # Mock embedding service
            mock_context.request_context.lifespan_context[
                "embedding_service"
            ].embed.return_value = [0.1] * 768
            
            # Mock LLM service
            mock_context.request_context.lifespan_context[
                "llm_service"
            ].complete.return_value = "Refined: Write a Python function that sorts a list."
            
            # Request without project_id
            request = RefinePromptRequest(
                original_prompt="Write a Python function to sort a list",
                agent_type="developer",
                main_language="python",
            )
            
            response = await refine_prompt(request, mock_context)
            
            # Refinement should succeed without error
            assert isinstance(response, RefinePromptResponse)
            assert "ERROR:" not in response.refined_prompt
            assert response.action in ("new", "refine")
            
            # Verify project_id is None in the refined prompt
            prompt_repo = RefinedPromptRepository(db_session)
            prompt_uuid = uuid.UUID(response.prompt_key)
            stored_prompt = await prompt_repo.get_by_prompt_key(prompt_uuid)
            assert stored_prompt is not None
            assert stored_prompt.project_id is None
            
        finally:
            settings.require_project_id = original_require


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestProjectIdInHistory:
    """Integration tests for project_id propagation to prompt_history."""

    async def test_history_inherits_project_from_prompt(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test that prompt_history records inherit project_id from their parent prompt."""
        # Create a project first
        project_repo = ProjectRepository(db_session)
        project = await project_repo.create(
            project_name="Web Dashboard",
            main_language="python",
            description="Web dashboard project",
        )
        await db_session.commit()
        
        # Mock services
        mock_context.request_context.lifespan_context[
            "embedding_service"
        ].embed.return_value = [0.1] * 768
        mock_context.request_context.lifespan_context[
            "llm_service"
        ].complete.return_value = "Refined: Create a Flask route."
        
        # Step 1: Refine a prompt with project_id
        refine_request = RefinePromptRequest(
            original_prompt="Create a Flask route",
            agent_type="developer",
            main_language="python",
            project_id=str(project.id),
        )
        
        refine_response = await refine_prompt(refine_request, mock_context)
        assert refine_response.action in ("new", "refine")
        prompt_key = refine_response.prompt_key
        
        # Step 2: Update results
        update_request = UpdatePromptResultsRequest(
            prompt_key=prompt_key,
            action_score=4.5,
            test_passed=True,
            files_modified=["app.py"],
        )
        
        update_response = await update_prompt_results(update_request, mock_context)
        assert update_response.success is True
        
        # Step 3: Verify history has project_id
        history_repo = PromptHistoryRepository(db_session)
        # Get the internal prompt_id from the prompt_key
        prompt_repo = RefinedPromptRepository(db_session)
        stored_prompt = await prompt_repo.get_by_prompt_key(uuid.UUID(prompt_key))
        assert stored_prompt is not None
        history_records = await history_repo.get_by_prompt_id(
            stored_prompt.id  # Use internal id, not prompt_key
        )
        assert len(history_records) == 1
        assert history_records[0].project_id == project.id

    async def test_history_without_project_when_prompt_has_no_project(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test that prompt_history records have no project_id when prompt doesn't have one."""
        # Ensure strict mode is disabled
        original_require = settings.require_project_id
        settings.require_project_id = False
        
        try:
            # Mock services
            mock_context.request_context.lifespan_context[
                "embedding_service"
            ].embed.return_value = [0.1] * 768
            mock_context.request_context.lifespan_context[
                "llm_service"
            ].complete.return_value = "Refined: Sort a list."
            
            # Step 1: Refine a prompt without project_id
            refine_request = RefinePromptRequest(
                original_prompt="Sort a list",
                agent_type="developer",
                main_language="python",
            )
            
            refine_response = await refine_prompt(refine_request, mock_context)
            assert refine_response.action in ("new", "refine")
            prompt_key = refine_response.prompt_key
            
            # Step 2: Update results
            update_request = UpdatePromptResultsRequest(
                prompt_key=prompt_key,
                action_score=4.0,
                test_passed=True,
            )
            
            update_response = await update_prompt_results(update_request, mock_context)
            assert update_response.success is True
            
            # Step 3: Verify history has no project_id
            history_repo = PromptHistoryRepository(db_session)
            # Get the internal prompt_id from the prompt_key
            prompt_repo = RefinedPromptRepository(db_session)
            stored_prompt = await prompt_repo.get_by_prompt_key(uuid.UUID(prompt_key))
            assert stored_prompt is not None
            history_records = await history_repo.get_by_prompt_id(
                stored_prompt.id  # Use internal id, not prompt_key
            )
            assert len(history_records) == 1
            assert history_records[0].project_id is None
            
        finally:
            settings.require_project_id = original_require


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestProjectIdRequiredEndToEnd:
    """End-to-end tests for project_id required workflow."""

    async def test_full_workflow_create_project_then_refine(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test the full workflow: create project, then refine with that project."""
        # Enable strict project mode
        original_require = settings.require_project_id
        settings.require_project_id = True
        
        try:
            # Step 1: Try to refine without project - should get error with project list
            mock_context.request_context.lifespan_context[
                "embedding_service"
            ].embed.return_value = [0.1] * 768
            
            refine_request = RefinePromptRequest(
                original_prompt="Create an API endpoint",
                agent_type="developer",
                main_language="python",
            )
            
            error_response = await refine_prompt(refine_request, mock_context)
            assert "ERROR:" in error_response.refined_prompt
            
            # Step 2: Create a new project
            from simpa.mcp_server import CreateProjectRequest
            create_request = CreateProjectRequest(
                project_name="APIService",
                main_language="python",
                description="REST API service project",
            )
            
            project_response = await create_project(create_request, mock_context)
            assert project_response.success is True
            project_id = project_response.project_id
            
            # Step 3: Now refine with the new project_id
            mock_context.request_context.lifespan_context[
                "llm_service"
            ].complete.return_value = "Refined: Create a FastAPI endpoint."
            
            refine_request_with_project = RefinePromptRequest(
                original_prompt="Create an API endpoint",
                agent_type="developer",
                main_language="python",
                project_id=project_id,
            )
            
            success_response = await refine_prompt(refine_request_with_project, mock_context)
            assert "ERROR:" not in success_response.refined_prompt
            assert success_response.action in ("new", "refine")
            
            # Verify the prompt is associated with the project
            prompt_repo = RefinedPromptRepository(db_session)
            prompt_uuid = uuid.UUID(success_response.prompt_key)
            stored_prompt = await prompt_repo.get_by_prompt_key(prompt_uuid)
            assert stored_prompt.project_id == uuid.UUID(project_id)
            
        finally:
            settings.require_project_id = original_require
