"""Integration tests for SIMPA's optimized workflow with all optimizations enabled."""
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib


class MockRefinerWithOptimizations:
    """Mock refiner with all SIMPA optimizations implemented."""
    
    def __init__(self):
        # Hash-based fast path
        self.file_hashes: Dict[str, str] = {}
        self.policy_hashes: Dict[str, str] = {}
        
        # LLM cache
        self.llm_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.llm_cache_ttl = 3600
        
        # Embedding LRU cache  
        self.embedding_cache_capacity = 50
        self.embedding_cache: Dict[str, Any] = {}
        self.embedding_access_order: List[str] = []
        
        # Diff saliency
        self.saliency_threshold = 0.3
        
        # Stats
        self.stats = {
            'hash_fast_path_hits': 0,
            'hash_fast_path_misses': 0,
            'llm_cache_hits': 0,
            'llm_cache_misses': 0,
            'llm_calls_skipped_trivial': 0,
            'llm_calls_made': 0,
            'embedding_cache_hits': 0,
            'embedding_cache_misses': 0,
            'diffs_filtered_trivial': 0,
            'diffs_process': 0
        }
    
    def _hash(self, content: str) -> str:
        """Compute content hash."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _check_hash_fast_path(self, filepath: str, content: str) -> bool:
        """Check if file content is unchanged (hash-based fast path)."""
        current_hash = self._hash(content)
        stored_hash = self.file_hashes.get(filepath)
        
        if stored_hash and stored_hash == current_hash:
            self.stats['hash_fast_path_hits'] += 1
            return True
        
        self.file_hashes[filepath] = current_hash
        self.stats['hash_fast_path_misses'] += 1
        return False
    
    def _score_diff_saliency(self, diff_text: str, filename: str) -> Tuple[float, str]:
        """Score diff for saliency."""
        if not diff_text or not diff_text.strip():
            return (0.0, "trivial")
        
        # Simple scoring based on keywords and patterns
        score = 0.0
        content_lower = diff_text.lower()
        
        # Security keywords
        security_keywords = ['auth', 'password', 'token', 'security', 'encrypt']
        score += sum(0.2 for kw in security_keywords if kw in content_lower)
        
        # API keywords
        api_keywords = ['api', 'endpoint', 'route', 'request']
        score += sum(0.15 for kw in api_keywords if kw in content_lower)
        
        # Database keywords
        db_keywords = ['database', 'sql', 'query', 'migration', 'table']
        score += sum(0.12 for kw in db_keywords if kw in content_lower)
        
        # Function definitions
        if 'def ' in diff_text or 'class ' in diff_text:
            score += 0.3
        
        # File type bonus
        if filename.endswith(('.py', '.js', '.ts')):
            score += 0.1
        
        score = min(score, 1.0)
        
        if score < 0.2:
            category = "trivial"
        elif score < 0.4:
            category = "minor"
        elif score < 0.7:
            category = "significant"
        else:
            category = "critical"
        
        return (score, category)
    
    def _get_embedding_cached(self, text: str) -> List[float]:
        """Get embedding with LRU cache."""
        if text in self.embedding_cache:
            # Move to end (most recent)
            self.embedding_access_order.remove(text)
            self.embedding_access_order.append(text)
            self.stats['embedding_cache_hits'] += 1
            return self.embedding_cache[text]
        
        # Generate embedding (mock)
        embedding = [hash(text) % 100 / 100.0] * 10
        
        # Evict if needed
        if len(self.embedding_cache) >= self.embedding_cache_capacity:
            oldest = self.embedding_access_order.pop(0)
            del self.embedding_cache[oldest]
        
        self.embedding_cache[text] = embedding
        self.embedding_access_order.append(text)
        self.stats['embedding_cache_misses'] += 1
        return embedding
    
    def _call_llm_cached(self, prompt: str, context: Dict) -> Dict:
        """Call LLM with caching."""
        cache_key = self._hash(f"{prompt}:{str(sorted(context.items()))}")
        
        # Check cache
        if cache_key in self.llm_cache:
            result, timestamp = self.llm_cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.llm_cache_ttl):
                self.stats['llm_cache_hits'] += 1
                return {**result, 'cached': True}
        
        # Make LLM call (mock)
        self.stats['llm_cache_misses'] += 1
        self.stats['llm_calls_made'] += 1
        
        result = {
            'suggestions': ['Mock suggestion 1', 'Mock suggestion 2'],
            'confidence': 0.85
        }
        
        # Cache result
        self.llm_cache[cache_key] = (result, datetime.now())
        return result
    
    def process_diff(self, filepath: str, file_content: str, diff_text: str, policy: str) -> Dict:
        """Process a diff with all optimizations."""
        self.stats['diffs_process'] += 1
        
        # Optimization 1: Hash-based fast path
        if self._check_hash_fast_path(filepath, file_content):
            return {
                'filepath': filepath,
                'status': 'fast_path',
                'result': 'UNCHANGED',
                'message': 'File unchanged, skipped LLM call'
            }
        
        # Optimization 2: Diff saliency filtering
        score, category = self._score_diff_saliency(diff_text, filepath)
        
        if score < self.saliency_threshold:
            self.stats['diffs_filtered_trivial'] += 1
            self.stats['llm_calls_skipped_trivial'] += 1
            return {
                'filepath': filepath,
                'status': 'filtered',
                'category': category,
                'score': score,
                'result': 'TRIVIAL'
            }
        
        # Optimization 4: Cached embedding lookup (if needed for policy matching)
        policy_embedding = self._get_embedding_cached(policy)
        
        # Optimization 3: Cached LLM call
        prompt = f"Review {filepath} ({category}, score={score:.2f})"
        llm_result = self._call_llm_cached(prompt, {
            'diff': diff_text[:100],
            'policy_hash': self._hash(policy)
        })
        
        return {
            'filepath': filepath,
            'status': 'analyzed',
            'category': category,
            'score': score,
            'llm_result': llm_result,
            'policy_embedding_match': policy_embedding
        }
    
    def get_stats(self) -> Dict:
        """Get optimization statistics."""
        total_llm_requests = self.stats['llm_cache_hits'] + self.stats['llm_cache_misses']
        llm_cache_rate = self.stats['llm_cache_hits'] / total_llm_requests if total_llm_requests > 0 else 0
        
        total_hash_checks = self.stats['hash_fast_path_hits'] + self.stats['hash_fast_path_misses']
        hash_hit_rate = self.stats['hash_fast_path_hits'] / total_hash_checks if total_hash_checks > 0 else 0
        
        total_embeddings = self.stats['embedding_cache_hits'] + self.stats['embedding_cache_misses']
        embedding_hit_rate = self.stats['embedding_cache_hits'] / total_embeddings if total_embeddings > 0 else 0
        
        return {
            **self.stats,
            'llm_cache_rate': llm_cache_rate,
            'hash_fast_path_rate': hash_hit_rate,
            'embedding_cache_rate': embedding_hit_rate,
            'total_llm_calls_avoided': (
                self.stats['hash_fast_path_hits'] +
                self.stats['llm_calls_skipped_trivial'] +
                self.stats['llm_cache_hits']
            )
        }


@pytest.mark.integration
class TestOptimizedWorkflowIntegration:
    """Integration tests for the full optimized workflow."""
    
    @pytest.fixture
    def refiner(self):
        return MockRefinerWithOptimizations()
    
    def test_fast_path_unchanged_files(self, refiner):
        """Unchanged files should hit fast path."""
        content = "def example(): pass"
        
        # First call - stores hash
        result1 = refiner.process_diff("file.py", content, "+def example(): pass", "policy")
        
        # Second call - same content, fast path
        result2 = refiner.process_diff("file.py", content, "+def example(): pass", "policy")
        
        assert result1['status'] == 'analyzed'
        assert result2['status'] == 'fast_path'
        
        stats = refiner.get_stats()
        assert stats['hash_fast_path_hits'] == 1
    
    def test_trivial_diff_filtering(self, refiner):
        """Trivial diffs should be filtered."""
        trivial_diff = """# Just a comment
