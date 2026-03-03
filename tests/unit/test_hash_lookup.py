"""Unit tests for hash-based fast path lookup optimization."""
import pytest
import hashlib
from typing import Dict, Optional, Set


class MockHashLookup:
    """Mock implementation of hash-based fast path lookup."""
    
    def __init__(self):
        self.policy_hashes: Dict[str, str] = {}  # policy_id -> hash
        self.file_hashes: Dict[str, str] = {}    # filepath -> hash
        self.cache_hits: int = 0
        self.cache_misses: int = 0
    
    def _compute_hash(self, content: str) -> str:
        """Compute MD5 hash of content."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def store_policy_hash(self, policy_id: str, policy_content: str):
        """Store hash of policy for later comparison."""
        self.policy_hashes[policy_id] = self._compute_hash(policy_content)
    
    def store_file_hash(self, filepath: str, content: str):
        """Store hash of file for later comparison."""
        self.file_hashes[filepath] = self._compute_hash(content)
    
    def check_policy_unchanged(self, policy_id: str, current_content: str) -> bool:
        """Check if policy has changed since last hash."""
        current_hash = self._compute_hash(current_content)
        stored_hash = self.policy_hashes.get(policy_id)
        
        if stored_hash is None:
            self.cache_misses += 1
            return False
        
        if stored_hash == current_hash:
            self.cache_hits += 1
            return True
        
        self.cache_misses += 1
        return False
    
    def check_file_unchanged(self, filepath: str, current_content: str) -> bool:
        """Check if file has changed since last hash."""
        current_hash = self._compute_hash(current_content)
        stored_hash = self.file_hashes.get(filepath)
        
        if stored_hash is None:
            self.cache_misses += 1
            return False
        
        if stored_hash == current_hash:
            self.cache_hits += 1
            return True
        
        self.cache_misses += 1
        return False
    
    def get_stats(self) -> Dict:
        """Get hash lookup statistics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0.0
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'total_checks': total,
            'stored_policies': len(self.policy_hashes),
            'stored_files': len(self.file_hashes)
        }


class TestHashLookup:
    """Test suite for hash-based lookup optimization."""
    
    @pytest.fixture
    def hash_lookup(self):
        return MockHashLookup()
    
    def test_compute_hash_consistency(self, hash_lookup):
        """Same content should produce same hash."""
        content = "test content"
        hash1 = hash_lookup._compute_hash(content)
        hash2 = hash_lookup._compute_hash(content)
        
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length
    
    def test_compute_hash_uniqueness(self, hash_lookup):
        """Different content should produce different hashes."""
        hash1 = hash_lookup._compute_hash("content A")
        hash2 = hash_lookup._compute_hash("content B")
        
        assert hash1 != hash2
    
    def test_store_policy_hash(self, hash_lookup):
        """Should store policy hash correctly."""
        hash_lookup.store_policy_hash("policy1", "policy content")
        
        assert "policy1" in hash_lookup.policy_hashes
        assert len(hash_lookup.policy_hashes["policy1"]) == 32
    
    def test_check_policy_unchanged_true(self, hash_lookup):
        """Should detect unchanged policy."""
        content = "policy content"
        hash_lookup.store_policy_hash("policy1", content)
        
        is_unchanged = hash_lookup.check_policy_unchanged("policy1", content)
        
        assert is_unchanged is True
        assert hash_lookup.cache_hits == 1
    
    def test_check_policy_unchanged_false(self, hash_lookup):
        """Should detect changed policy."""
        hash_lookup.store_policy_hash("policy1", "old content")
        
        is_unchanged = hash_lookup.check_policy_unchanged("policy1", "new content")
        
        assert is_unchanged is False
        assert hash_lookup.cache_misses == 1
    
    def test_check_policy_no_stored_hash(self, hash_lookup):
        """Should return False for policy with no stored hash."""
        is_unchanged = hash_lookup.check_policy_unchanged("unknown_policy", "content")
        
        assert is_unchanged is False
        assert hash_lookup.cache_misses == 1
    
    def test_store_file_hash(self, hash_lookup):
        """Should store file hash correctly."""
        hash_lookup.store_file_hash("/path/to/file.py", "file content")
        
        assert "/path/to/file.py" in hash_lookup.file_hashes
    
    def test_check_file_unchanged_true(self, hash_lookup):
        """Should detect unchanged file."""
        content = "file content"
        hash_lookup.store_file_hash("/path/file.py", content)
        
        is_unchanged = hash_lookup.check_file_unchanged("/path/file.py", content)
        
        assert is_unchanged is True
    
    def test_check_file_changed(self, hash_lookup):
        """Should detect changed file."""
        hash_lookup.store_file_hash("/path/file.py", "old content")
        
        is_unchanged = hash_lookup.check_file_unchanged("/path/file.py", "new content")
        
        assert is_unchanged is False
    
    def test_multiple_policies_isolated(self, hash_lookup):
        """Policies should have independent hash tracking."""
        hash_lookup.store_policy_hash("policy1", "content 1")
        hash_lookup.store_policy_hash("policy2", "content 2")
        
        assert hash_lookup.check_policy_unchanged("policy1", "content 1") is True
        assert hash_lookup.check_policy_unchanged("policy2", "content 2") is True
        assert hash_lookup.check_policy_unchanged("policy1", "content 2") is False
    
    def test_stats_tracking(self, hash_lookup):
        """Should track cache statistics correctly."""
        # One hit
        hash_lookup.store_policy_hash("p1", "content")
        hash_lookup.check_policy_unchanged("p1", "content")
        
        # Two misses
        hash_lookup.check_policy_unchanged("p1", "different")
        hash_lookup.check_policy_unchanged("unknown", "content")
        
        stats = hash_lookup.get_stats()
        
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 2
        assert stats['hit_rate'] == 1/3
        assert stats['total_checks'] == 3
        assert stats['stored_policies'] == 1
    
    def test_whitespace_sensitivity(self, hash_lookup):
        """Hash should be sensitive to whitespace."""
        hash1 = hash_lookup._compute_hash("content")
        hash2 = hash_lookup._compute_hash("content ")
        
        assert hash1 != hash2


