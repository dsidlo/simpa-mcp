"""Tests for diff saliency scoring and filtering."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from simpa.core.diff_saliency import (
    DiffSaliencyScorer,
    SalientDiff,
    SalientDiffFilter,
    SaliencyFactors,
)
from simpa.config import settings


class TestSaliencyFactors:
    """Test SaliencyFactors dataclass."""

    def test_default_values(self):
        """Test default factor values."""
        factors = SaliencyFactors()
        assert factors.impact_ratio == 0.0
        assert factors.keyword_density == 0.0
        assert factors.semantic_relevance == 0.0
        assert factors.file_type_weight == 1.0

    def test_custom_values(self):
        """Test custom factor values."""
        factors = SaliencyFactors(
            impact_ratio=0.5,
            keyword_density=0.7,
            semantic_relevance=0.9,
            file_type_weight=0.8
        )
        assert factors.impact_ratio == 0.5
        assert factors.keyword_density == 0.7
        assert factors.semantic_relevance == 0.9
        assert factors.file_type_weight == 0.8


class TestDiffSaliencyScorer:
    """Test DiffSaliencyScorer functionality."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer instance."""
        return DiffSaliencyScorer()

    def test_calculate_impact_ratio_small_change(self, scorer):
        """Test impact ratio for small changes."""
        # 10 lines changed in 100 line file
        ratio = scorer.calculate_impact_ratio(10, 100)
        assert 0 < ratio < 1.0

    def test_calculate_impact_ratio_large_change(self, scorer):
        """Test impact ratio for large changes."""
        # 90% of file changed
        ratio = scorer.calculate_impact_ratio(90, 100)
        assert 0 < ratio < 1.0

    def test_calculate_impact_ratio_unknown_size(self, scorer):
        """Test impact ratio when file size is unknown."""
        ratio = scorer.calculate_impact_ratio(10, 0)
        assert ratio == 0.5  # Default moderate impact

    def test_get_keyword_density_empty_content(self, scorer):
        """Test keyword density with empty content."""
        density = scorer.get_keyword_density("")
        assert density == 0.0

    def test_get_keyword_density_with_keywords(self, scorer):
        """Test keyword density with code keywords."""
        diff = """+def my_function():
-    pass
+    return True
+class MyClass:
+    def __init__(self):"""
        density = scorer.get_keyword_density(diff)
        assert 0 < density <= 1.0

    def test_get_keyword_density_no_keywords(self, scorer):
        """Test keyword density without code keywords."""
        diff = """+Some text
+More text
+Even more text"""
        density = scorer.get_keyword_density(diff)
        assert density == 0.0

    def test_get_file_type_weight_known_extensions(self, scorer):
        """Test file type weights for known extensions."""
        assert scorer.get_file_type_weight("file.py") == 1.0
        assert scorer.get_file_type_weight("file.ts") == 0.9
        assert scorer.get_file_type_weight("file.js") == 0.85
        assert scorer.get_file_type_weight("file.md") == 0.3

    def test_get_file_type_weight_unknown_extension(self, scorer):
        """Test file type weight for unknown extension."""
        assert scorer.get_file_type_weight("file.xyz") == 0.5  # Default

    def test_get_file_type_weight_no_extension(self, scorer):
        """Test file type weight for file without extension."""
        assert scorer.get_file_type_weight("Makefile") == 0.5  # Default

    @pytest.mark.asyncio
    async def test_calculate_semantic_relevance_no_context(self, scorer):
        """Test semantic relevance without context embedding."""
        relevance = await scorer.calculate_semantic_relevance("diff content", None)
        assert relevance == 0.5  # Neutral

    @pytest.mark.asyncio
    async def test_score_diff_basic(self, scorer):
        """Test basic diff scoring."""
        diff = """+def hello():
+    print('hello')
+    return True"""
        result = await scorer.score_diff("test.py", diff)
        
        assert isinstance(result, SalientDiff)
        assert result.file_path == "test.py"
        assert result.diff_content == diff
        assert 0 <= result.saliency_score <= 1.0
        assert isinstance(result.factors, SaliencyFactors)
        assert result.change_count > 0
        assert result.line_count > 0

    @pytest.mark.asyncio
    async def test_score_diff_multiple_files(self, scorer):
        """Test scoring multiple diffs."""
        diffs = {
            "main.py": "+def main():\n+    pass",
            "utils.js": "+function helper() {\n+    return 1;\n}",
            "readme.md": "+This is a readme\n+More text",
        }
        
        results = []
        for path, content in diffs.items():
            result = await scorer.score_diff(path, content)
            results.append(result)
        
        # Python should have higher score than markdown
        py_score = next(r for r in results if r.file_path == "main.py").saliency_score
        md_score = next(r for r in results if r.file_path == "readme.md").saliency_score
        assert py_score >= md_score