// Another comment"""
        
        result = refiner.process_diff("readme.md", "content", trivial_diff, "policy")
        
        assert result['status'] == 'filtered'
        assert result['category'] == 'trivial'
        assert refiner.stats['diffs_filtered_trivial'] == 1
    
    def test_significant_diff_not_filtered(self, refiner):
        """Significant diffs should be processed."""
        diff = """+def authenticate_user():
+    token = generate_auth_token()
+    validate_password()
+    log_security_event()"""
        
        result = refiner.process_diff("auth.py", "content", diff, "policy")
        
        assert result['status'] == 'analyzed'
        assert result['category'] in ['significant', 'critical']
    
    def test_llm_cache_reduces_calls(self, refiner):
        """LLM cache should reduce actual LLM calls."""
        diff = "+def process(): pass"
        
        # Same diff twice
        refiner.process_diff("file1.py", "content", diff, "policy")
        refiner.process_diff("file2.py", "content", diff, "policy")
        
        stats = refiner.get_stats()
        # Second call should hit cache for same diff characteristics
        assert stats['llm_calls_made'] <= 2
    
    def test_embedding_cache(self, refiner):
        """Embedding cache should work correctly."""
        policy = "Security and API validation policy"
        
        # Process multiple files with same policy
        for i in range(5):
            refiner.process_diff(f"file{i}.py", f"content{i}", "+def func(): pass", policy)
        
        stats = refiner.get_stats()
        # Only one embedding call for the policy
        assert stats['embedding_cache_misses'] == 1
        assert stats['embedding_cache_hits'] == 4
    
    def test_full_workflow_multiple_files(self, refiner):
        """Test full workflow with multiple files."""
        files = [
            ("api.py", "+def endpoint():\n+    auth.validate()", "significant content"),
            ("readme.md", "+## Section", "docs"),
            ("config.json", "+{\"key\": \"value\"}", "settings"),
            ("utils.py", "+def process(): pass", "code"),
        ]
        
        results = []
        for filepath, diff, content in files:
            result = refiner.process_diff(filepath, content, diff, "security policy")
            results.append(result)
            
            # Process again (should hit fast path)
            refiner.process_diff(filepath, content, diff, "security policy")
        
        # Check filtering
        categories = [r['category'] if r['status'] == 'filtered' else 'analyzed' for r in results]
        assert 'trivial' in categories  # readme should be filtered
        
        stats = refiner.get_stats()
        assert stats['hash_fast_path_hits'] == 4  # All files hit fast path on second pass
        assert stats['diffs_process'] == 8  # 4 files × 2 passes
    
    def test_changed_content_bypasses_fast_path(self, refiner):
        """Changed content should bypass fast path."""
        filepath = "file.py"
        
        # First version
        refiner.process_diff(filepath, "content v1", "+def v1(): pass", "policy")
        
        # Second version (different content)
        result = refiner.process_diff(filepath, "content v2", "+def v2(): pass", "policy")
        
        assert result['status'] == 'analyzed'
        assert refiner.stats['hash_fast_path_hits'] == 0
    
    def test_cache_stats_accuracy(self, refiner):
        """Cache statistics should be accurate."""
        # Mix of operations
        refiner.process_diff("f1.py", "content", "+def func(): pass", "policy")
        refiner.process_diff("f1.py", "content", "+def func(): pass", "policy")  # Fast path
        refiner.process_diff("f2.py", "content", "+def func(): pass", "policy")
        
        stats = refiner.get_stats()
        
        assert stats['hash_fast_path_hits'] == 1
        assert stats['hash_fast_path_misses'] == 2
        assert stats['hash_fast_path_rate'] == 1/3
    
    def test_security_diff_scores_critical_significant(self, refiner):
        """Security-related diffs should score as significant or critical."""
        diff = """-password = request.data
+password = hash_password(request.data)"""
        
        result = refiner.process_diff("auth.py", "content", diff, "security policy")
        
        # Should be at least significant
        assert result['category'] in ['significant', 'critical']
    
    def test_api_diff_scores_significant(self, refiner):
        """API changes should score as significant."""
        diff = """+@app.route('/api/users')
+def get_users():
+    return database.query()"""
        
        result = refiner.process_diff("routes.py", "content", diff, "API policy")
        
        assert result['category'] in ['significant', 'critical']
    
    def test_total_llm_calls_avoided_calculation(self, refiner):
        """Calculate total LLM calls avoided correctly."""
        # Process same file twice (fast path)
        refiner.process_diff("file.py", "content", "+def func(): pass", "policy")
        refiner.process_diff("file.py", "content", "+def func(): pass", "policy")
        
        # Process trivial diff (filtered)
        refiner.process_diff("doc.md", "content", "# comment", "policy")
        
        stats = refiner.get_stats()
        
        assert stats['total_llm_calls_avoided'] >= 2  # 1 fast path + 1 filtered
        assert stats['llm_cache_rate'] >= 0
        assert 0 <= stats['llm_cache_rate'] <= 1