class TestFastPathOptimization:
    """Test repository fast path using hash lookup."""
    
    @pytest.fixture
    def fast_path_repo(self):
        hash_lookup = MockHashLookup()
        
        class FastPathRepo:
            def __init__(self, hash_lookup):
                self.hash_lookup = hash_lookup
                self.llm_calls = 0
                self.fast_path_hits = 0
            
            def process_diff(self, filepath: str, file_content: str, diff_text: str):
                """Process diff with fast path optimization."""
                # Check if we've seen this exact file before
                if self.hash_lookup.check_file_unchanged(filepath, file_content):
                    self.fast_path_hits += 1
                    return {
                        'fast_path': True,
                        'result': 'UNCHANGED',
                        'message': 'File unchanged since last check'
                    }
                
                # Check policy cache
                # (Would check policy hash here in real implementation)
                
                # Otherwise, need LLM analysis
                self.llm_calls += 1
                
                # Store new hash
                self.hash_lookup.store_file_hash(filepath, file_content)
                
                return {
                    'fast_path': False,
                    'result': 'ANALYZED',
                    'requires_llm': True
                }
        
        return FastPathRepo(hash_lookup)
    
    def test_fast_path_hit_skips_llm(self, fast_path_repo):
        """Fast path hit should skip LLM call."""
        # First call - stores hash
        result1 = fast_path_repo.process_diff("file.py", "content", "diff")
        
        # Second call with same content - fast path
        result2 = fast_path_repo.process_diff("file.py", "content", "diff")
        
        assert result1['fast_path'] is False
        assert result2['fast_path'] is True
        assert fast_path_repo.llm_calls == 1
        assert fast_path_repo.fast_path_hits == 1
    
    def test_changed_content_bypasses_fast_path(self, fast_path_repo):
        """Changed content should bypass fast path."""
        # First call
        fast_path_repo.process_diff("file.py", "content v1", "diff")
        
        # Second call with different content
        result = fast_path_repo.process_diff("file.py", "content v2", "diff")
        
        assert result['fast_path'] is False
        assert fast_path_repo.llm_calls == 2
    
    def test_different_files_independent(self, fast_path_repo):
        """Different files should have independent fast paths."""
        file1_content = "content 1"
        file2_content = "content 2"
        
        # Process both files
        fast_path_repo.process_diff("file1.py", file1_content, "diff")
        fast_path_repo.process_diff("file2.py", file2_content, "diff")
        
        # Re-check both (both should hit fast path)
        with_fast1 = fast_path_repo.process_diff("file1.py", file1_content, "diff")
        with_fast2 = fast_path_repo.process_diff("file2.py", file2_content, "diff")
        
        assert with_fast1['fast_path'] is True
        assert with_fast2['fast_path'] is True
        assert fast_path_repo.llm_calls == 2  # Initial calls only
        assert fast_path_repo.fast_path_hits == 2


class TestHashCollisionHandling:
    """Test handling of hash collisions (rare but important)."""
    
    def test_md5_collision_extremely_unlikely(self):
        """MD5 collisions are extremely unlikely with proper content."""
        # This is a sanity check, not a real collision test
        import hashlib
        
        contents = [
            "def function(): pass",
            "def function():  pass",
            "def function() : pass",
        ]
        
        hashes = [hashlib.md5(c.encode()).hexdigest() for c in contents]
        
        # All should be different
        assert len(set(hashes)) == len(contents)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
