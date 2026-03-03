"""Unit tests for LLM service using LiteLLM."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simpa.llm.service import LLMService


@pytest.fixture(autouse=True)
def clear_llm_cache():
    """Clear LLM cache before each test to ensure isolation."""
    # Remove cache database file if it exists
    cache_path = "./llm_cache.db"
    if os.path.exists(cache_path):
        os.remove(cache_path)
    yield
    # Cleanup after test
    if os.path.exists(cache_path):
        os.remove(cache_path)


def mock_llm_settings(mock_settings, model="ollama/llama3.2"):
    """Helper to configure LLM settings for LiteLLM."""
    mock_settings.llm_model = model
    mock_settings.llm_temperature = 0.7
    mock_settings.openai_api_key = "test-openai-key"
    mock_settings.anthropic_api_key = "test-anthropic-key"
    mock_settings.llm_cache_enabled = False
    mock_settings.llm_cache_db_path = "./test_llm_cache.db"


class TestLLMServiceInit:
    """Test LLMService initialization with LiteLLM."""

    def test_init_with_model(self):
        """Test initialization with model name."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "ollama/llama3.2"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            assert service.model == "ollama/llama3.2"
            assert service.temperature == 0.7

    def test_init_with_openai_model(self):
        """Test initialization with OpenAI model format."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "gpt-4"
            mock_settings.llm_temperature = 0.5
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            assert service.model == "gpt-4"
            assert service.temperature == 0.5

    def test_init_with_anthropic_model(self):
        """Test initialization with Anthropic model format."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "claude-3-opus-20240229"
            mock_settings.llm_temperature = 0.3
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            assert service.model == "claude-3-opus-20240229"


@pytest.mark.asyncio
class TestLLMServiceComplete:
    """Test the complete method using LiteLLM."""

    async def test_complete_with_litellm(self):
        """Test completion with LiteLLM (any provider)."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "ollama/llama3.2"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            # Mock LiteLLM's acompletion
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Refined prompt text"))
            ]

            with patch("simpa.llm.service.litellm.acompletion", return_value=mock_response):
                result = await service.complete(
                    system_prompt="You are a helpful assistant",
                    user_prompt="Refine this: write a function",
                )

            assert result == "Refined prompt text"

    async def test_complete_with_openai_model(self):
        """Test completion with OpenAI model via LiteLLM."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "gpt-4"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="GPT-4 refined output"))
            ]

            with patch("simpa.llm.service.litellm.acompletion", return_value=mock_response) as mock_acompletion:
                result = await service.complete("system", "user prompt")

                # Verify LiteLLM was called with correct model
                mock_acompletion.assert_called_once()
                call_kwargs = mock_acompletion.call_args.kwargs
                assert call_kwargs["model"] == "gpt-4"
                assert call_kwargs["temperature"] == 0.7

            assert result == "GPT-4 refined output"

    async def test_complete_with_anthropic_model(self):
        """Test completion with Anthropic model via LiteLLM."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "claude-3-sonnet"
            mock_settings.llm_temperature = 0.5
            mock_settings.llm_cache_enabled = False

            service = LLMService()
            
            # Ensure cache is empty
            service._cache.clear_all()

            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Claude refined output"))
            ]

            with patch("simpa.llm.service.litellm.acompletion", return_value=mock_response) as mock_acompletion:
                result = await service.complete("system", "user")

                # Verify LiteLLM was called (not from cache)
                assert mock_acompletion.called
                
            assert result == "Claude refined output"

    async def test_complete_empty_response(self):
        """Test handling empty response from LiteLLM."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "gpt-4"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()
            
            # Ensure cache is empty
            service._cache.clear_all()

            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content=None))  # Empty content
            ]

            with patch("simpa.llm.service.litellm.acompletion", return_value=mock_response) as mock_acompletion:
                result = await service.complete("system", "user")

                # Verify LiteLLM was called (not from cache)
                assert mock_acompletion.called

            assert result == ""  # Should return empty string

    async def test_complete_cache_hit(self):
        """Test that cached responses are returned without calling LiteLLM."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "ollama/llama3.2"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = True

            service = LLMService()

            # Pre-populate cache
            service._cache.set("system prompt", "user prompt", "Cached response")

            with patch("simpa.llm.service.litellm.acompletion") as mock_acompletion:
                # Should return cached value without calling LiteLLM
                result = await service.complete("system prompt", "user prompt")

                assert result == "Cached response"
                assert not mock_acompletion.called  # LiteLLM should NOT be called

    async def test_complete_with_azure_model(self):
        """Test completion with Azure model via LiteLLM."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "azure/gpt-4"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()
            service._cache.clear_all()  # Clear any cached entries

            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Azure GPT-4 output"))
            ]

            with patch("simpa.llm.service.litellm.acompletion", return_value=mock_response) as mock_acompletion:
                result = await service.complete("system", "user")

                assert mock_acompletion.called
                assert mock_acompletion.call_args.kwargs["model"] == "azure/gpt-4"

            assert result == "Azure GPT-4 output"


@pytest.mark.asyncio
class TestLLMServiceErrorHandling:
    """Test error handling with LiteLLM."""

    async def test_litellm_error_handling(self):
        """Test error when LiteLLM raises exception."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "ollama/llama3.2"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()
            service._cache.clear_all()  # Clear any cached entries

            # LiteLLM will raise exception without proper API keys
            with patch(
                "simpa.llm.service.litellm.acompletion",
                side_effect=Exception("API Error: connection failed")
            ):
                with pytest.raises(RuntimeError, match="LLM call failed"):
                    await service.complete("system", "user")


@pytest.mark.asyncio
class TestLLMServiceRetry:
    """Test retry behavior with LiteLLM."""

    async def test_complete_retries_on_failure(self):
        """Test that complete retries when LiteLLM fails."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_model = "ollama/llama3.2"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_cache_enabled = False

            service = LLMService()
            
            # Ensure cache is cleared
            service._cache.clear_all()

            # First call fails, second succeeds
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Success after retry"))
            ]

            with patch(
                "simpa.llm.service.litellm.acompletion", 
                side_effect=[
                    RuntimeError("Network error"),
                    mock_response,
                ]
            ) as mock_acompletion:
                result = await service.complete("system", "user")

                # Should be called twice due to retry
                assert mock_acompletion.call_count == 2
                assert result == "Success after retry"


@pytest.mark.asyncio
class TestLLMServiceClose:
    """Test service cleanup."""

    async def test_close_service(self):
        """Test closing service clears cache."""
        service = LLMService()
        
        # Pre-populate cache
        service._cache.set("sys", "user", "response")
        
        # Close should clear the cache
        service.close()
        
        # Verify stats show cleared cache
        stats = service.get_cache_stats()
        assert stats["entry_count"] == 0
