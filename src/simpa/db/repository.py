"""Data access layer for SIMPA database operations with optimization support."""

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from simpa.config import settings
from simpa.db.models import PromptHistory, Project, RefinedPrompt


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
        project_id: uuid.UUID | None = None,
        refinement_type: str = "sigmoid",
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
            project_id=project_id,
            refinement_type=refinement_type,
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
        self, prompt_id: uuid.UUID
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
        self, prompt_id: uuid.UUID
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

    async def get_by_refined_text_hash(
        self,
        refined_text: str,
    ) -> RefinedPrompt | None:
        """Find exact match by refined prompt text using MD5 hash.
        
        Uses the functional MD5 hash index for O(1) exact matching.
        This prevents storing duplicate refined prompts.
        
        Args:
            refined_text: The exact refined prompt text to match
            
        Returns:
            Matching RefinedPrompt or None if not found
        """
        from sqlalchemy import func
        
        result = await self.session.execute(
            select(RefinedPrompt)
            .where(
                func.md5(RefinedPrompt.refined_prompt) == func.md5(refined_text)
            )
            .where(RefinedPrompt.is_active == True)
            .limit(1)
        )
        return result.scalar_one_or_none()

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


class ProjectRepository:
    """Repository for Project operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_name: str,
        description: str | None = None,
        main_language: str | None = None,
        other_languages: list[str] | None = None,
        library_dependencies: list[str] | None = None,
    ) -> Project:
        """Create a new project record."""
        project = Project(
            project_name=project_name,
            description=description,
            main_language=main_language,
            other_languages=other_languages or [],
            library_dependencies=library_dependencies or [],
        )
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get_by_id(
        self, project_id: uuid.UUID
    ) -> Project | None:
        """Get a project by internal ID."""
        result = await self.session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self, project_name: str
    ) -> Project | None:
        """Get a project by its unique name."""
        result = await self.session.execute(
            select(Project).where(Project.project_name == project_name)
        )
        return result.scalar_one_or_none()

    async def list_projects(
        self,
        main_language: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """List projects with optional filtering and pagination.
        
        Returns a tuple of (projects_list, total_count).
        """
        query = select(Project).where(Project.is_active == True)
        
        if main_language:
            query = query.where(Project.main_language == main_language)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(Project.created_at.desc())
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        projects = list(result.scalars().all())
        
        return projects, total_count

    async def update(
        self,
        project_id: uuid.UUID,
        description: str | None = None,
        main_language: str | None = None,
        other_languages: list[str] | None = None,
        library_dependencies: list[str] | None = None,
    ) -> Project | None:
        """Update a project record."""
        project = await self.get_by_id(project_id)
        if not project:
            return None
        
        if description is not None:
            project.description = description
        if main_language is not None:
            project.main_language = main_language
        if other_languages is not None:
            project.other_languages = other_languages
        if library_dependencies is not None:
            project.library_dependencies = library_dependencies
        
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def soft_delete(
        self,
        project_id: uuid.UUID,
    ) -> bool:
        """Soft delete a project."""
        project = await self.get_by_id(project_id)
        if project:
            project.is_active = False
            await self.session.flush()
            return True
        return False

    async def add_prompt(
        self,
        project_id: uuid.UUID,
        prompt_id: uuid.UUID,
    ) -> bool:
        """Add a prompt reference to a project.
        
        Args:
            project_id: UUID of the project
            prompt_id: UUID of the prompt to add
            
        Returns:
            True if successful, False otherwise
        """
        from simpa.db.models import RefinedPrompt
        
        project = await self.get_by_id(project_id)
        if not project:
            return False
        
        # Get the prompt
        result = await self.session.execute(
            select(RefinedPrompt).where(RefinedPrompt.id == prompt_id)
        )
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            return False
        
        # Associate prompt with project
        prompt.project_id = project_id
        await self.session.flush()
        return True

    async def list_all(self) -> list[Project]:
        """List all projects (no pagination).
        
        Returns:
            List of all projects
        """
        result = await self.session.execute(
            select(Project).order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[Project]:
        """List only active projects.
        
        Returns:
            List of active projects
        """
        result = await self.session.execute(
            select(Project)
            .where(Project.is_active == True)
            .order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())


class PromptHistoryRepository:
    """Repository for PromptHistory operations with saliency support."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        prompt_id: uuid.UUID,
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
        project_id: uuid.UUID | None = None,
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
            project_id=project_id,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(history)
        return history

    async def get_by_prompt_id(
        self,
        prompt_id: uuid.UUID,
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
        prompt_id: uuid.UUID,
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
