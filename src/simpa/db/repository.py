"""Data access layer for SIMPA database operations with optimization support."""

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from simpa.config import settings
from simpa.db.models import PromptHistory, RefinedPrompt


class RefinedPromptRepository:
    """Repository for RefinedPrompt operations with hash-based fast path."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        embedding: list[float] | None,
        agent_type: str,
        original_prompt: str,
        refined_prompt: str,
        main_language: str | None = None,
        other_languages: list[str] | None = None,
        domain: str | None = None,
        tags: list[str] | None = None,
        prior_refinement_id: int | None = None,
        original_prompt_hash: str | None = None,
        refinement_version: int = 1,
    ) -> RefinedPrompt:
        """Create a new refined prompt record."""
        prompt = RefinedPrompt(
            embedding=embedding,
            agent_type=agent_type,
            original_prompt=original_prompt,
            refined_prompt=refined_prompt,
            main_language=main_language,
            other_languages=other_languages or [],
            domain=domain,
            tags=tags or [],
            prior_refinement_id=prior_refinement_id,
            original_prompt_hash=original_prompt_hash,
            refinement_version=refinement_version,
        )
        # Increment refinement version if this is a refinement of an existing prompt
        if prior_refinement_id:
            # Get the prior prompt's version and increment
            prior = await self.get_by_id(prior_refinement_id)
            if prior:
                prompt.refinement_version = prior.refinement_version + 1

        self.session.add(prompt)
        await self.session.flush()
        await self.session.refresh(prompt)
        return prompt

    async def get_by_id(
        self, prompt_id: int
    ) -> RefinedPrompt | None:
        """Get a refined prompt by internal ID."""
        result = await self.session.execute(
            select(RefinedPrompt).where(RefinedPrompt.id == prompt_id)
        )
        return result.scalar_one_or_none()

    async def get_by_prompt_key(
        self, prompt_key: uuid.UUID
    ) -> RefinedPrompt | None:
        """Get a refined prompt by its public UUID key."""
        result = await self.session.execute(
            select(RefinedPrompt).where(RefinedPrompt.prompt_key == prompt_key)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_history(
        self, prompt_id: int
    ) -> RefinedPrompt | None:
        """Get a refined prompt with its history."""
        result = await self.session.execute(
            select(RefinedPrompt)
            .where(RefinedPrompt.id == prompt_id)
            .options(selectinload(RefinedPrompt.history))
        )
        return result.scalar_one_or_none()

    async def get_by_prompt_key_with_history(
        self, prompt_key: uuid.UUID
    ) -> RefinedPrompt | None:
        """Get a refined prompt by key with its history."""
        result = await self.session.execute(
            select(RefinedPrompt)
            .where(RefinedPrompt.prompt_key == prompt_key)
            .options(selectinload(RefinedPrompt.history))
        )
        return result.scalar_one_or_none()

    async def get_by_original_hash(
        self,
        original_hash: str,
        agent_type: str | None = None,
    ) -> RefinedPrompt | None:
        """Get a refined prompt by original prompt hash.
        
        Args:
            original_hash: Hash of the original prompt
            agent_type: Optional agent type filter
            
        Returns:
            RefinedPrompt if found, None otherwise
        """
        query = select(RefinedPrompt).where(
            RefinedPrompt.original_prompt_hash == original_hash
        )
        
        if agent_type:
            query = query.where(RefinedPrompt.agent_type == agent_type)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_best_by_hash(
        self,
        original_hash: str,
        agent_type: str | None = None,
        min_score: float = 4.0,
    ) -> RefinedPrompt | None:
        """Get best prompt by hash with score threshold.
        
        Args:
            original_hash: Hash of the original prompt
            agent_type: Optional agent type filter
            min_score: Minimum average score required
            
        Returns:
            RefinedPrompt if found with sufficient score, None otherwise
        """
        query = select(RefinedPrompt).where(
            RefinedPrompt.original_prompt_hash == original_hash,
            RefinedPrompt.average_score >= min_score,
            RefinedPrompt.usage_count > 0,
            RefinedPrompt.is_active == True,
        )
        
        if agent_type:
            query = query.where(RefinedPrompt.agent_type == agent_type)
        
        # Order by score descending
        query = query.order_by(RefinedPrompt.average_score.desc())
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_similar(
        self,
        embedding: list[float],
        agent_type: str,
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[RefinedPrompt]:
        """Find similar prompts by vector similarity.

        Uses cosine similarity for vector comparison.
        """
        # Use pgvector's cosine distance operator <=>
        # Lower distance = higher similarity
        distance_threshold = 1.0 - similarity_threshold

        result = await self.session.execute(
            select(RefinedPrompt)
            .where(RefinedPrompt.agent_type == agent_type)
            .where(RefinedPrompt.is_active == True)
            .where(RefinedPrompt.embedding.cosine_distance(embedding) <= distance_threshold)
            .order_by(RefinedPrompt.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_best_for_agent(
        self,
        agent_type: str,
        limit: int = 5,
    ) -> list[RefinedPrompt]:
        """Get the best performing prompts for an agent type."""
        result = await self.session.execute(
            select(RefinedPrompt)
            .where(RefinedPrompt.agent_type == agent_type)
            .where(RefinedPrompt.is_active == True)
            .where(RefinedPrompt.usage_count > 0)
            .order_by(RefinedPrompt.average_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_stats(
        self,
        prompt_key: uuid.UUID,
        score: float,
    ) -> RefinedPrompt | None:
        """Update prompt statistics with a new score."""
        prompt = await self.get_by_prompt_key(prompt_key)
        if prompt:
            prompt.update_score_stats(score)
            await self.session.flush()
            await self.session.refresh(prompt)
        return prompt

    async def soft_delete(
        self,
        prompt_key: uuid.UUID,
    ) -> bool:
        """Soft delete a prompt."""
        prompt = await self.get_by_prompt_key(prompt_key)
        if prompt:
            prompt.is_active = False
            await self.session.flush()
            return True
        return False


class PromptHistoryRepository:
    """Repository for PromptHistory operations with saliency support."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        prompt_id: int,
        action_score: float,
        request_id: uuid.UUID | None = None,
        executed_by_agent: str | None = None,
        files_modified: list[str] | None = None,
        files_added: list[str] | None = None,
        files_deleted: list[str] | None = None,
        diffs: dict[str, Any] | None = None,
        test_passed: bool | None = None,
        lint_score: float | None = None,
        security_scan_passed: bool | None = None,
        execution_duration_ms: int | None = None,
        agent_output_summary: str | None = None,
        validation_results: dict[str, Any] | None = None,
        saliency_metadata: dict[str, Any] | None = None,
    ) -> PromptHistory:
        """Create a new prompt history record with saliency metadata."""
        history = PromptHistory(
            prompt_id=prompt_id,
            action_score=action_score,
            request_id=request_id,
            executed_by_agent=executed_by_agent,
            files_modified=files_modified or [],
            files_added=files_added or [],
            files_deleted=files_deleted or [],
            diffs=diffs or {},
            test_passed=test_passed,
            lint_score=lint_score,
            security_scan_passed=security_scan_passed,
            execution_duration_ms=execution_duration_ms,
            agent_output_summary=agent_output_summary,
            validation_results=validation_results,
            saliency_metadata=saliency_metadata,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(history)
        return history

    async def get_by_prompt_id(
        self,
        prompt_id: int,
        limit: int = 100,
    ) -> list[PromptHistory]:
        """Get history records for a prompt."""
        result = await self.session.execute(
            select(PromptHistory)
            .where(PromptHistory.prompt_id == prompt_id)
            .order_by(PromptHistory.executed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_prompt_key(
        self,
        prompt_key: uuid.UUID,
        limit: int = 100,
    ) -> list[PromptHistory]:
        """Get history records for a prompt by its key."""
        # First get the prompt id
        prompt_result = await self.session.execute(
            select(RefinedPrompt.id).where(RefinedPrompt.prompt_key == prompt_key)
        )
        prompt_id = prompt_result.scalar_one_or_none()
        
        if not prompt_id:
            return []
        
        return await self.get_by_prompt_id(prompt_id, limit)

    async def create_with_filtered_diffs(
        self,
        prompt_id: int,
        action_score: float,
        diffs: dict[str, Any] | None = None,
        **kwargs
    ) -> PromptHistory:
        """Create history with diff saliency filtering applied.
        
        This method should be called by a service that has already
        filtered diffs using DiffSaliencyScorer.
        
        Args:
            prompt_id: The prompt ID
            action_score: The action score
            diffs: Raw diffs dict (will be stored as-is, filtering done externally)
            **kwargs: Additional fields for history record
            
        Returns:
            Created PromptHistory
        """
        return await self.create(
            prompt_id=prompt_id,
            action_score=action_score,
            diffs=diffs,
            **kwargs
        )
