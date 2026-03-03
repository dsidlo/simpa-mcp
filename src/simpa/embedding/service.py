"""Embedding service for generating text embeddings with LRU caching using LiteLLM."""

import hashlib
import structlog
import warnings
from collections import OrderedDict
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import litellm
from simpa.config import settings

logger = structlog.get_logger()


class EmbeddingCache:
    """LRU cache for embeddings."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

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
            return embedding
        self._misses += 1
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
        elif len(self._cache) >= self.max_size:
            # Remove oldest entry
            self._cache.popitem(last=False)
        
        self._cache[text_hash] = embedding

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

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
        
        # Initialize cache
        self.cache_enabled = settings.embedding_cache_enabled
        self.cache_max_text_length = settings.embedding_cache_max_text_length
        self._cache = EmbeddingCache(max_size=settings.embedding_cache_max_size)

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
            return False
        if len(text) > self.cache_max_text_length:
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
        # Check cache
        cache_hit = False
        if self._should_cache(text):
            text_hash = self._compute_hash(text)
            cached = self._cache.get(text_hash)
            if cached is not None:
                cache_hit = True
                logger.debug("embedding_cache_hit", text_length=len(text))
                return cached

        # Generate embedding using LiteLLM
        try:
            response = await litellm.aembedding(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )
            
            embedding = response.data[0].get("embedding", [])
            
        except Exception as e:
            logger.error("embedding_failed", error=str(e), model=self.model)
            raise RuntimeError(f"Embedding generation failed: {e}") from e

        # Validate embedding dimensions
        if len(embedding) != self.dimensions:
            warnings.warn(
                f"Embedding dimension mismatch: expected {self.dimensions}, got {len(embedding)}",
                UserWarning,
            )
            logger.warning(
                "embedding_dimension_mismatch",
                expected=self.dimensions,
                actual=len(embedding),
            )

        # Cache the result
        if not cache_hit and self._should_cache(text):
            text_hash = self._compute_hash(text)
            self._cache.set(text_hash, embedding)
            logger.debug("embedding_cached", text_length=len(text))

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        # Process individually (LiteLLM handles batching internally for supported providers)
        results = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
        return results

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.stats()

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        logger.info("embedding_cache_cleared")

    def close(self) -> None:
        """Close the service and cleanup resources."""
        self._cache.clear()