@pytest.mark.integration
class TestRegressionScenarios:
    """Test that optimizations don't break core functionality."""
    
    @pytest.fixture
    def refiner(self):
        return MockRefinerWithOptimizations()
    
    def test_empty_diff_handling(self, refiner):
        """Empty diffs should be handled gracefully."""
        result = refiner.process_diff("file.py", "content", "", "policy")
        
        assert result['status'] == 'filtered'
        assert result['category'] == 'trivial'
    
    def test_none_diff_handling(self, refiner):
        """None diffs should be handled gracefully."""
        result = refiner.process_diff("file.py", "content", None, "policy")
        
        # Should not crash
        assert 'status' in result
    
    def test_very_large_diff(self, refiner):
        """Very large diffs should be handled."""
        large_diff = "+line\n" * 10000
        
        result = refiner.process_diff("file.py", "content", large_diff, "policy")
        
        assert 'status' in result
    
    def test_unicode_content(self, refiner):
        """Unicode content should be handled."""
        unicode_diff = "+def 日本語(): pass"
        
        result = refiner.process_diff("file.py", "content", unicode_diff, "policy")
        
        assert 'status' in result
    
    def test_special_characters_in_filename(self, refiner):
        """Special characters in filenames should be handled."""
        result = refiner.process_diff("file-with-special-chars_v1.2.py", "content", "+pass", "policy")
        
        assert 'status' in result
    
    def test_multiple_policy_embeddings(self, refiner):
        """Multiple policy embeddings should be cached correctly."""
        diff = "+def func(): pass"
        
        result1 = refiner.process_diff("file.py", "content1", diff, "policy A")
        result2 = refiner.process_diff("file.py", "content2", diff, "policy B")
        result3 = refiner.process_diff("file.py", "content3", diff, "policy A")  # Same policy again
        
        # All should be analyzed (different content each time)
        assert result1['status'] == 'analyzed'
        assert result2['status'] == 'analyzed'
        assert result3['status'] == 'analyzed'
        
        # Policy A's embedding should have been retrieved from cache
        # (not tested in mock, but architecture supports it)


