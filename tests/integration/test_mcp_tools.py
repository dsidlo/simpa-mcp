"""Integration tests for FastMCP tool handlers."""

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastmcp import Context
from pydantic import ValidationError

from simpa.mcp_server import (
    RefinePromptRequest,
    RefinePromptResponse,
    UpdatePromptResultsRequest,
    UpdatePromptResultsResponse,
    health_check,
    refine_prompt,
    update_prompt_results,
)
from simpa.db.models import RefinedPrompt
from simpa.db.repository import PromptHistoryRepository, RefinedPromptRepository


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestRefinePromptTool:
    """Integration tests for the refine_prompt MCP tool."""

    async def test_reuse_existing_prompt(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        high_score_prompt: RefinedPrompt,
        sample_embedding: list[float],
    ):
        """Test reusing an existing high-quality prompt."""
        # Mock embedding service - use same embedding as the fixture
        mock_context.request_context.lifespan_context[
            "embedding_service"
        ].embed.return_value = sample_embedding
        
        # Request
        request = RefinePromptRequest(
            original_prompt="Write a Python function",
            agent_type=high_score_prompt.agent_type,
            main_language="python",
        )
        
        # Patch random to force reuse (return value above probability)
        with patch("simpa.prompts.selector.random.random", return_value=0.95):
            response = await refine_prompt(request, mock_context)
        
        assert isinstance(response, RefinePromptResponse)
        assert response.action == "reuse"
        assert response.prompt_key == str(high_score_prompt.prompt_key)
        assert response.refined_prompt == high_score_prompt.refined_prompt
        assert response.average_score == high_score_prompt.average_score
        assert response.usage_count == high_score_prompt.usage_count

    async def test_create_new_prompt(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test creating a new prompt when no similar prompts exist."""
        # Mock embedding service - use different embedding pattern to avoid matching
        mock_embedding = [i % 2 for i in range(768)]  # Alternating 0, 1 pattern
        mock_context.request_context.lifespan_context[
            "embedding_service"
        ].embed.return_value = mock_embedding
        
        # Mock LLM service
        refined_text = "This is a refined prompt with better instructions."
        mock_context.request_context.lifespan_context[
            "llm_service"
        ].complete.return_value = refined_text
        
        # Request
        request = RefinePromptRequest(
            original_prompt="Write a function to handle API requests",
            agent_type="developer",
            main_language="python",
        )
        
        response = await refine_prompt(request, mock_context)
        
        assert isinstance(response, RefinePromptResponse)
        assert response.action in ("new", "refine")
        assert response.refined_prompt == refined_text
        assert response.average_score in (None, 0.0)  # New prompt has no score
        assert response.usage_count in (None, 0)  # New prompt has no usage

    async def test_refinement_error_handling(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test error handling when LLM service fails."""
        mock_emedding = [0.1] * 768
        mock_context.request_context.lifespan_context[
            "embedding_service"
        ].embed.return_value = mock_emedding
        
        # Make LLM service fail
        mock_context.request_context.lifespan_context[
            "llm_service"
        ].complete.side_effect = Exception("LLM API error")
        
        request = RefinePromptRequest(
            original_prompt="Write a test function",
            agent_type="developer",
            main_language="python",
        )
        
        # Should raise the exception (to be caught by MCP framework)
        with pytest.raises(Exception, match="LLM API error"):
            await refine_prompt(request, mock_context)

    async def test_invalid_agent_type(
        self,
        db_session,
        mock_context: Context,
    ):
        """Test validation of empty agent type."""
        # Pydantic validation should catch empty agent_type
        with pytest.raises(ValidationError) as exc_info:
            RefinePromptRequest(
                original_prompt="Write a function",
                agent_type="",  # Empty - should fail validation
                main_language="python",
            )
        
        assert "agent_type" in str(exc_info.value).lower()

    async def test_invalid_prompt_length(
        self,
        db_session,
        mock_context: Context,
    ):
        """Test validation of prompt length constraints."""
        with pytest.raises(ValidationError) as exc_info:
            RefinePromptRequest(
                original_prompt="Short",  # Less than min_length=10
                agent_type="developer",
                main_language="python",
            )
        
        assert "at least" in str(exc_info.value).lower() or "10" in str(exc_info.value)

    async def test_pii_detection(
        self,
        db_session,
        mock_context: Context,
    ):
        """Test PII detection in prompt."""
        with patch("simpa.mcp_server.settings.enable_pii_detection", True):
            with pytest.raises((ValueError, ValidationError)) as exc_info:
                RefinePromptRequest(
                    original_prompt="My SSN is 123-45-6789 for reference",  # Contains SSN
                    agent_type="developer",
                    main_language="python",
                )
            
            assert "pii" in str(exc_info.value).lower()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestUpdatePromptResultsTool:
    """Integration tests for the update_prompt_results MCP tool."""

    async def test_update_prompt_succeeded(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        sample_prompt: RefinedPrompt,
    ):
        """Test successful update of prompt results."""
        request = UpdatePromptResultsRequest(
            prompt_key=str(sample_prompt.prompt_key),
            action_score=4.5,
            lint_score=0.9,  # 0-1 scale, not 0-100
            test_passed=True,
            files_modified=["test.py", "main.py"],
            file_count=2,
        )
        
        response = await update_prompt_results(request, mock_context)
        
        assert isinstance(response, UpdatePromptResultsResponse)
        assert response.success is True
        # Verify response fields - the prompt was updated with these values
        assert response.usage_count >= 1  # Should be incremented
        assert response.average_score > 0  # Should have a score now
        
    async def test_update_prompt_failed(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        sample_prompt: RefinedPrompt,
    ):
        """Test update with failing test."""
        request = UpdatePromptResultsRequest(
            prompt_key=str(sample_prompt.prompt_key),
            action_score=3.0,
            test_passed=False,
        )
        
        response = await update_prompt_results(request, mock_context)
        
        assert response.success is True  # Update succeeded
        assert response.usage_count >= 1  # Usage incremented even on failure
        assert response.average_score == pytest.approx(3.0, abs=0.1)  # Score recorded
        
    async def test_invalid_prompt_key_format(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test handling of invalid prompt key format - Pydantic validates UUID."""
        # Pydantic validates UUID format at model creation
        with pytest.raises(ValidationError) as exc_info:
            UpdatePromptResultsRequest(
                prompt_key="invalid-uuid",
                action_score=4.0,
            )
        
        assert "uuid" in str(exc_info.value).lower() or "prompt_key" in str(exc_info.value).lower()

    async def test_update_score_out_of_range_high(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        sample_prompt: RefinedPrompt,
    ):
        """Test update with score > 5.0."""
        with pytest.raises(ValueError) as exc_info:
            UpdatePromptResultsRequest(
                prompt_key=str(sample_prompt.prompt_key),
                action_score=6.0,  # Above max of 5.0
            )
        
        error_str = str(exc_info.value).lower()
        assert "5.0" in str(exc_info.value) or "less than or equal" in error_str or "at most" in error_str

    async def test_update_score_out_of_range_low(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        sample_prompt: RefinedPrompt,
    ):
        """Test update with score < 1.0."""
        with pytest.raises(ValueError) as exc_info:
            UpdatePromptResultsRequest(
                prompt_key=str(sample_prompt.prompt_key),
                action_score=0.5,  # Below min of 1.0
            )
        
        error_str = str(exc_info.value).lower()
        assert "1.0" in str(exc_info.value) or "greater than or equal" in error_str or "at least" in error_str

    async def test_multiple_updates_aggregate_correctly(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        sample_prompt: RefinedPrompt,
    ):
        """Test that multiple updates correctly aggregate statistics."""
        scores = [3.0, 4.0, 5.0, 2.0]
        
        for score in scores:
            request = UpdatePromptResultsRequest(
                prompt_key=str(sample_prompt.prompt_key),
                action_score=score,
                files_modified=["test.py"],
            )
            response = await update_prompt_results(request, mock_context)
            assert response.success is True
        
        # Verify final statistics
        # usage_count should be 4
        # average_score should be (3.0 + 4.0 + 5.0 + 2.0) / 4 = 3.5
        repo = RefinedPromptRepository(db_session)
        updated = await repo.get_by_id(sample_prompt.id)
        
        assert updated is not None
        assert updated.usage_count == 4
        assert updated.average_score == pytest.approx(3.5, abs=0.01)
        
        # Verify histogram
        assert updated.score_dist_2 == 1
        assert updated.score_dist_3 == 1
        assert updated.score_dist_4 == 1
        assert updated.score_dist_5 == 1


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestHealthCheckTool:
    """Tests for the health_check MCP tool."""

    async def test_health_check_success(self):
        """Test health check returns success."""
        response = await health_check()
        
        assert response.status == "healthy"
        assert response.timestamp is not None


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestPromptHistoryCreation:
    """Tests for prompt history creation via update_prompt_results."""

    async def test_history_record_created(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
        sample_prompt: RefinedPrompt,
    ):
        """Test that a history record is created on successful update."""
        request = UpdatePromptResultsRequest(
            prompt_key=str(sample_prompt.prompt_key),
            action_score=4.0,
            files_modified=["test.py"],
            test_passed=True,
        )
        
        response = await update_prompt_results(request, mock_context)
        assert response.success is True
        
        # Verify history record was created
        history_repo = PromptHistoryRepository(db_session)
        history_items = await history_repo.get_by_prompt_id(sample_prompt.id)
        
        assert len(history_items) == 1
        history = history_items[0]
        assert history.action_score == 4.0
        assert history.test_passed is True


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestEndToEndWorkflow:
    """End-to-end integration tests."""

    async def test_full_prompt_lifecycle(
        self,
        db_session,
        mock_context: Context,
        patch_async_session_local,
    ):
        """Test complete lifecycle: refine, reuse, update, history."""
        # Step 1: Create a new prompt
        mock_context.request_context.lifespan_context[
            "embedding_service"
        ].embed.return_value = [0.1] * 768
        
        mock_context.request_context.lifespan_context[
            "llm_service"
        ].complete.return_value = "Refined prompt text"
        
        request = RefinePromptRequest(
            original_prompt="Write a Python function to handle JSON",
            agent_type="developer",
            main_language="python",
        )
        
        response = await refine_prompt(request, mock_context)
        assert response.action in ("new", "refine")
        assert response.prompt_key is not None
        prompt_key = response.prompt_key
        
        # Step 2: Update results
        update_request = UpdatePromptResultsRequest(
            prompt_key=prompt_key,
            action_score=4.5,
            test_passed=True,
        )
        
        update_response = await update_prompt_results(update_request, mock_context)
        assert update_response.success is True
        
        # Step 3: Verify history
        history_repo = PromptHistoryRepository(db_session)
        history = await history_repo.get_by_prompt_key(prompt_key)
        assert len(history) == 1
        assert history[0].action_score == 4.5
