"""SQLAlchemy database models for SIMPA."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from simpa.config import settings


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map: dict[type, type] = {
        datetime: DateTime(timezone=True),
    }


class RefinedPrompt(Base):
    """Stores refined prompts with vector embeddings and statistics."""

    __tablename__ = "refined_prompts"

    # Primary key (UUID for external reference)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Public UUID for external reference (alias for id)
    prompt_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Embedding vector for similarity search
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=True,
    )

    # Classification fields
    agent_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    refinement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="sigmoid",
        server_default="sigmoid",
    )
    main_language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    other_languages: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    domain: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Prompt content
    original_prompt_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    original_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    refined_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    refinement_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Refinement chain (self-referential)
    prior_refinement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refined_prompts.id"),
        nullable=True,
    )

    # Project context (optional)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )
    project: Mapped["Project | None"] = relationship(
        "Project",
        back_populates="prompts",
    )
    prior_refinement: Mapped["RefinedPrompt"] = relationship(
        "RefinedPrompt",
        remote_side=[id],
        backref="subsequent_refinements",
    )

    # Performance statistics
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    average_score: Mapped[float] = mapped_column(
        default=0.0,
        server_default="0.0",
        nullable=False,
    )
    score_weighted: Mapped[float] = mapped_column(
        default=0.0,
        server_default="0.0",
        nullable=False,
    )

    # Score distribution histogram (1-5 bins)
    score_dist_1: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    score_dist_2: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    score_dist_3: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    score_dist_4: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    score_dist_5: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # Soft delete for audit trail
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Relationships
    history: Mapped[list["PromptHistory"]] = relationship(
        "PromptHistory",
        back_populates="refined_prompt",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def update_score_stats(self, new_score: float) -> None:
        """Update statistics with a new score.

        Args:
            new_score: Score between 1.0 and 5.0
        """
        # Update usage count
        self.usage_count += 1

        # Update running average
        self.average_score = (
            (self.average_score * (self.usage_count - 1)) + new_score
        ) / self.usage_count

        # Update weighted score (Bayesian-like approach)
        self.score_weighted = self.average_score

        # Update score distribution histogram
        score_bin = max(1, min(5, int(new_score)))
        if score_bin == 1:
            self.score_dist_1 += 1
        elif score_bin == 2:
            self.score_dist_2 += 1
        elif score_bin == 3:
            self.score_dist_3 += 1
        elif score_bin == 4:
            self.score_dist_4 += 1
        elif score_bin == 5:
            self.score_dist_5 += 1

        # Update last used timestamp
        self.last_used_at = datetime.now()

    def get_score_distribution(self) -> dict[str, int]:
        """Get score distribution as a dictionary."""
        return {
            "1": self.score_dist_1,
            "2": self.score_dist_2,
            "3": self.score_dist_3,
            "4": self.score_dist_4,
            "5": self.score_dist_5,
        }

    def __repr__(self) -> str:
        return (
            f"<RefinedPrompt(id={self.id}, prompt_key={self.prompt_key}, "
            f"agent_type={self.agent_type}, avg_score={self.average_score:.2f}, "
            f"usage={self.usage_count})>"
        )


class Project(Base):
    """Project for organizing prompts with context."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    # Note: tests expect 'description' not 'project_description'
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Language context
    main_language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    other_languages: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Dependencies
    library_dependencies: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Note: tests expect 'created_at' and 'updated_at' not 'project_created_at'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Soft delete
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    prompts: Mapped[list["RefinedPrompt"]] = relationship(
        "RefinedPrompt",
        back_populates="project",
        lazy="selectin",
    )
    history: Mapped[list["PromptHistory"]] = relationship(
        "PromptHistory",
        back_populates="project",
        lazy="selectin",
    )

    def __init__(self, **kwargs):
        """Initialize Project with defaults."""
        # Set defaults before calling super
        if "is_active" not in kwargs:
            kwargs["is_active"] = True
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.now()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.now()
        
        # Validate project_name is not None/empty
        project_name = kwargs.get("project_name")
        if project_name is None:
            raise ValueError("project_name cannot be None")
        if isinstance(project_name, str) and len(project_name) == 0:
            raise ValueError("project_name cannot be empty")
        
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<Project(id={self.id}, project_name={self.project_name}, "
            f"main_language={self.main_language})>"
        )


class PromptHistory(Base):
    """Records of prompt usage and outcomes."""

    __tablename__ = "prompt_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Project context (optional)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )
    project: Mapped["Project | None"] = relationship(
        "Project",
        back_populates="history",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Foreign key to the refined prompt
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refined_prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refined_prompt: Mapped["RefinedPrompt"] = relationship(
        "RefinedPrompt",
        back_populates="history",
    )

    # Execution context
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    executed_by_agent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Performance metrics
    action_score: Mapped[float] = mapped_column(
        nullable=False,
    )
    test_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    lint_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    security_scan_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # Files and diffs
    files_modified: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    files_added: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    files_deleted: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    diffs: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Execution metadata
    execution_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    agent_output_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    validation_results: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Diff saliency metadata
    saliency_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<PromptHistory(id={self.id}, prompt_id={self.prompt_id}, "
            f"score={self.action_score})>"
        )