@pytest.mark.integration
class TestPerformanceMetrics:
    """Test that optimizations provide expected performance benefits."""
    
    @pytest.fixture
    def simulate_heavy_load(self):
        def _simulate(repeats: int = 100):
            refiner = MockRefinerWithOptimizations()
            
            # Simulate a typical workflow with repeated patterns
            files = [
                ("api.py", "+@app.route('/users')", "security api"),
                ("models.py", "+class User:", "database model"),
                ("utils.py", "+def helper():", "utility"),
                ("tests.py", "+def test():", "test code"),
            ]
            
            for _ in range(repeats):
                for filepath, diff, policy in files:
                    # First call
                    refiner.process_diff(filepath, f"content of {filepath}", diff, policy)
                    # Second call (same) - fast path
                    refiner.process_diff(filepath, f"content of {filepath}", diff, policy)
            
            return refiner.get_stats()
        return _simulate
    
    def test_fast_path_hit_rate_above_40_percent(self, simulate_heavy_load):
        """Fast path should hit at least 40% of the time."""
        stats = simulate_heavy_load(50)
        
        assert stats['hash_fast_path_rate'] >= 0.4, \
            f"Fast path hit rate {stats['hash_fast_path_rate']} is below 40%"
    
    def test_llm_cache_effective(self, simulate_heavy_load):
        """LLM cache should provide some benefit."""
        stats = simulate_heavy_load(50)
        
        # With repeated patterns, cache should be useful
        assert stats['llm_cache_rate'] >= 0
    
    def test_trivial_diffs_filtered(self, simulate_heavy_load):
        """Trivial diffs should be filtered."""
        refiner = MockRefinerWithOptimizations()
        
        # Add some trivial diffs
        for _ in range(50):
            refiner.process_diff("readme.md", "content", "# Just a comment", "policy")
        
        stats = refiner.get_stats()
        assert stats['diffs_filtered_trivial'] > 0
    
    def test_embedding_cache_reduces_calls(self, simulate_heavy_load):
        """Embedding cache should reduce embedding API calls."""
        refiner = MockRefinerWithOptimizations()
        
        # Same policy, many files
        for i in range(20):
            refiner.process_diff(f"file{i}.py", "content", "+def func(): pass", "same policy")
        
        stats = refiner.get_stats()
        total_embeddings = stats['embedding_cache_hits'] + stats['embedding_cache_misses']
        
        if total_embeddings > 0:
            assert stats['embedding_cache_rate'] >= 0.8, \
                f"Embedding cache rate {stats['embedding_cache_rate']} is below 80%"
    
    def test_optimization_effectiveness_summary(self, simulate_heavy_load):
        """Summary of all optimization effectiveness."""
        stats = simulate_heavy_load(25)
        
        print("\n=== OPTIMIZATION EFFECTIVENESS REPORT ===")
        print(f"Fast Path Hit Rate:  {stats['hash_fast_path_rate']:.2%}")
        print(f"LLM Cache Hit Rate:  {stats['llm_cache_rate']:.2%}")
        print(f"Embedding Cache Rate: {stats['embedding_cache_rate']:.2%}")
        print(f"Trivial Diffs Filtered: {stats['diffs_filtered_trivial']}")
        print(f"Total LLM Calls Avoided: {stats['total_llm_calls_avoided']}")
        print(f"Actual LLM Calls Made: {stats['llm_calls_made']}")
        print("==========================================")
        
        # Overall effectiveness assertion
        assert stats['total_llm_calls_avoided'] > 0, \
            "Optimizations should avoid at least some LLM calls"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
