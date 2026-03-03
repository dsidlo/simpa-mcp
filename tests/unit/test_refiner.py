"""Unit tests for prompt refiner."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from simpa.prompts.refiner import PromptRefiner, REFINEMENT_SYSTEM_PROMPT
from simpa.db.models import RefinedPrompt


@pytest.mark.asyncio
class TestPromptRefinerBuildContext:
    """Test the build_context method."""

    async def test_build_context_no_similar_prompts(self):
        """Test context building without similar prompts."""
        mock_repo = MagicMock()
        mock_embedding = AsyncMock()
        mock_llm = AsyncMock()

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        context = await refiner.build_context(
            original_prompt="Write a function",
            agent_type="developer",
            main_language="python",
            similar_prompts=[],
        )

        assert "Agent Type: developer" in context
        assert "Primary Language: python" in context
        assert "Write a function" in context
        assert "Similar Successful Prompts:" not in context

    async def test_build_context_with_similar_prompts(self):
        """Test context building with similar prompts."""
        mock_repo = MagicMock()
        mock_embedding = AsyncMock()
        mock_llm = AsyncMock()

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        mock_prompt = MagicMock(spec=RefinedPrompt)
        mock_prompt.average_score = 4.5
        mock_prompt.usage_count = 10
        mock_prompt.refined_prompt = "Refined: Write a Python function with type hints"

        context = await refiner.build_context(
            original_prompt="Write a function",
            agent_type="developer",
            main_language="python",
            similar_prompts=[mock_prompt],
        )

        assert "Similar Successful Prompts (" in context
        assert "Example 1 (Score: 4.50, Usage: 10):" in context
        assert "Refined: Write a Python function with type hints" in context

    async def test_build_context_limits_to_three_examples(self):
        """Test that only top 3 examples are included."""
        mock_repo = MagicMock()
        mock_embedding = AsyncMock()
        mock_llm = AsyncMock()

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        prompts = []
        for i in range(5):
            mock_prompt = MagicMock(spec=RefinedPrompt)
            mock_prompt.average_score = 4.0 - (i * 0.1)
            mock_prompt.usage_count = i + 1
            mock_prompt.refined_prompt = f"Refined {i}"
            prompts.append(mock_prompt)

        context = await refiner.build_context(
            original_prompt="Test",
            agent_type="test",
            main_language="python",
            similar_prompts=prompts,
        )

        # Should only have Example 1, 2, 3
        assert "Example 1" in context
        assert "Example 2" in context
        assert "Example 3" in context
        assert "Example 4" not in context
        assert "Example 5" not in context


@pytest.mark.asyncio
class TestPromptRefinerRefine:
    """Test the main refine method."""

    async def test_refine_reuses_existing_prompt(self):
        """Test reusing an existing high-quality prompt."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        mock_llm = AsyncMock()

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        mock_prompt = MagicMock(spec=RefinedPrompt)
        mock_prompt.id = 1
        mock_prompt.prompt_key = "test-key"
        mock_prompt.average_score = 4.5
        mock_prompt.usage_count = 10
        mock_prompt.refined_prompt = "Refined: Write a Python function"

        # Patch selector to return existing prompt and not refine
        with patch.object(refiner.selector, "select_best_prompt", return_value=mock_prompt):
            with patch.object(refiner.selector, "should_create_new_prompt", return_value=False):
                result = await refiner.refine(
                    original_prompt="Write a function",
                    agent_type="developer",
                    main_language="python",
                )

        assert result["source"] == "reused"
        assert result["prompt_key"] == "test-key"
        assert result["refined_prompt"] == "Refined: Write a Python function"
        assert result["average_score"] == 4.5
        assert result["usage_count"] == 10

    async def test_refine_creates_new_prompt(self):
        """Test creating a new prompt."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_repo.create = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "REFINED_PROMPT:\nNew refined prompt\nREASONING:\nImproved clarity"

        mock_new_prompt = MagicMock()
        mock_new_prompt.prompt_key = "new-key"
        mock_repo.create.return_value = mock_new_prompt

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        result = await refiner.refine(
            original_prompt="Write a function",
            agent_type="developer",
            main_language="python",
        )

        assert result["source"] == "new"
        assert "prompt_key" in result
        mock_repo.create.assert_called_once()

    async def test_refine_with_prior_refinement(self):
        """Test refining from an existing prompt."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_repo.create = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "REFINED_PROMPT:\nBetter prompt\nREASONING:\nEnhanced"

        mock_new_prompt = MagicMock()
        mock_new_prompt.prompt_key = "refined-key"
        mock_repo.create.return_value = mock_new_prompt

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        result = await refiner.refine(
            original_prompt="Write a function",
            agent_type="developer",
            main_language="python",
        )

        assert result["source"] == "new"
        assert "prompt_key" in result

    async def test_refine_embedding_composition(self):
        """Test that embedding text is composed correctly."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        mock_llm = AsyncMock()

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        mock_prompt = MagicMock(spec=RefinedPrompt)
        mock_prompt.id = 1
        mock_prompt.average_score = 4.5
        mock_prompt.usage_count = 10
        mock_prompt.refined_prompt = "Refined prompt"

        with patch.object(refiner.selector, "select_best_prompt", return_value=mock_prompt):
            with patch.object(refiner.selector, "should_create_new_prompt", return_value=False):
                await refiner.refine(
                    original_prompt="Write a function",
                    agent_type="developer",
                    main_language="python",
                )

        # Check that embed was called with composed text
        mock_embedding.embed.assert_called_once()
        call_args = mock_embedding.embed.call_args[0][0]
        assert "developer" in call_args
        assert "python" in call_args
        assert "Write a function" in call_args

    async def test_refine_strips_llm_output(self):
        """Test that REFINED_PROMPT section is extracted from LLM output."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_repo.create = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        llm_response = """REFINED_PROMPT:
