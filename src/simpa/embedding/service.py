"""Embedding service for generating text embeddings with LRU caching."""

import hashlib
import structlog
from collections import OrderedDict
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
    """Service for generating text embeddings with LRU caching."""

    def __init__(self) -> None:
        self.provider = settings.embedding_provider
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._client = None
        
        # Initialize cache
        self.cache_enabled = settings.embedding_cache_enabled
        self.cache_max_text_length = settings.embedding_cache_max_text_length
        self._cache = EmbeddingCache(max_size=settings.embedding_cache_max_size)

    def _compute_hash(self, text: str) -> str:
        """Compute hash for cache key."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def _get_client(self):
        """Lazy load the appropriate client."""
        if self._client is None:
            if self.provider == "openai":
                from openai import AsyncOpenAI

                if not settings.openai_api_key:
                    raise ValueError("OpenAI API key not configured")
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
            elif self.provider == "ollama":
                import httpx

                self._client = httpx.AsyncClient(base_url=settings.ollama_base_url)
        return self._client

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
        """Generate embedding for text with caching.

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

        # Generate embedding
        client = await self._get_client()
        embedding = None

        if self.provider == "openai":
            response = await client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.data[0].embedding

        elif self.provider == "ollama":
            response = await client.post(
                "/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["embedding"]

        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

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
        # Check cache first for all texts
        results = []
        to_compute = []
        
        for i, text in enumerate(texts):
            if self._should_cache(text):
                text_hash = self._compute_hash(text)
                cached = self._cache.get(text_hash)
                if cached is not None:
                    results.append((i, cached))
                    continue
            to_compute.append((i, text))
        
        # Sort by index for consistent ordering
        results = [None] * len(texts)
        
        # Compute embeddings for uncached texts
        for idx, text in to_compute:
            embedding = await self.embed(text)
            results[idx] = embedding
        
        # Get cached results
        for idx, text in enumerate(texts):
            if results[idx] is None:
                embedding = await self.embed(text)
                results[idx] = embedding
        
        return results

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.stats()

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        logger.info("embedding_cache_cleared")

    async def close(self) -> None:
        """Close the client connection."""
        if self._client and self.provider == "ollama":
            await self._client.aclose()
