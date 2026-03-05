"""Unit tests for BM25 hybrid search functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# Mock logger trace before importing modules
@pytest.fixture(autouse=True)
def mock_logger():
    """Mock logger to support trace level."""
    with patch("simpa.db.bm25_repository.logger") as mock_logger:
        mock_logger.trace = MagicMock()
        mock_logger.debug = MagicMock()
        mock_logger.info = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.error = MagicMock()
        yield mock_logger


class TestTokenCounting:
    """Test token counting utilities."""

    def test_count_tokens_simple(self):
        """Test token counting with simple text."""
        from simpa.utils.tokens import count_tokens
        
        text = "Hello world"
        count = count_tokens(text)
        
        assert count > 0
        assert count < 10  # Simple text should be low

    def test_count_prompt_tokens(self):
        """Test counting prompt tokens."""
        from simpa.utils.tokens import count_prompt_tokens
        
        original = "Write a function to sort a list"
        refined = "Write a type-hinted function to sort a list using Python"
        
        orig_toks, ref_toks, total = count_prompt_tokens(original, refined)
        
        assert orig_toks > 0
        assert ref_toks > 0
        assert total == orig_toks + ref_toks

    def test_count_tokens_empty(self):
        """Test token counting with empty text."""
        from simpa.utils.tokens import count_tokens
        
        assert count_tokens("") == 0
        assert count_tokens(None) == 0


class TestBM25Config:
    """Test BM25 configuration settings."""

    def test_bm25_settings_exist(self):
        """Verify BM25 settings are configurable."""
        from simpa.config import settings
        
        assert hasattr(settings, "bm25_search_enabled")
        assert hasattr(settings, "bm25_k1")
        assert hasattr(settings, "bm25_b")
        assert hasattr(settings, "bm25_limit")
        
        assert settings.bm25_k1 == 1.2
        assert settings.bm25_b == 0.75
        assert settings.bm25_limit == 5

    def test_hybrid_settings_exist(self):
        """Verify hybrid search settings."""
        from simpa.config import settings
        
        assert hasattr(settings, "hybrid_search_enabled")
        assert hasattr(settings, "llm_rerank_enabled")
        assert hasattr(settings, "llm_rerank_candidates")