Write a well-structured Python function with type hints and docstrings.

REASONING:
Added type hints for better code quality and docstrings for documentation."""

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = llm_response

        mock_new_prompt = MagicMock()
        mock_new_prompt.prompt_key = "test-key"
        mock_repo.create.return_value = mock_new_prompt

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        result = await refiner.refine(
            original_prompt="Write a function",
            agent_type="developer",
            main_language="python",
        )

        # Should extract just the refined prompt text
        assert "REFINED_PROMPT:" not in result["refined_prompt"]
        assert "REASONING:" not in result["refined_prompt"]
        assert "Write a well-structured Python function" in result["refined_prompt"]


@pytest.mark.asyncio
class TestPromptRefinerWithRepository:
    """Test with actual repository integration."""

    async def test_refine_uses_repository_find_similar(self):
        """Test that find_similar is called on repository."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_repo.create = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "REFINED_PROMPT:\nTest prompt"

        mock_new_prompt = MagicMock()
        mock_new_prompt.prompt_key = "test-key"
        mock_repo.create.return_value = mock_new_prompt

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        await refiner.refine(
            original_prompt="Test",
            agent_type="test",
            main_language="python",
        )

        mock_repo.find_similar.assert_called_once()
        call_kwargs = mock_repo.find_similar.call_args.kwargs
        assert "embedding" in call_kwargs
        assert call_kwargs["agent_type"] == "test"


@pytest.mark.asyncio
class TestPromptRefinerLLMContext:
    """Test LLM context preparation."""

    async def test_llm_called_with_system_prompt(self):
        """Test that LLM is called with proper system prompt."""
        mock_repo = MagicMock()
        mock_repo.find_similar = AsyncMock(return_value=[])
        mock_repo.create = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [0.1] * 768

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "REFINED_PROMPT:\nRefined"

        mock_new_prompt = MagicMock()
        mock_new_prompt.prompt_key = "test-key"
        mock_repo.create.return_value = mock_new_prompt

        refiner = PromptRefiner(mock_repo, mock_embedding, mock_llm)

        await refiner.refine("Test", "test", "python")

        mock_llm.complete.assert_called_once()
        call_args = mock_llm.complete.call_args.kwargs
        assert call_args["system_prompt"] == REFINEMENT_SYSTEM_PROMPT
