"""Diff saliency scoring and filtering module for SIMPA."""

import hashlib
import re
import structlog
from dataclasses import dataclass
from typing import Any, Optional

from simpa.config import settings
from simpa.embedding.service import EmbeddingService

logger = structlog.get_logger()


@dataclass
class SaliencyFactors:
    """Factors contributing to diff saliency score."""
    impact_ratio: float = 0.0
    keyword_density: float = 0.0
    semantic_relevance: float = 0.0
    file_type_weight: float = 1.0


@dataclass
class SalientDiff:
    """A diff with computed saliency score."""
    file_path: str
    diff_content: str
    saliency_score: float
    factors: SaliencyFactors
    change_count: int
    line_count: int


class DiffSaliencyScorer:
    """Score diffs for semantic importance and storage priority."""

    # Keywords that indicate important code changes
    CODE_KEYWORDS = {
        "def ", "class ", "import ", "return", "raise", "await",
        "async ", "try:", "except", "finally", "if ", "elif ", "else:",
        "for ", "while ", "with ", "yield", "lambda", "@"  # decorators
    }

    # File type weights (higher = more important)
    FILE_TYPE_WEIGHTS = {
        ".py": 1.0,
        ".ts": 0.9,
        ".tsx": 0.9,
        ".js": 0.85,
        ".jsx": 0.85,
        ".go": 0.9,
        ".rs": 0.9,
        ".java": 0.85,
        ".kt": 0.85,
        ".sql": 0.7,
        ".yml": 0.5,
        ".yaml": 0.5,
        ".json": 0.4,
        ".md": 0.3,
        ".txt": 0.2,
    }

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        """Initialize the scorer."""
        self.embedding_service = embedding_service

    def calculate_impact_ratio(self, diff_lines: int, total_lines: int = 100) -> float:
        """Calculate impact ratio based on change size.
        
        Args:
            diff_lines: Number of lines changed
            total_lines: Total lines in file (or default)
            
        Returns:
            Impact ratio (0.0 to 1.0)
        """
        if total_lines == 0:
            return 0.5  # Unknown size, moderate impact
            
        # Impact increases with change size, but caps at 1.0
        ratio = min(diff_lines / total_lines, 1.0)
        
        # Use sigmoid-like curve - small changes have moderate impact
        # but very large changes don't necessarily mean more relevant
        return 1.0 / (1.0 + (ratio - 0.5) ** 2)

    def get_keyword_density(self, diff_content: str) -> float:
        """Calculate density of important code keywords.
        
        Args:
            diff_content: The diff content
            
        Returns:
            Keyword density score (0.0 to 1.0)
        """
        lines = diff_content.split("\n")
        if not lines:
            return 0.0
            
        # Only count added/modified lines (starting with + or not with +/-)
        content_lines = [
            line for line in lines 
            if line.startswith("+") and not line.startswith("+++")
        ]
        
        if not content_lines:
            content_lines = [
                line for line in lines 
                if not line.startswith(("-", "+++", "---", "@@", "diff", "index"))
            ]
        
        if not content_lines:
            return 0.0
            
        keyword_count = 0
        total_lines = len(content_lines)
        
        for line in content_lines:
            line_lower = line.lower()
            for keyword in self.CODE_KEYWORDS:
                if keyword in line_lower:
                    keyword_count += 1
                    break
        
        return min(keyword_count / max(total_lines, 1), 1.0)

    def get_file_type_weight(self, file_path: str) -> float:
        """Get weight based on file type.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Weight from FILE_TYPE_WEIGHTS or default 0.5
        """
        import os
        ext = os.path.splitext(file_path)[1].lower()
        return self.FILE_TYPE_WEIGHTS.get(ext, 0.5)

    async def calculate_semantic_relevance(
        self, 
        diff_content: str, 
        context_embedding: Optional[list[float]] = None
    ) -> float:
        """Calculate semantic relevance of diff to request context.
        
        Args:
            diff_content: The diff content
            context_embedding: Optional embedding of the request context
            
        Returns:
            Semantic relevance score (0.0 to 1.0)
        """
        if context_embedding is None or self.embedding_service is None:
            return 0.5  # Neutral when context unavailable
            
        try:
            # Extract meaningful text from diff
            content_lines = [
                line[1:]  # Remove leading +/-
                for line in diff_content.split("\n")
                if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
            ]
            content_text = " ".join(content_lines[:50])  # First 50 lines only
            
            if not content_text:
                return 0.5
                
            # Get embedding for diff content
            diff_embedding = await self.embedding_service.embed(content_text)
            
            # Calculate cosine similarity
            import math
            dot_product = sum(a * b for a, b in zip(diff_embedding, context_embedding))
            norm_a = math.sqrt(sum(a * a for a in diff_embedding))
            norm_b = math.sqrt(sum(b * b for b in context_embedding))
            
            if norm_a == 0 or norm_b == 0:
                return 0.5
                
            similarity = dot_product / (norm_a * norm_b)
            return (similarity + 1.0) / 2.0  # Normalize to [0, 1]
            
        except Exception as e:
            logger.warning("semantic_relevance_calculation_failed", error=str(e))
            return 0.5

    async def score_diff(
        self,
        file_path: str,
        diff_content: str,
        context_embedding: Optional[list[float]] = None
    ) -> SalientDiff:
        """Score a single diff for saliency.
        
        Args:
            file_path: Path to the file
            diff_content: The diff content
            context_embedding: Optional embedding of request context
            
        Returns:
            SalientDiff with computed score and factors
        """
        # Calculate individual factors
        line_count = len(diff_content.split("\n"))
        change_count = len([l for l in diff_content.split("\n") if l.startswith(("+", "-"))])
        
        factors = SaliencyFactors(
            impact_ratio=self.calculate_impact_ratio(change_count, max(line_count, 100)),
            keyword_density=self.get_keyword_density(diff_content),
            file_type_weight=self.get_file_type_weight(file_path),
            semantic_relevance=0.5  # Will be updated if context provided
        )
        
        # Calculate semantic relevance if possible
        if context_embedding is not None and self.embedding_service is not None:
            factors.semantic_relevance = await self.calculate_semantic_relevance(
                diff_content, context_embedding
            )
        
        # Compute weighted score
        # Weights: 30% impact, 25% keywords, 35% semantic, 10% file type
        saliency_score = (
            factors.impact_ratio * 0.30 +
            factors.keyword_density * 0.25 +
            factors.semantic_relevance * 0.35 +
            factors.file_type_weight * 0.10
        )
        
        return SalientDiff(
            file_path=file_path,
            diff_content=diff_content,
            saliency_score=saliency_score,
            factors=factors,
            change_count=change_count,
            line_count=line_count
        )