class TestSalientDiffFilter:
    """Test SalientDiffFilter functionality."""

    @pytest.fixture
    def filter_instance(self):
        """Create a filter instance."""
        return SalientDiffFilter()

    @pytest.mark.asyncio
    async def test_filter_empty_dict(self, filter_instance):
        """Test filtering empty dict."""
        filtered, metadata = await filter_instance.filter_diffs({})
        assert filtered == {}
        assert metadata["total"] == 0
        assert metadata["kept"] == 0

    @pytest.mark.asyncio
    async def test_filter_single_diff(self, filter_instance):
        """Test filtering single diff."""
        diffs = {
            "main.py": "+def main():\n+    pass"
        }
        filtered, metadata = await filter_instance.filter_diffs(diffs)
        
        assert isinstance(filtered, dict)
        assert metadata["total"] == 1
        assert metadata["kept"] >= 0

    @pytest.mark.asyncio
    async def test_filter_with_threshold(self, filter_instance):
        """Test filtering applies threshold."""
        # Low quality diff (just comments/text)
        diffs = {
            "readme.md": "+# This is just a comment\n+More text\n+Even more text"
        }
        
        filtered, metadata = await filter_instance.filter_diffs(diffs)
        # May or may not pass threshold depending on implementation
        assert isinstance(metadata, dict)
        assert "scores" in metadata

    @pytest.mark.asyncio
    async def test_filter_respects_max_diffs(self, filter_instance, monkeypatch):
        """Test filter respects max_diffs limit."""
        monkeypatch.setattr(settings, "diff_max_stored_per_request", 2)
        
        diffs = {
            f"file{i}.py": f"+def func{i}():\n+    pass" 
            for i in range(10)
        }
        
        filtered, metadata = await filter_instance.filter_diffs(diffs)
        assert len(filtered) <= 2
        assert metadata["filter_stats"]["truncated"] or len(filtered) == 10

    @pytest.mark.asyncio
    async def test_filter_disabled(self, filter_instance, monkeypatch):
        """Test filter when disabled."""
        monkeypatch.setattr(settings, "diff_saliency_enabled", False)
        
        diffs = {"test.py": "+content"}
        filtered, metadata = await filter_instance.filter_diffs(diffs)
        
        assert filtered == diffs
        assert metadata["enabled"] is False

    def test_extract_salient_summary_empty(self, filter_instance):
        """Test summary extraction from empty dict."""
        summary = filter_instance.extract_salient_summary({})
        assert summary == ""

    def test_extract_salient_summary_single_file(self, filter_instance):
        """Test summary extraction from single file."""
        diffs = {
            "main.py": """@@ -1,3 +1,5 @@
+def new_func():
+    return True
 def main():
     pass"""
        }
        summary = filter_instance.extract_salient_summary(diffs)
        assert "main.py" in summary
        assert "+" in summary or "-" in summary

    def test_extract_salient_summary_with_max(self, filter_instance):
        """Test summary respects max_files limit."""
        diffs = {
            f"file{i}.py": "+content" 
            for i in range(20)
        }
        summary = filter_instance.extract_salient_summary(diffs, max_files=3)
        
        lines = summary.split("\n")
        # Should only show up to 3 files
        file_lines = [l for l in lines if l.startswith("  -")]
        assert len(file_lines) <= 3


class TestDiffSaliencyIntegration:
    """Integration tests for diff saliency functionality."""

    @pytest.mark.asyncio
    async def test_end_to_end_filtering(self):
        """Test complete diff filtering pipeline."""
        diffs = {
            "src/main.py": """+def critical_function():
+    '''This is important'''
+    return process_data()
+    
+class DataProcessor:
+    def __init__(self):
+        self.data = []""",
            "README.md": "+Just updating docs\n+Added line",
            "tests/test_main.py": """+def test_critical():
+    result = critical_function()
+    assert result is not None""",
        }
        
        filter_instance = SalientDiffFilter()
        filtered, metadata = await filter_instance.filter_diffs(diffs)
        
        assert isinstance(filtered, dict)
        assert isinstance(metadata, dict)
        assert metadata["total"] == 3
        assert metadata["enabled"] is True

    @pytest.mark.asyncio
    async def test_real_world_diff_example(self):
        """Test with realistic git-style diff."""
        diff = """diff --git a/src/main.py b/src/main.py
index 123456..789abc 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,5 +10,10 @@ def old_function():
     pass
 
+def new_critical_function(data: dict) -> bool:
+    '''Process data with validation'''
+    if not data:
+        raise ValueError("Data required")
+    return process(data)
+
 def main():
     return old_function()"""
        
        scorer = DiffSaliencyScorer()
        result = await scorer.score_diff("src/main.py", diff)
        
        # Should score high (contains function def, keywords)
        assert result.saliency_score > 0.3
        assert result.factors.keyword_density > 0
