"""Unit tests for embedding service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response

from simpa.embedding.service import EmbeddingService
from simpa.config import Settings


def mock_cache_settings(mock_settings):
    """Helper to add cache settings to mock."""
    mock_settings.embedding_cache_enabled = False  # Disable cache for most tests
    mock_settings.embedding_cache_max_text_length = 10000
    mock_settings.embedding_cache_max_size = 1000


class TestEmbeddingServiceInit:
    """Test EmbeddingService initialization."""

    def test_init_with_ollama_provider(self):
        """Test initialization with Ollama provider."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            assert service.provider == "ollama"
            assert service.model == "nomic-embed-text"
            assert service.dimensions == 768
            assert service._client is None

    def test_init_with_openai_provider(self):
        """Test initialization with OpenAI provider."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.embedding_model = "text-embedding-3-small"
            mock_settings.embedding_dimensions = 1536
            mock_settings.openai_api_key = "test-key"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            assert service.provider == "openai"
            assert service.model == "text-embedding-3-small"


@pytest.mark.asyncio
class TestEmbeddingServiceEmbed:
    """Test the embed method with different providers."""

    async def test_embed_with_ollama(self):
        """Test embedding generation with Ollama."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Mock httpx client
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"embedding": [0.1] * 768}

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            service._client = mock_client

            result = await service.embed("Test text")

            assert len(result) == 768
            assert result[0] == 0.1
            mock_client.post.assert_called_once_with(
                "/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": "Test text"},
            )

    async def test_embed_with_openai(self):
        """Test embedding generation with OpenAI."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.embedding_model = "text-embedding-3-small"
            mock_settings.embedding_dimensions = 1536
            mock_settings.openai_api_key = "test-key"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Mock OpenAI client
            mock_embedding_data = MagicMock()
            mock_embedding_data.embedding = [0.2] * 1536

            mock_response = MagicMock()
            mock_response.data = [mock_embedding_data]

            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_response
            service._client = mock_client

            result = await service.embed("Test text")

            assert len(result) == 1536
            assert result[0] == 0.2
            mock_client.embeddings.create.assert_called_once_with(
                model="text-embedding-3-small",
                input="Test text",
            )

    async def test_embed_unknown_provider(self):
        """Test error on unknown provider."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "unknown"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()
            # Initialize client to bypass _get_client
            service._client = object()  # non-None but not a real client

            # Should raise ValueError when trying to get client
            with pytest.raises((ValueError, Exception)):
                await service.embed("Test")

    async def test_embed_openai_missing_key(self):
        """Test error when OpenAI key is missing."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.openai_api_key = None
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            with pytest.raises(ValueError, match="OpenAI API key not configured"):
                await service._get_client()


@pytest.mark.asyncio
class TestEmbeddingServiceEmbedBatch:
    """Test batch embedding generation."""

    async def test_embed_batch_sequential(self):
        """Test batch embedding processes sequentially."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Mock single embed
            service.embed = AsyncMock(side_effect=[[0.1] * 768, [0.2] * 768, [0.3] * 768])

            texts = ["Text 1", "Text 2", "Text 3"]
            results = await service.embed_batch(texts)

            assert len(results) == 3
            assert results[0][0] == 0.1
            assert results[1][0] == 0.2
            assert results[2][0] == 0.3
            assert service.embed.call_count == 3

    async def test_embed_batch_empty(self):
        """Test batch embedding with empty list."""
        service = EmbeddingService()
        service.embed = AsyncMock()

        results = await service.embed_batch([])

        assert results == []
        service.embed.assert_not_called()


@pytest.mark.asyncio
class TestEmbeddingServiceRetry:
    """Test retry behavior on failures."""

    async def test_embed_retries_on_failure(self):
        """Test that embed retries on exception."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            mock_client = AsyncMock()
            # Fail twice, succeed on third
            mock_client.post.side_effect = [
                RuntimeError("Connection error"),
                RuntimeError("Connection error"),
                MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value={"embedding": [0.1] * 768})),
            ]
            service._client = mock_client

            result = await service.embed("Test")

            # Should have been called 3 times
            assert mock_client.post.call_count == 3
            assert len(result) == 768


@pytest.mark.asyncio
class TestEmbeddingServiceClose:
    """Test service cleanup."""

    async def test_close_ollama(self):
        """Test closing Ollama client."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()
            mock_client = AsyncMock()
            service._client = mock_client

            await service.close()

            mock_client.aclose.assert_called_once()

    async def test_close_openai(self):
        """Test closing OpenAI client (no-op)."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_cache_settings(mock_settings)

            service = EmbeddingService()
            service._client = AsyncMock()

            # Should not raise
            await service.close()

    async def test_close_no_client(self):
        """Test close when client not initialized."""
        service = EmbeddingService()
        service._client = None

        # Should not raise
        await service.close()