class SalientDiffFilter:
    """Filter diffs to store only the most salient ones."""

    def __init__(self, scorer: Optional[DiffSaliencyScorer] = None):
        """Initialize the filter."""
        self.scorer = scorer or DiffSaliencyScorer()

    async def filter_diffs(
        self,
        diffs: dict[str, str],
        context_embedding: Optional[list[float]] = None
    ) -> tuple[dict[str, str], dict[str, Any]]:
        """Filter diffs and return only salient ones.
        
        Args:
            diffs: Dict of file_path -> diff_content
            context_embedding: Optional embedding of request context
            
        Returns:
            Tuple of (filtered_diffs, saliency_metadata)
        """
        # Read settings at runtime to allow test overrides
        threshold = settings.diff_saliency_threshold
        max_diffs = settings.diff_max_stored_per_request
        
        if not settings.diff_saliency_enabled:
            return diffs, {"enabled": False}
            
        if not diffs:
            return {}, {"enabled": True, "total": 0, "kept": 0}
            
        # Score all diffs
        scored_diffs = []
        for file_path, diff_content in diffs.items():
            scored = await self.scorer.score_diff(file_path, diff_content, context_embedding)
            scored_diffs.append(scored)
            
        # Filter by threshold
        above_threshold = [
            sd for sd in scored_diffs 
            if sd.saliency_score >= threshold
        ]
        
        # Sort by score descending and take top N
        sorted_diffs = sorted(above_threshold, key=lambda x: x.saliency_score, reverse=True)
        kept_diffs = sorted_diffs[:max_diffs]
        
        # Build result dict
        filtered = {sd.file_path: sd.diff_content for sd in kept_diffs}
        
        # Build metadata
        metadata = {
            "enabled": True,
            "total": len(diffs),
            "kept": len(kept_diffs),
            "threshold": threshold,
            "scores": {
                sd.file_path: round(sd.saliency_score, 3) 
                for sd in kept_diffs
            },
            "filter_stats": {
                "above_threshold": len(above_threshold),
                "below_threshold": len(diffs) - len(above_threshold),
                "truncated": len(above_threshold) > max_diffs,
            }
        }
        
        logger.info(
            "diffs_filtered",
            total=len(diffs),
            kept=len(kept_diffs),
            threshold=threshold
        )
        
        return filtered, metadata

    def extract_salient_summary(self, diffs: dict[str, str], max_files: int = 5) -> str:
        """Extract a summary of salient changes.
        
        Args:
            diffs: Dict of file_path -> diff_content
            max_files: Maximum files to include in summary
            
        Returns:
            Summary string for storage
        """
        if not diffs:
            return ""
            
        files = list(diffs.keys())[:max_files]
        lines = ["Key changes in this request:"]
        
        for file_path in files:
            diff_content = diffs[file_path]
            # Count additions and deletions
            additions = len([l for l in diff_content.split("\n") if l.startswith("+") and not l.startswith("+++")])
            deletions = len([l for l in diff_content.split("\n") if l.startswith("-") and not l.startswith("---")])
            
            lines.append(f"  - {file_path}: +{additions}/-{deletions}")
            
        return "\n".join(lines)


# Singleton filter instance for convenience
diff_filter = SalientDiffFilter()
