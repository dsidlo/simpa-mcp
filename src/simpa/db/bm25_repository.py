"""BM25 repository for keyword-based search in PostgreSQL."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from simpa.config import settings
from simpa.db.models import RefinedPrompt
from simpa.utils.logging import get_logger, log_trace

logger = get_logger(__name__)


@dataclass
class HybridSearchResult:
    """Result container for hybrid search."""
    vector_results: list[RefinedPrompt]
    bm25_results: list[RefinedPrompt]
    combined: list[RefinedPrompt]
    bm25_scores: dict[uuid.UUID, float]


class BM25Repository:
    """Repository for BM25 keyword search operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query_text: str,
        agent_type: str | None = None,
        limit: int = 5,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> tuple[list[RefinedPrompt], dict[uuid.UUID, float]]:
        """Search for prompts using BM25 keyword scoring.
        
        Args:
            query_text: The search query text
            agent_type: Optional agent type filter
            limit: Maximum number of results
            k1: BM25 k1 parameter (term saturation)
            b: BM25 b parameter (document length normalization)
            
        Returns:
            Tuple of (prompts list, score dictionary mapping prompt_id to bm25_score)
        """
        log_trace(
            logger,
            "bm25_search_enter",
            query_length=len(query_text),
            agent_type=agent_type,
            limit=limit,
            k1=k1,
            b=b,
        )
        
        # Call the BM25 search function
        query = text("""
            SELECT * FROM bm25_search(
                :query_text,
                :agent_type,
                :limit_count,
                :k1,
                :b
            )
        """)
        
        result = await self.session.execute(
            query,
            {
                "query_text": query_text,
                "agent_type": agent_type,
                "limit_count": limit,
                "k1": k1,
                "b": b,
            }
        )
        
        prompts = []
        scores: dict[uuid.UUID, float] = {}
        
        for row in result.mappings():
            # Create a RefinedPrompt from the result
            prompt_data = {
                "id": row["prompt_id"],
                "prompt_key": row["prompt_key"],
                "original_prompt": row["original_prompt"],
                "refined_prompt": row["refined_prompt"],
                "agent_type": row["agent_type"],
                "average_score": row["average_score"],
                "usage_count": row["usage_count"],
            }
            prompt = RefinedPrompt(**prompt_data)
            prompts.append(prompt)
            scores[row["prompt_key"]] = row["bm25_score_result"]
        
        log_trace(
            logger,
            "bm25_search_complete",
            results_found=len(prompts),
            scores=list(scores.values()) if scores else [],
        )
        
        return prompts, scores

    async def index_prompt(
        self,
        prompt_id: uuid.UUID,
        original_prompt: str,
        refined_prompt: str,
    ) -> None:
        """Index a prompt for BM25 search.
        
        Args:
            prompt_id: The UUID of the prompt
            original_prompt: Original prompt text
            refined_prompt: Refined prompt text
        """
        log_trace(
            logger,
            "bm25_index_prompt_enter",
            prompt_id=str(prompt_id),
            original_length=len(original_prompt),
            refined_length=len(refined_prompt),
        )
        
        query = text("CALL bm25_index_prompt(:prompt_id, :original, :refined)")
        
        await self.session.execute(
            query,
            {
                "prompt_id": prompt_id,
                "original": original_prompt,
                "refined": refined_prompt,
            }
        )
        
        log_trace(logger, "bm25_index_prompt_complete", prompt_id=str(prompt_id))

    async def update_collection_stats(self) -> None:
        """Update BM25 collection statistics (IDF values)."""
        log_trace(logger, "bm25_update_stats_enter")
        
        query = text("CALL bm25_update_stats()")
        await self.session.execute(query)
        
        log_trace(logger, "bm25_update_stats_complete")

    async def find_hybrid(
        self,
        embedding: list[float],
        query_text: str,
        agent_type: str,
        vector_limit: int = 5,
        bm25_limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> HybridSearchResult:
        """Find similar prompts using both vector and BM25 search.
        
        Args:
            embedding: Vector embedding for semantic search
            query_text: Query text for BM25 search
            agent_type: Agent type filter
            vector_limit: Maximum vector results
            bm25_limit: Maximum BM25 results
            similarity_threshold: Minimum similarity for vector search
            
        Returns:
            HybridSearchResult with vector, BM25, and combined results
        """
        from simpa.db.repository import RefinedPromptRepository
        
        log_trace(
            logger,
            "find_hybrid_enter",
            query_length=len(query_text),
            agent_type=agent_type,
            vector_limit=vector_limit,
            bm25_limit=bm25_limit,
        )
        
        # Get vector results using existing repository
        vector_repo = RefinedPromptRepository(self.session)
        
        vector_results = await vector_repo.find_similar(
            embedding=embedding,
            agent_type=agent_type,
            limit=vector_limit,
            similarity_threshold=similarity_threshold,
        )
        
        log_trace(
            logger,
            "find_hybrid_vector_complete",
            vector_count=len(vector_results),
            vector_ids=[str(v.prompt_key) for v in vector_results],
        )
        
        # Get BM25 results
        bm25_results, bm25_scores = await self.search(
            query_text=query_text,
            agent_type=agent_type,
            limit=bm25_limit,
            k1=settings.bm25_k1,
            b=settings.bm25_b,
        )
        
        log_trace(
            logger,
            "find_hybrid_bm25_complete",
            bm25_count=len(bm25_results),
            bm25_ids=[str(b.prompt_key) for b in bm25_results],
            bm25_scores=bm25_scores,
        )
        
        # Combine and deduplicate results
        seen_keys: set[uuid.UUID] = set()
        combined: list[RefinedPrompt] = []
        
        # Add vector results first
        for prompt in vector_results:
            if prompt.prompt_key not in seen_keys:
                seen_keys.add(prompt.prompt_key)
                combined.append(prompt)
        
        # Add BM25 results that aren't already included
        for prompt in bm25_results:
            if prompt.prompt_key not in seen_keys:
                seen_keys.add(prompt.prompt_key)
                combined.append(prompt)
        
        log_trace(
            logger,
            "find_hybrid_complete",
            total_results=len(combined),
            vector_count=len(vector_results),
            bm25_count=len(bm25_results),
            unique_count=len(combined),
        )
        
        return HybridSearchResult(
            vector_results=vector_results,
            bm25_results=bm25_results,
            combined=combined,
            bm25_scores=bm25_scores,
        )


async def get_bm25_repository(session: AsyncSession) -> BM25Repository:
    """Factory function to get BM25 repository."""
    return BM25Repository(session)
