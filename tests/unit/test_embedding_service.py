"""Unit tests for embedding service using LiteLLM."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simpa.embedding.service import EmbeddingService


@pytest.fixture(autouse=True)
def patch_logger():
    """Mock logger to support trace level."""
    with patch("simpa.embedding.service.logger") as mock_logger:
        mock_logger.trace = MagicMock()
        mock_logger.debug = MagicMock()
        mock_logger.info = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.error = MagicMock()
        yield mock_logger


def mock_cache_settings(mock_settings):
    """Helper to add cache settings to mock."""
    mock_settings.embedding_cache_enabled = False  # Disable cache for most tests
    mock_settings.embedding_cache_max_text_length = 10000


class TestEmbeddingServiceInit:
    """Test EmbeddingService initialization with LiteLLM."""

    def test_init_with_ollama_model(self):
        """Test initialization with Ollama provider."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # LiteLLM format: provider/model
            assert service.model == "ollama/nomic-embed-text"
            assert service.dimensions == 768

    def test_init_with_openai_model(self):
        """Test initialization with OpenAI provider."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.embedding_model = "text-embedding-3-small"
            mock_settings.embedding_dimensions = 1536
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            assert service.model == "openai/text-embedding-3-small"
            assert service.dimensions == 1536


@pytest.mark.asyncio
class TestEmbeddingServiceEmbed:
    """Test the embed method using LiteLLM."""

    async def test_embed_with_litellm(self):
        """Test embedding generation using LiteLLM."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Mock LiteLLM's aembedding
            mock_response = MagicMock()
            mock_response.data = [{"embedding": [0.1] * 768}]

            with patch(
                "simpa.embedding.service.litellm.aembedding",
                return_value=mock_response
            ) as mock_aembedding:
                result = await service.embed("Test text")

                # Verify LiteLLM was called correctly
                mock_aembedding.assert_called_once()
                call_kwargs = mock_aembedding.call_args.kwargs
                assert call_kwargs["model"] == "ollama/nomic-embed-text"
                assert call_kwargs["input"] == "Test text"
                assert call_kwargs["dimensions"] == 768

            assert len(result) == 768
            assert result[0] == 0.1

    async def test_embed_with_openai(self):
        """Test embedding generation with OpenAI via LiteLLM."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.embedding_model = "text-embedding-3-small"
            mock_settings.embedding_dimensions = 1536
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            mock_response = MagicMock()
            mock_response.data = [{"embedding": [0.2] * 1536}]

            with patch(
                "simpa.embedding.service.litellm.aembedding",
                return_value=mock_response
            ) as mock_aembedding:
                result = await service.embed("Test text")

                # Verify OpenAI model format
                assert mock_aembedding.call_args.kwargs["model"] == "openai/text-embedding-3-small"

            assert len(result) == 1536
            assert result[0] == 0.2

    async def test_embed_dimension_mismatch_warning(self):
        """Test warning when embedding dimensions don't match expected."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Return different dimensions than expected
            mock_response = MagicMock()
            mock_response.data = [{"embedding": [0.1] * 512}]  # Only 512 dimensions

            with patch(
                "simpa.embedding.service.litellm.aembedding",
                return_value=mock_response
            ):
                with pytest.warns(UserWarning, match="dimension"):
                    result = await service.embed("Test")

            assert len(result) == 512  # Returns actual dimensions


@pytest.mark.asyncio
class TestEmbeddingServiceEmbedBatch:
    """Test batch embedding generation using LiteLLM."""

    async def test_embed_batch(self):
        """Test batch embedding processes sequentially."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Mock LiteLLM to return different embeddings for each call
            responses = [
                MagicMock(data=[{"embedding": [0.1] * 768}]),
                MagicMock(data=[{"embedding": [0.2] * 768}]),
                MagicMock(data=[{"embedding": [0.3] * 768}]),
            ]

            with patch(
                "simpa.embedding.service.litellm.aembedding",
                side_effect=responses
            ) as mock_aembedding:
                texts = ["Text 1", "Text 2", "Text 3"]
                results = await service.embed_batch(texts)

                assert len(results) == 3
                assert results[0][0] == 0.1
                assert results[1][0] == 0.2
                assert results[2][0] == 0.3
                assert mock_aembedding.call_count == 3

    async def test_embed_batch_empty(self):
        """Test batch embedding with empty list."""
        service = EmbeddingService()

        with patch("simpa.embedding.service.litellm.aembedding") as mock_aembedding:
            results = await service.embed_batch([])

            assert results == []
            mock_aembedding.assert_not_called()


@pytest.mark.asyncio
class TestEmbeddingServiceRetry:
    """Test retry behavior on failures using LiteLLM."""

    async def test_embed_retries_on_failure(self):
        """Test that embed retries when LiteLLM fails."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_model = "nomic-embed-text"
            mock_settings.embedding_dimensions = 768
            mock_cache_settings(mock_settings)

            service = EmbeddingService()

            # Fail twice, succeed on third
            with patch(
                "simpa.embedding.service.litellm.aembedding",
                side_effect=[
                    RuntimeError("Connection error"),
                    RuntimeError("Connection error"),
                    MagicMock(data=[{"embedding": [0.1] * 768}]),
                ]
            ) as mock_aembedding:
                result = await service.embed("Test")

                # Should have been called 3 times due to retry
                assert mock_aembedding.call_count == 3
                assert len(result) == 768


class TestEmbeddingServiceClose:
    """Test service cleanup - no client to close with LiteLLM."""

    def test_close_is_noop(self):
        """Test close with LiteLLM (no-op, stateless)."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_cache_enabled = True
            mock_settings.embedding_cache_max_size = 1000
            mock_settings.embedding_cache_max_text_length = 10000

            service = EmbeddingService()

            # Should not raise - LiteLLM is stateless
            service.close()

    def test_close_clears_cache(self):
        """Test close clears the embedding cache."""
        with patch("simpa.embedding.service.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.embedding_cache_enabled = True
            mock_settings.embedding_cache_max_size = 1000
            mock_settings.embedding_cache_max_text_length = 10000

            service = EmbeddingService()

            # Add something to cache
            service._cache.set("hash123", [0.1] * 768)
            assert service._cache.stats()["size"] == 1

            # Close should clear
            service.close()
            assert service._cache.stats()["size"] == 0
