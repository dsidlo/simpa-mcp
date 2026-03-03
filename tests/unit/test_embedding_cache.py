"""Unit tests for embedding LRU cache optimization."""
import pytest
from typing import Dict, Any, Optional, Tuple
from collections import OrderedDict


class MockLRUCache:
    """Mock implementation of LRU cache for embeddings."""
    
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.access_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'inserts': 0
        }
    
    def _generate_key(self, text: str, model: str = "embedding-model") -> str:
        """Generate cache key from text and model."""
        import hashlib
        key_string = f"{model}:{text}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, text: str, model: str = "embedding-model") -> Optional[Tuple]:
        """Get embedding from cache."""
        key = self._generate_key(text, model)
        
        if key not in self.cache:
            self.access_stats['misses'] += 1
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.access_stats['hits'] += 1
        return self.cache[key]
    
    def put(self, text: str, embedding: Tuple, model: str = "embedding-model"):
        """Store embedding in cache."""
        key = self._generate_key(text, model)
        
        if key in self.cache:
            # Update existing and move to end
            self.cache.move_to_end(key)
            self.cache[key] = embedding
            return
        
        # Evict if at capacity
        if len(self.cache) >= self.capacity:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.access_stats['evictions'] += 1
        
        self.cache[key] = embedding
        self.access_stats['inserts'] += 1
    
    def peek_oldest(self) -> Optional[Tuple[str, Any, Any]]:
        """Peek at oldest item without accessing it."""
        if not self.cache:
            return None
        key, value = next(iter(self.cache.items()))
        return (key, value)
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.access_stats['hits'] + self.access_stats['misses']
        hit_rate = self.access_stats['hits'] / total if total > 0 else 0.0
        return {
            **self.access_stats,
            'size': len(self.cache),
            'capacity': self.capacity,
            'hit_rate': hit_rate,
            'fill_rate': len(self.cache) / self.capacity
        }
    
    def clear(self):
        """Clear all cached items."""
        self.cache.clear()


class TestLRUCache:
    """Test suite for LRU cache functionality."""
    
    @pytest.fixture
    def lru_cache(self):
        return MockLRUCache(capacity=5)
    
    def test_empty_cache_returns_none(self, lru_cache):
        """Empty cache should return None on miss."""
        result = lru_cache.get("some text")
        assert result is None
        assert lru_cache.access_stats['misses'] == 1
    
    def test_put_and_get(self, lru_cache):
        """Should store and retrieve embeddings."""
        embedding = ([0.1, 0.2, 0.3], {"model": "test"})
        lru_cache.put("sample text", embedding)
        
        result = lru_cache.get("sample text")
        assert result == embedding
    
    def test_different_texts_different_keys(self, lru_cache):
        """Different texts should have different cache entries."""
        lru_cache.put("text A", ([1.0], {}))
        lru_cache.put("text B", ([2.0], {}))
        
        assert lru_cache.get("text A") == ([1.0], {})
        assert lru_cache.get("text B") == ([2.0], {})
    
    def test_same_text_same_key(self, lru_cache):
        """Same text should update existing entry."""
        lru_cache.put("text", ([1.0], {}))
        lru_cache.put("text", ([2.0], {}))  # Update
        
        assert lru_cache.get("text") == ([2.0], {})
        assert len(lru_cache.cache) == 1
    
    def test_hit_updates_lru_order(self, lru_cache):
        """Cache hit should update LRU order."""
        # Fill cache
        for i in range(5):
            lru_cache.put(f"text{i}", ([float(i)], {}))
        
        # Access oldest item
        lru_cache.get("text0")  # Moves to most recent
        
        # Add new item (should evict text1, not text0)
        lru_cache.put("new_text", ([99.0], {}))
        
        assert lru_cache.get("text0") is not None  # Still exists
        assert lru_cache.get("text1") is None  # Was evicted
    
    def test_capacity_enforced(self, lru_cache):
        """Cache should enforce capacity limit."""
        # Fill exactly at capacity
        for i in range(5):
            lru_cache.put(f"text{i}", ([float(i)], {}))
        
        assert len(lru_cache.cache) == 5
        assert lru_cache.access_stats['evictions'] == 0
        
        # Add one more - should evict oldest
        lru_cache.put("extra", ([99.0], {}))
        
        assert len(lru_cache.cache) == 5
        assert lru_cache.access_stats['evictions'] == 1
    
    def test_fifo_eviction_order(self, lru_cache):
        """Cache should evict oldest items first (FIFO)."""
        # Add items
        for i in range(7):  # 7 items with capacity 5
            lru_cache.put(f"text{i}", ([float(i)], {}))
        
        stats = lru_cache.get_stats()
        assert stats['evictions'] == 2  # 7 - 5 = 2 evicted
        
        # Oldest 2 should be evicted
        assert lru_cache.get("text0") is None
        assert lru_cache.get("text1") is None
        
        # Recent 5 should remain
        assert lru_cache.get("text2") is not None
        assert lru_cache.get("text6") is not None
    
    def test_stats_tracking(self, lru_cache):
        """Should track access statistics."""
        # Insert
        lru_cache.put("text", ([1.0], {}))
        
        # Miss
        lru_cache.get("unknown")
        
        # Hit (3 times)
        for _ in range(3):
            lru_cache.get("text")
        
        stats = lru_cache.get_stats()
        
        assert stats['inserts'] == 1
        assert stats['misses'] == 1
        assert stats['hits'] == 3
        assert stats['hit_rate'] == 0.75  # 3/4
        assert stats['size'] == 1
    
    def test_clear_removes_all(self, lru_cache):
        """Clear should remove all items."""
        lru_cache.put("text1", ([1.0], {}))
        lru_cache.put("text2", ([2.0], {}))
        
        lru_cache.clear()
        
        assert len(lru_cache.cache) == 0
        assert lru_cache.get("text1") is None
        assert lru_cache.get("text2") is None
    
    def test_model_parameter_in_key(self, lru_cache):
        """Different models should create different cache entries."""
        lru_cache.put("text", ([1.0], {}), model="model-A")
        lru_cache.put("text", ([2.0], {}), model="model-B")
        
        # Same text, different keys due to model
        assert len(lru_cache.cache) == 2
        assert lru_cache.get("text", model="model-A") == ([1.0], {})
        assert lru_cache.get("text", model="model-B") == ([2.0], {})
    
    def test_fill_rate_calculation(self, lru_cache):
        """Fill rate should reflect cache utilization."""
        for i in range(3):
            lru_cache.put(f"text{i}", ([float(i)], {}))
        
        stats = lru_cache.get_stats()
        assert stats['fill_rate'] == 0.6  # 3/5


