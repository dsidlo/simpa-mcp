"""Embedding service for generating text embeddings with LRU caching using LiteLLM."""

import hashlib
import warnings
from collections import OrderedDict

import litellm
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from simpa.config import settings
from simpa.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """LRU cache for embeddings."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        logger.debug("embedding_cache_initialized", max_size=max_size)

    def get(self, text_hash: str) -> list[float] | None:
        """Get cached embedding.
        
        Args:
            text_hash: Hash of the text
            
        Returns:
            Cached embedding or None
        """
        if text_hash in self._cache:
            # Move to end (most recently used)
            embedding = self._cache.pop(text_hash)
            self._cache[text_hash] = embedding
            self._hits += 1
            logger.debug("embedding_cache_hit", text_hash=text_hash[:16])
            return embedding
        self._misses += 1
        logger.debug("embedding_cache_miss", text_hash=text_hash[:16])
        return None

    def set(self, text_hash: str, embedding: list[float]) -> None:
        """Cache embedding.
        
        Args:
            text_hash: Hash of the text
            embedding: The embedding vector
        """
        if text_hash in self._cache:
            # Remove old entry
            del self._cache[text_hash]
            logger.debug("embedding_cache_updated", text_hash=text_hash[:16])
        elif len(self._cache) >= self.max_size:
            # Remove oldest entry
            removed_hash, _ = self._cache.popitem(last=False)
            logger.debug("embedding_cache_evicted", removed_hash=removed_hash[:16])
        
        self._cache[text_hash] = embedding
        logger.debug(
            "embedding_cache_set",
            text_hash=text_hash[:16],
            cache_size=len(self._cache),
        )

    def clear(self) -> None:
        """Clear all cached entries."""
        size_before = len(self._cache)
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("embedding_cache_cleared", entries_removed=size_before)

    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }


class EmbeddingService:
    """Service for generating text embeddings with LRU caching using LiteLLM."""

    def __init__(self) -> None:
        # LiteLLM model format: provider/model (e.g., "openai/text-embedding-3-small", "ollama/nomic-embed-text")
        self.model = f"{settings.embedding_provider}/{settings.embedding_model}"
        self.dimensions = settings.embedding_dimensions
        
        # Get Ollama base URL for embeddings if using ollama
        if settings.embedding_provider == "ollama":
            self.ollama_base_url = settings.ollama_base_url
            litellm.set_verbose = False
            logger.info(
                "embedding_service_initialized",
                provider=settings.embedding_provider,
                model=settings.embedding_model,
                ollama_base_url=self.ollama_base_url,
                dimensions=self.dimensions,
            )
        else:
            logger.info(
                "embedding_service_initialized",
                provider=settings.embedding_provider,
                model=settings.embedding_model,
                dimensions=self.dimensions,
            )
        
        # Initialize cache
        self.cache_enabled = settings.embedding_cache_enabled
        self.cache_max_text_length = settings.embedding_cache_max_text_length
        self._cache = EmbeddingCache(max_size=settings.embedding_cache_max_size)
        
        logger.debug(
            "embedding_cache_config",
            enabled=self.cache_enabled,
            max_text_length=self.cache_max_text_length,
            max_entries=settings.embedding_cache_max_size,
        )

    def _compute_hash(self, text: str) -> str:
        """Compute hash for cache key."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _should_cache(self, text: str) -> bool:
        """Determine if text should be cached.
        
        Args:
            text: Text to check
            
        Returns:
            True if should cache
        """
        if not self.cache_enabled:
            logger.debug("embedding_cache_skip_disabled")
            return False
        if len(text) > self.cache_max_text_length:
            logger.debug(
                "embedding_cache_skip_too_long",
                text_length=len(text),
                max_length=self.cache_max_text_length,
            )
            return False
        return True

    @retry(
        retry=retry_if_exception_type(RuntimeError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text with caching using LiteLLM.

        Args:
            text: Text to embed

        Returns:
            List of float values (embedding vector)
        """
        logger.debug("embedding_request", text_length=len(text), model=self.model)
        
        # Check cache
        cache_hit = False
        if self._should_cache(text):
            text_hash = self._compute_hash(text)
            cached = self._cache.get(text_hash)
            if cached is not None:
                cache_hit = True
                logger.info(
                    "embedding_cache_hit",
                    text_length=len(text),
                    text_hash=text_hash[:16],
                )
                return cached

        # Generate embedding using LiteLLM
        try:
            logger.debug("embedding_api_call", model=self.model, text_length=len(text))
            
            # For Ollama, pass base_url
            kwargs = {
                "model": self.model,
                "input": text,
                "dimensions": self.dimensions,
            }
            if settings.embedding_provider == "ollama":
                kwargs["api_base"] = self.ollama_base_url
            
            response = await litellm.aembedding(**kwargs)
            
            embedding = response.data[0].get("embedding", [])
            logger.debug(
                "embedding_api_success",
                model=self.model,
                text_length=len(text),
                embedding_dimensions=len(embedding),
            )
            
        except Exception as e:
            logger.error(
                "embedding_api_failed",
                error=str(e),
                model=self.model,
                text_length=len(text),
                exc_info=True,
            )
            raise RuntimeError(f"Embedding generation failed: {e}") from e

        # Validate embedding dimensions
        if len(embedding) != self.dimensions:
            logger.warning(
                "embedding_dimension_mismatch",
                expected=self.dimensions,
                actual=len(embedding),
                model=self.model,
            )
            warnings.warn(
                f"Embedding dimension mismatch: expected {self.dimensions}, got {len(embedding)}",
                UserWarning,
            )

        # Cache the result
        if not cache_hit and self._should_cache(text):
            text_hash = self._compute_hash(text)
            self._cache.set(text_hash, embedding)
            logger.debug(
                "embedding_cached",
                text_length=len(text),
                text_hash=text_hash[:16],
            )

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        logger.info("embedding_batch_request", count=len(texts))
        
        # Process individually (LiteLLM handles batching internally for supported providers)
        results = []
        for i, text in enumerate(texts):
            try:
                embedding = await self.embed(text)
                results.append(embedding)
            except Exception as e:
                logger.error(
                    "embedding_batch_item_failed",
                    index=i,
                    text_length=len(text),
                    error=str(e),
                )
                raise
        
        logger.info("embedding_batch_complete", count=len(results))
        return results

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        stats = self._cache.stats()
        logger.info("embedding_cache_stats", **stats)
        return stats

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    def close(self) -> None:
        """Close the service and cleanup resources."""
        logger.info("embedding_service_closing")
        self._cache.clear()
        logger.info("embedding_service_closed")
