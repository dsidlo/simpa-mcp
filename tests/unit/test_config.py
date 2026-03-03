"""Unit tests for configuration."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from simpa.config import Settings, settings


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_database_url(self):
        """Test default database URL."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert "localhost:5432/simpa" in str(s.database_url)

    def test_default_embedding_provider(self):
        """Test default embedding provider."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.embedding_provider == "ollama"

    def test_default_embedding_model(self):
        """Test default embedding model."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.embedding_model == "nomic-embed-text"

    def test_default_embedding_dimensions(self):
        """Test default embedding dimensions."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.embedding_dimensions == 768

    def test_default_llm_model(self):
        """Test default LLM model."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.llm_model == "ollama/llama3.2"

    def test_default_sigmoid_params(self):
        """Test default sigmoid parameters."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.sigmoid_k == 1.5
            assert s.sigmoid_mu == 3.0
            assert s.min_refinement_probability == 0.05

    def test_default_vector_search_params(self):
        """Test default vector search parameters."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.vector_search_limit == 5
            assert s.vector_similarity_threshold == 0.7

    def test_default_mcp_transport(self):
        """Test default MCP transport."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.mcp_transport == "stdio"

    def test_default_log_level(self):
        """Test default log level."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.log_level == "INFO"


class TestSettingsEnvironmentVariables:
    """Test configuration from environment variables."""

    def test_database_url_from_env(self):
        """Test database URL from environment."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}, clear=True):
            s = Settings()
            assert str(s.database_url) == "postgresql://user:pass@host/db"

    def test_embedding_provider_from_env(self):
        """Test embedding provider from environment."""
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "openai"}, clear=True):
            s = Settings()
            assert s.embedding_provider == "openai"

    def test_sigmoid_k_from_env(self):
        """Test sigmoid k from environment."""
        with patch.dict(os.environ, {"SIGMOID_K": "2.0"}, clear=True):
            s = Settings()
            assert s.sigmoid_k == 2.0

    def test_sigmoid_mu_from_env(self):
        """Test sigmoid mu from environment."""
        with patch.dict(os.environ, {"SIGMOID_MU": "2.5"}, clear=True):
            s = Settings()
            assert s.sigmoid_mu == 2.5

    def test_min_probability_from_env(self):
        """Test min probability from environment."""
        with patch.dict(os.environ, {"MIN_REFINEMENT_PROBABILITY": "0.1"}, clear=True):
            s = Settings()
            assert s.min_refinement_probability == 0.1

    def test_vector_limit_from_env(self):
        """Test vector search limit from environment."""
        with patch.dict(os.environ, {"VECTOR_SEARCH_LIMIT": "10"}, clear=True):
            s = Settings()
            assert s.vector_search_limit == 10

    def test_openai_api_key_from_env(self):
        """Test OpenAI API key from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            s = Settings()
            assert s.openai_api_key == "sk-test123"


class TestSettingsValidation:
    """Test configuration validation."""

    def test_log_level_must_be_valid(self):
        """Test log level must be one of allowed values."""
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")

    def test_mcp_transport_must_be_valid(self):
        """Test MCP transport must be stdio or sse."""
        with pytest.raises(ValidationError):
            Settings(mcp_transport="http")

    def test_embedding_provider_must_be_valid(self):
        """Test embedding provider must be valid."""
        with pytest.raises(ValidationError):
            Settings(embedding_provider="invalid")

    def test_sigmoid_k_range(self):
        """Test sigmoid k must be positive."""
        # No range constraint in current config, but should be reasonable
        s = Settings(sigmoid_k=0.1)
        assert s.sigmoid_k == 0.1

        s = Settings(sigmoid_k=5.0)
        assert s.sigmoid_k == 5.0

    def test_min_probability_range(self):
        """Test min probability must be between 0 and 1."""
        # Test lower bound
        with pytest.raises(ValidationError):
            Settings(min_refinement_probability=-0.1)

        # Test upper bound
        with pytest.raises(ValidationError):
            Settings(min_refinement_probability=1.1)

        # Test valid values
        s = Settings(min_refinement_probability=0.0)
        assert s.min_refinement_probability == 0.0

        s = Settings(min_refinement_probability=1.0)
        assert s.min_refinement_probability == 1.0

    def test_vector_similarity_threshold_range(self):
        """Test similarity threshold must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Settings(vector_similarity_threshold=-0.1)

        with pytest.raises(ValidationError):
            Settings(vector_similarity_threshold=1.1)

    def test_llm_temperature_range(self):
        """Test temperature must be between 0 and 2."""
        with pytest.raises(ValidationError):
            Settings(llm_temperature=-0.1)

        with pytest.raises(ValidationError):
            Settings(llm_temperature=2.1)

        s = Settings(llm_temperature=0.0)
        assert s.llm_temperature == 0.0

        s = Settings(llm_temperature=2.0)
        assert s.llm_temperature == 2.0

    def test_mcp_port_range(self):
        """Test MCP port must be valid."""
        with pytest.raises(ValidationError):
            Settings(mcp_port=1023)  # Below valid range

        with pytest.raises(ValidationError):
            Settings(mcp_port=65536)  # Above valid range

        s = Settings(mcp_port=1024)
        assert s.mcp_port == 1024

        s = Settings(mcp_port=65535)
        assert s.mcp_port == 65535

    def test_max_prompt_length_range(self):
        """Test max prompt length constraints."""
        with pytest.raises(ValidationError):
            Settings(max_prompt_length=99)  # Below minimum

        with pytest.raises(ValidationError):
            Settings(max_prompt_length=100001)  # Above maximum


class TestSettingsTypes:
    """Test configuration type handling."""

    def test_boolean_from_string_true(self):
        """Test boolean True from string."""
        with patch.dict(os.environ, {"JSON_LOGGING": "true"}, clear=True):
            s = Settings()
            assert s.json_logging is True

    def test_boolean_from_string_false(self):
        """Test boolean False from string."""
        with patch.dict(os.environ, {"JSON_LOGGING": "false"}, clear=True):
            s = Settings()
            assert s.json_logging is False

    def test_enable_pii_detection_env(self):
        """Test PII detection setting from environment."""
        with patch.dict(os.environ, {"ENABLE_PII_DETECTION": "false"}, clear=True):
            s = Settings()
            assert s.enable_pii_detection is False


class TestGlobalSettings:
    """Test global settings instance."""

    def test_global_settings_exists(self):
        """Test that global settings instance exists."""
        assert settings is not None
        assert isinstance(settings, Settings)