class TestEmbeddingCacheIntegration:
    """Test integration with embedding service."""
    
    @pytest.fixture
    def embedding_service(self):
        cache = MockLRUCache(capacity=10)
        call_count = [0]  # mutable counter
        
        class EmbeddingService:
            def __init__(self, cache, counter):
                self.cache = cache
                self.call_count = counter
            
            def embed(self, text: str, model: str = "embedding-model") -> Tuple:
                """Get embedding with caching."""
                cached = self.cache.get(text, model)
                if cached:
                    return cached
                
                # Simulate embedding generation
                self.call_count[0] += 1
                embedding = self._generate_embedding(text, model)
                
                # Cache result
                self.cache.put(text, embedding, model)
                return embedding
            
            def _generate_embedding(self, text: str, model: str) -> Tuple:
                """Mock embedding generation."""
                import hashlib
                hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
                embedding_vector = [
                    (hash_val % 100) / 100.0,
                    ((hash_val // 100) % 100) / 100.0,
                    ((hash_val // 10000) % 100) / 100.0
                ]
                return (embedding_vector, {"model": model, "dim": 3})
            
            def get_call_count(self):
                return self.call_count[0]
        
        return EmbeddingService(cache, call_count)
    
    def test_first_call_generates_embedding(self, embedding_service):
        """First call should generate new embedding."""
        result = embedding_service.embed("sample text")
        
        assert result is not None
        assert embedding_service.get_call_count() == 1
    
    def test_repeated_call_uses_cache(self, embedding_service):
        """Repeated calls should hit cache."""
        # First call
        result1 = embedding_service.embed("sample text")
        
        # Second call (should use cache)
        result2 = embedding_service.embed("sample text")
        
        assert result1 == result2
        assert embedding_service.get_call_count() == 1
    
    def test_cache_reduces_embedding_calls(self, embedding_service):
        """Cache should reduce embedding API calls."""
        texts = ["text A", "text B", "text C"] * 3  # 9 calls total
        
        for text in texts:
            embedding_service.embed(text)
        
        # Should only make 3 unique calls
        assert embedding_service.get_call_count() == 3
        
        stats = embedding_service.cache.get_stats()
        assert stats['hit_rate'] > 0.6  # At least 60% hit rate
    
    def test_model_specific_caching(self, embedding_service):
        """Different models should have separate cache entries."""
        # Same text, different models
        embedding_service.embed("text", model="model-A")
        embedding_service.embed("text", model="model-B")
        
        # Should make 2 calls
        assert embedding_service.get_call_count() == 2
        
        stats = embedding_service.cache.get_stats()
        assert stats['size'] == 2


class TestEmbeddingCacheSizes:
    """Test behavior with different cache sizes."""
    
    @pytest.fixture
    def create_service(self):
        def factory(capacity: int):
            cache = MockLRUCache(capacity=capacity)
            call_count = [0]
            
            class EmbeddingService:
                def embed(self, text: str):
                    if cache.get(text) is not None:
                        return cache.get(text)
                    call_count[0] += 1
                    result = ([1.0], {"text": text})
                    cache.put(text, result)
                    return result
                
                def get_stats(self):
                    return cache.get_stats(), call_count[0]
            
            return EmbeddingService()
        return factory
    
    def test_small_cache_higher_eviction(self, create_service):
        """Small cache should have more evictions."""
        service = create_service(capacity=2)
        
        # Access 5 unique items
        for i in range(5):
            service.embed(f"text{i}")
        
        stats, calls = service.get_stats()
        assert stats['evictions'] == 3  # 5 - 2 = 3 evicted
    
    def test_large_cache_better_retention(self, create_service):
        """Large cache should retain more items."""
        service = create_service(capacity=100)
        
        for i in range(5):
            service.embed(f"text{i}")
        
        stats, calls = service.get_stats()
        assert stats['evictions'] == 0
        assert stats['size'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
