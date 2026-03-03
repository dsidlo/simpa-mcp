"""SIMPA configuration management using Pydantic Settings."""

from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SIMPA service configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql://dsidlo@localhost:5432/simpa",
        description="PostgreSQL connection URL",
    )

    # Embedding
    embedding_provider: Literal["openai", "ollama"] = Field(
        default="ollama",
        description="Embedding service provider",
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Embedding model name",
    )
    embedding_dimensions: int = Field(
        default=768,
        description="Embedding vector dimensions",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key",
    )

    # Embedding Cache
    embedding_cache_enabled: bool = Field(
        default=True,
        description="Enable LRU cache for embeddings",
    )
    embedding_cache_max_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum entries in embedding cache",
    )
    embedding_cache_max_text_length: int = Field(
        default=10000,
        description="Maximum text length to cache",
    )

    # LLM
    llm_provider: Literal["openai", "anthropic", "ollama"] = Field(
        default="ollama",
        description="LLM service provider",
    )
    llm_model: str = Field(
        default="llama3.2",
        description="LLM model name",
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key",
    )

    # LLM Cache
    llm_cache_enabled: bool = Field(
        default=True,
        description="Enable LLM response caching",
    )
    llm_cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="LLM cache TTL in seconds",
    )
    llm_cache_max_entries: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum entries in LLM cache",
    )
    llm_cache_db_path: str = Field(
        default="./llm_cache.db",
        description="Path to LLM cache SQLite database",
    )

    # Fast-Path Hash Lookup
    hash_fast_path_enabled: bool = Field(
        default=True,
        description="Enable hash-based fast path for exact matches",
    )
    hash_fast_path_min_score: float = Field(
        default=4.0,
        ge=1.0,
        le=5.0,
        description="Minimum average score for hash fast path reuse",
    )

    # Conditional Refinement
    similarity_bypass_threshold: float = Field(
        default=0.95,
        ge=0.9,
        le=1.0,
        description="Cosine similarity threshold for bypassing LLM refinement",
    )
    similarity_bypass_min_score: float = Field(
        default=4.5,
        ge=1.0,
        le=5.0,
        description="Minimum score for high-similarity bypass",
    )

    # Sigmoid refinement parameters
    sigmoid_k: float = Field(
        default=1.5,
        description="Sigmoid steepness parameter",
    )
    sigmoid_mu: float = Field(
        default=3.0,
        description="Sigmoid midpoint (50% threshold)",
    )
    min_refinement_probability: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Minimum probability of refinement (exploration floor)",
    )

    # Vector search
    vector_search_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of similar prompts to retrieve",
    )
    vector_similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for vector matches",
    )

    # MCP Server
    mcp_transport: Literal["stdio", "sse"] = Field(
        default="stdio",
        description="MCP transport protocol",
    )
    mcp_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="MCP server port (for SSE transport)",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    json_logging: bool = Field(
        default=True,
        description="Enable structured JSON logging",
    )

    # Security
    max_prompt_length: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum prompt text length",
    )
    enable_pii_detection: bool = Field(
        default=True,
        description="Enable basic PII detection in prompts",
    )

    # Diff Saliency
    diff_saliency_enabled: bool = Field(
        default=True,
        description="Enable diff saliency filtering",
    )
    diff_saliency_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum saliency score for diffs to be stored",
    )
    diff_max_stored_per_request: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of diffs to store per request",
    )


# Global settings instance
settings = Settings()
