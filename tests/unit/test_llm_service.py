"""Unit tests for LLM service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simpa.llm.service import LLMService


def mock_llm_settings(mock_settings, openai_key="test-key", anthropic_key="test-key"):
    """Helper to add LLM settings to mock."""
    mock_settings.llm_temperature = 0.7
    mock_settings.openai_api_key = openai_key
    mock_settings.anthropic_api_key = anthropic_key
    mock_settings.ollama_base_url = "http://localhost:11434"
    mock_settings.llm_cache_enabled = False


class TestLLMServiceInit:
    """Test LLMService initialization."""

    def test_init_with_openai(self):
        """Test initialization with OpenAI provider."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4"
            mock_llm_settings(mock_settings)

            service = LLMService()

            assert service.provider == "openai"
            assert service.model == "gpt-4"
            assert service.temperature == 0.7

    def test_init_with_anthropic(self):
        """Test initialization with Anthropic provider."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_model = "claude-3-sonnet"
            mock_llm_settings(mock_settings)

            service = LLMService()

            assert service.provider == "anthropic"
            assert service.model == "claude-3-sonnet"

    def test_init_with_ollama(self):
        """Test initialization with Ollama provider."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.llm_model = "llama3.2"
            mock_llm_settings(mock_settings)

            service = LLMService()

            assert service.provider == "ollama"
            assert service.model == "llama3.2"


@pytest.mark.asyncio
class TestLLMServiceComplete:
    """Test the complete method with different providers."""

    async def test_complete_with_openai(self):
        """Test completion with OpenAI."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            # Mock OpenAI client
            mock_message = MagicMock()
            mock_message.content = "Refined prompt text"

            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=mock_message)]

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            service._client = mock_client

            result = await service.complete(
                system_prompt="You are a helpful assistant",
                user_prompt="Refine this: write a function",
            )

            assert result == "Refined prompt text"

    async def test_complete_with_anthropic(self):
        """Test completion with Anthropic."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_model = "claude-3-sonnet"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            # Mock Anthropic response
            mock_content = MagicMock()
            mock_content.text = "Refined prompt result"

            mock_response = MagicMock()
            mock_response.content = [mock_content]

            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            service._client = mock_client

            result = await service.complete(
                system_prompt="You are Claude",
                user_prompt="Refine this prompt",
            )

            assert result == "Refined prompt result"

    async def test_complete_with_ollama(self):
        """Test completion with Ollama."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.llm_model = "llama3.2"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            # Mock httpx client
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "message": {"content": "LLaMA refined output"}
            }

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            service._client = mock_client

            result = await service.complete(
                system_prompt="System prompt",
                user_prompt="User prompt",
            )

            assert result == "LLaMA refined output"

    async def test_complete_empty_response_openai(self):
        """Test handling empty response from OpenAI."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            mock_message = MagicMock()
            mock_message.content = None  # Empty content

            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=mock_message)]

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            service._client = mock_client

            result = await service.complete("system", "user")

            assert result == ""  # Should return empty string

    async def test_complete_empty_response_anthropic(self):
        """Test handling empty response from Anthropic."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            mock_response = MagicMock()
            mock_response.content = []  # Empty content

            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            service._client = mock_client

            result = await service.complete("system", "user")

            assert result == ""

    async def test_complete_cache_hit(self):
        """Test that cached responses are returned."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Pre-populate cache
            service._cache.set("system", "user", "Cached response")

            # Should return cached value without calling client
            result = await service.complete("system", "user")

            assert result == "Cached response"

    async def test_complete_unknown_provider(self):
        """Test error on unknown provider."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "unknown"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            # Initialize client to bypass _get_client
            service._client = object()  # non-None but not a real client

            with pytest.raises(ValueError, match="Unknown LLM provider"):
                await service.complete("system", "user")


@pytest.mark.asyncio
class TestLLMServiceErrorHandling:
    """Test error handling for missing API keys."""

    async def test_openai_missing_key(self):
        """Test error when OpenAI key is missing."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4"
            mock_settings.llm_temperature = 0.7
            mock_settings.openai_api_key = None  # Key is missing
            mock_settings.anthropic_api_key = None
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            with pytest.raises(ValueError, match="OpenAI API key not configured"):
                await service._get_client()

    async def test_anthropic_missing_key(self):
        """Test error when Anthropic key is missing."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_model = "claude-3-sonnet"
            mock_settings.llm_temperature = 0.7
            mock_settings.openai_api_key = None
            mock_settings.anthropic_api_key = None  # Key is missing
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.llm_cache_enabled = False

            service = LLMService()

            with pytest.raises(ValueError, match="Anthropic API key not configured"):
                await service._get_client()


@pytest.mark.asyncio
class TestLLMServiceRetry:
    """Test retry behavior."""

    async def test_complete_retries_on_failure(self):
        """Test that complete retries on exception."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_llm_settings(mock_settings)

            service = LLMService()

            # Disable cache for this test
            service._cache.enabled = False

            mock_client = AsyncMock()
            mock_client.post.side_effect = [
                RuntimeError("Network error"),
                MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(return_value={"message": {"content": "Success"}}),
                ),
            ]
            service._client = mock_client

            result = await service.complete("system", "user")

            assert result == "Success"


@pytest.mark.asyncio
class TestLLMServiceClose:
    """Test service cleanup."""

    async def test_close_ollama(self):
        """Test closing Ollama client."""
        with patch("simpa.llm.service.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_llm_settings(mock_settings)

            service = LLMService()
            mock_client = AsyncMock()
            service._client = mock_client

            await service.close()

            mock_client.aclose.assert_called_once()

    async def test_close_no_client(self):
        """Test close when client not initialized."""
        service = LLMService()
        service._client = None

        # Should not raise
        await service.close()
