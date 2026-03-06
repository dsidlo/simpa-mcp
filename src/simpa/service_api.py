"""Direct service API for SIMPA - no MCP transport. (for pi extension integration)

This module provides async functions that can be called directly from
both the MCP server and the JSON-RPC server. It contains all the business
logic without any transport-specific code.
"""

import hashlib
import re
import uuid
from datetime import datetime
from typing import Any

from simpa.config import settings
from simpa.db.engine import AsyncSessionLocal
from simpa.db.repository import (
    ProjectRepository,
    PromptHistoryRepository,
    RefinedPromptRepository,
)
from simpa.embedding.service import EmbeddingService
from simpa.llm.service import LLMService
from simpa.prompts.refiner import PromptRefiner
from simpa.core.diff_saliency import SalientDiffFilter
from simpa.utils.logging import get_logger

logger = get_logger(__name__)

# PII Detection & Sanitization
PII_PATTERNS = {
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b\+?\d{1,4}?[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b",
    "api_key": r"(?i)(api[_-]?key\s*=\s*['\"][^'\"]+)",
    "password": r"(?i)(password\s*=\s*['\"][^'\"]+)",
    "secret": r"(?i)(secret\s*=\s*['\"][^'\"]+)",
}


def sanitize_pii(text: str) -> tuple[str, dict[str, int]]:
    """Detect and sanitize PII in text.

    Returns:
        Tuple of (sanitized_text, detected_entities)
    """
    detected = {}
    sanitized = text

    for entity_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            detected[entity_type] = len(matches)
            sanitized = re.sub(pattern, f"[{entity_type.upper()}_REDACTED]", sanitized)

    return sanitized, detected


def should_block_request(detected: dict[str, int]) -> tuple[bool, str]:
    """Check if request should be blocked due to high-risk PII."""
    high_risk = {"credit_card", "ssn", "api_key", "password", "secret"}
    blocks = set(detected.keys()) & high_risk

    if blocks:
        return True, f"High-risk PII detected: {', '.join(blocks)}. Request blocked."
    return False, ""


def compute_hash(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode()).hexdigest()


async def refine_prompt(
    agent_type: str,
    original_prompt: str,
    project_id: str | None = None,
    context: dict[str, Any] | None = None,
    main_language: str | None = None,
    other_languages: list[str] | None = None,
    domain: str | None = None,
    tags: list[str] | None = None,
    embedding_service: EmbeddingService | None = None,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """Refine a prompt before sending to an agent.

    Given an original prompt and context, either selects an existing refined prompt
    or creates a new one optimized for the agent type and language.

    Args:
        agent_type: Type of agent (e.g., "developer", "architect")
        original_prompt: The original prompt text
        project_id: Optional project ID to associate with this prompt
        context: Optional context dictionary
        main_language: Primary programming language
        other_languages: Additional programming languages
        domain: Domain category
        tags: List of tags
        embedding_service: Optional embedding service instance
        llm_service: Optional LLM service instance

    Returns:
        Dictionary with refined_prompt, prompt_key, source, action, etc.
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        agent_type=agent_type,
        main_language=main_language,
    )
    log.info("refine_prompt_called")

    # Validate agent_type format
    if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", agent_type):
        raise ValueError(
            "agent_type must start with a letter and contain only alphanumeric "
            "characters, underscores, and hyphens"
        )

    # Validate project_id if provided
    project_uuid = None
    if project_id:
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            raise ValueError("project_id must be a valid UUID")

    # Check for high-risk PII
    if settings.enable_pii_detection:
        _, detected = sanitize_pii(original_prompt)
        should_block, message = should_block_request(detected)
        if should_block:
            raise ValueError(message)

    async with AsyncSessionLocal() as session:
        try:
            # Sanitize prompt (log detection but allow through if not high-risk)
            sanitized_prompt, detected_pii = sanitize_pii(original_prompt)
            if detected_pii:
                log.warning("pii_detected", entities=list(detected_pii.keys()))

            # Check for project_id if strictly required
            if settings.require_project_id and not project_id:
                log.warning("refine_prompt_no_project_id_required")
                # Get list of existing projects to help the agent
                project_repo = ProjectRepository(session)
                projects, _ = await project_repo.list_projects(limit=5)
                project_list = [
                    {
                        "project_id": str(p.id),
                        "project_name": p.project_name,
                        "main_language": p.main_language,
                    }
                    for p in projects
                ]

                if not project_list:
                    return {
                        "refined_prompt": (
                            "ERROR: No project_id provided and no projects exist. "
                            "Please create a project first using create_project, "
                            "then resubmit your request with the project_id."
                        ),
                        "prompt_key": str(uuid.uuid4()),
                        "source": "new",
                        "action": "new",
                        "confidence_score": 0.0,
                        "similar_prompts_found": 0,
                        "average_score": None,
                        "usage_count": 0,
                    }
                else:
                    project_list_text = "\n".join([
                        f"  - {p['project_name']} (ID: {p['project_id']}, Language: {p.get('main_language', 'N/A')})"
                        for p in project_list
                    ])
                    return {
                        "refined_prompt": (
                            f"ERROR: No project_id provided. Please either:\n\n"
                            f"1. Use an existing project from the list below:\n{project_list_text}\n\n"
                            f"Or create a new project using create_project, then resubmit with the project_id."
                        ),
                        "prompt_key": str(uuid.uuid4()),
                        "source": "new",
                        "action": "new",
                        "confidence_score": 0.0,
                        "similar_prompts_found": 0,
                        "average_score": None,
                        "usage_count": 0,
                    }

            # Initialize services if not provided
            embedding_svc = embedding_service or EmbeddingService()
            llm_svc = llm_service or LLMService()

            # Create repository and refiner
            repository = RefinedPromptRepository(session)
            refiner = PromptRefiner(
                repository=repository,
                embedding_service=embedding_svc,
                llm_service=llm_svc,
            )

            # Compute hash of original prompt for deduplication
            original_hash = compute_hash(original_prompt)

            # Perform refinement
            result = await refiner.refine(
                original_prompt=sanitized_prompt,
                agent_type=agent_type,
                main_language=main_language,
                other_languages=other_languages,
                domain=domain,
                tags=tags,
                original_hash=original_hash,
                context=context,
                project_id=project_uuid,
            )

            await session.commit()

            log.info(
                "refine_prompt_completed",
                source=result["source"],
                prompt_key=result["prompt_key"],
            )

            return {
                "refined_prompt": result["refined_prompt"],
                "prompt_key": result["prompt_key"],
                "source": result["source"],
                "action": result["action"],
                "confidence_score": result.get("confidence_score"),
                "similar_prompts_found": result.get("similar_prompts_found", 0),
                "average_score": result.get("average_score"),
                "usage_count": result.get("usage_count"),
            }

        except Exception as e:
            await session.rollback()
            log.error("refine_prompt_failed", error=str(e))
            raise

        finally:
            # Cleanup services if we created them
            if embedding_service is None and embedding_svc:
                embedding_svc.close()
            if llm_service is None and llm_svc:
                llm_svc.close()


async def update_prompt_results(
    prompt_key: str,
    action_score: float,
    files_modified: list[str] | None = None,
    files_added: list[str] | None = None,
    files_deleted: list[str] | None = None,
    diffs: dict[str, Any] | None = None,
    validation_results: dict[str, Any] | None = None,
    executed_by_agent: str | None = None,
    execution_duration_ms: int | None = None,
    test_passed: bool | None = None,
    lint_score: float | None = None,
    security_scan_passed: bool | None = None,
) -> dict[str, Any]:
    """Update prompt performance metrics after agent execution.

    Records the outcome of using a refined prompt and updates
    the prompt's statistics for future refinement decisions.

    Args:
        prompt_key: The UUID of the prompt to update
        action_score: Score from 1.0 to 5.0
        files_modified: List of files modified
        files_added: List of files added
        files_deleted: List of files deleted
        diffs: Diff content per file
        validation_results: Validation results dictionary
        executed_by_agent: Name of the agent that executed the prompt
        execution_duration_ms: Execution duration in milliseconds
        test_passed: Whether tests passed
        lint_score: Lint score from 0.0 to 1.0
        security_scan_passed: Whether security scan passed

    Returns:
        Dictionary with success, usage_count, average_score, last_used_at
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        prompt_key=prompt_key,
        score=action_score,
    )
    log.info("update_result_called")

    # Validate prompt_key
    try:
        prompt_uuid = uuid.UUID(prompt_key)
    except ValueError:
        raise ValueError("prompt_key must be a valid UUID")

    async with AsyncSessionLocal() as session:
        try:
            # Get the prompt
            repository = RefinedPromptRepository(session)
            prompt = await repository.get_by_prompt_key(prompt_uuid)

            if not prompt:
                raise ValueError(f"Prompt not found: {prompt_key}")

            # Update prompt statistics
            await repository.update_stats(
                prompt_key=prompt_uuid,
                score=action_score,
            )

            # Apply diff saliency filtering
            diff_filter = SalientDiffFilter()
            filtered_diffs = diffs or {}
            saliency_metadata = None

            if diffs:
                # Get context embedding if available
                context_embedding = None
                # Filter diffs
                filtered_diffs, saliency_metadata = await diff_filter.filter_diffs(
                    diffs,
                    context_embedding=context_embedding,
                )

            # Create history record
            history_repo = PromptHistoryRepository(session)
            await history_repo.create(
                prompt_id=prompt.id,
                action_score=action_score,
                request_id=uuid.UUID(trace_id),
                executed_by_agent=executed_by_agent,
                files_modified=files_modified,
                files_added=files_added,
                files_deleted=files_deleted,
                diffs=filtered_diffs,
                test_passed=test_passed,
                lint_score=lint_score,
                security_scan_passed=security_scan_passed,
                execution_duration_ms=execution_duration_ms,
                validation_results=validation_results,
                saliency_metadata=saliency_metadata,
                project_id=prompt.project_id,
            )

            await session.commit()

            log.info(
                "update_result_completed",
                prompt_id=prompt.id,
                usage_count=prompt.usage_count,
                average_score=prompt.average_score,
            )

            return {
                "success": True,
                "usage_count": prompt.usage_count,
                "average_score": prompt.average_score,
                "last_used_at": prompt.last_used_at.isoformat() if prompt.last_used_at else None,
            }

        except Exception as e:
            await session.rollback()
            log.error("update_result_failed", error=str(e))
            raise


async def create_project(
    project_name: str,
    description: str | None = None,
    main_language: str | None = None,
    other_languages: list[str] | None = None,
    library_dependencies: list[str] | None = None,
    project_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new project for organizing prompts.

    Args:
        project_name: Name of the project
        description: Optional description
        main_language: Primary programming language
        other_languages: Additional programming languages
        library_dependencies: List of library dependencies
        project_structure: Project structure hints (src_dirs, test_dirs, etc.)

    Returns:
        Dictionary with project_id, project_name, created_at, etc.
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        project_name=project_name,
        main_language=main_language,
    )
    log.info("create_project_called")

    # Validate project_name format
    if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", project_name):
        raise ValueError(
            "project_name must start with a letter and contain only alphanumeric "
            "characters, underscores, and hyphens"
        )

    async with AsyncSessionLocal() as session:
        try:
            # Check for duplicate project name first
            repo = ProjectRepository(session)
            existing = await repo.get_by_name(project_name)
            if existing:
                raise ValueError(f"Project with name '{project_name}' already exists")

            # Sanitize description if provided
            sanitized_description = None
            if description:
                sanitized_description, detected_pii = sanitize_pii(description)
                if detected_pii:
                    log.warning("pii_detected_in_description", entities=list(detected_pii.keys()))

            # Create the project
            project = await repo.create(
                project_name=project_name,
                description=description,
                main_language=main_language,
                other_languages=other_languages,
                library_dependencies=library_dependencies,
                project_structure=project_structure,
            )

            await session.commit()

            log.info(
                "create_project_completed",
                project_id=str(project.id),
            )

            return {
                "project_id": str(project.id),
                "project_name": project.project_name,
                "created_at": project.created_at.isoformat(),
                "description": project.description,
                "success": True,
            }

        except Exception as e:
            await session.rollback()
            log.error("create_project_failed", error=str(e))
            raise


async def get_project(
    project_id: str | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    """Retrieve project information by ID or name.

    Args:
        project_id: UUID of the project
        project_name: Name of the project

    Returns:
        Dictionary with project details

    Raises:
        ValueError: If neither project_id nor project_name provided, or project not found
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        project_id=project_id,
        project_name=project_name,
    )
    log.info("get_project_called")

    if not project_id and not project_name:
        raise ValueError("Either project_id or project_name must be provided")

    async with AsyncSessionLocal() as session:
        try:
            repo = ProjectRepository(session)

            # Find project by ID or name
            if project_id:
                try:
                    project_uuid = uuid.UUID(project_id)
                    project = await repo.get_by_id(project_uuid)
                except ValueError:
                    raise ValueError("project_id must be a valid UUID")
            else:
                project = await repo.get_by_name(project_name)

            if not project:
                raise ValueError("Project not found")

            # Count associated prompts
            prompt_count = len(project.prompts) if project.prompts else 0

            log.info(
                "get_project_completed",
                project_id=str(project.id),
                prompt_count=prompt_count,
            )

            return {
                "project_id": str(project.id),
                "project_name": project.project_name,
                "description": project.description,
                "main_language": project.main_language,
                "other_languages": project.other_languages,
                "library_dependencies": project.library_dependencies,
                "project_structure": project.project_structure,
                "prompt_count": prompt_count,
                "project_created_at": project.created_at.isoformat(),
                "project_updated_at": project.updated_at.isoformat() if project.updated_at else None,
            }

        except Exception as e:
            log.error("get_project_failed", error=str(e))
            raise


async def list_projects(
    main_language: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List all projects with optional filtering.

    Args:
        main_language: Filter by programming language
        limit: Maximum number of results (default 50)
        offset: Pagination offset (default 0)

    Returns:
        Dictionary with projects list, total_count, limit, offset
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        main_language=main_language,
        limit=limit,
        offset=offset,
    )
    log.info("list_projects_called")

    async with AsyncSessionLocal() as session:
        try:
            repo = ProjectRepository(session)

            projects, total_count = await repo.list_projects(
                main_language=main_language,
                limit=limit,
                offset=offset,
            )

            # Build summaries
            project_summaries = []
            for project in projects:
                project_summaries.append({
                    "project_id": str(project.id),
                    "project_name": project.project_name,
                    "description": project.description,
                    "main_language": project.main_language,
                    "prompt_count": len(project.prompts) if project.prompts else 0,
                    "project_created_at": project.created_at.isoformat(),
                    "project_structure": project.project_structure,
                })

            log.info(
                "list_projects_completed",
                returned_count=len(project_summaries),
                total_count=total_count,
            )

            return {
                "projects": project_summaries,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            log.error("list_projects_failed", error=str(e))
            raise


async def activate_prompt(prompt_key: str) -> dict[str, Any]:
    """Activate a previously deactivated prompt.

    Args:
        prompt_key: UUID of the prompt to activate

    Returns:
        Dictionary with success, prompt_key, is_active, message
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        prompt_key=prompt_key,
    )
    log.info("activate_prompt_called")

    # Validate prompt_key
    try:
        prompt_uuid = uuid.UUID(prompt_key)
    except ValueError:
        raise ValueError("prompt_key must be a valid UUID")

    async with AsyncSessionLocal() as session:
        try:
            # Get the prompt
            repository = RefinedPromptRepository(session)
            prompt = await repository.get_by_prompt_key(prompt_uuid)

            if not prompt:
                raise ValueError(f"Prompt not found: {prompt_key}")

            # Activate the prompt
            if prompt.is_active:
                return {
                    "success": True,
                    "prompt_key": prompt_key,
                    "is_active": True,
                    "message": "Prompt was already active",
                }

            prompt.is_active = True
            await session.flush()
            await session.commit()

            log.info(
                "activate_prompt_completed",
                prompt_id=str(prompt.id),
            )

            return {
                "success": True,
                "prompt_key": prompt_key,
                "is_active": True,
                "message": "Prompt activated successfully",
            }

        except Exception as e:
            await session.rollback()
            log.error("activate_prompt_failed", error=str(e))
            raise


async def deactivate_prompt(prompt_key: str) -> dict[str, Any]:
    """Deactivate a prompt so it won't be used in searches.

    Args:
        prompt_key: UUID of the prompt to deactivate

    Returns:
        Dictionary with success, prompt_key, is_active, message
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        prompt_key=prompt_key,
    )
    log.info("deactivate_prompt_called")

    # Validate prompt_key
    try:
        prompt_uuid = uuid.UUID(prompt_key)
    except ValueError:
        raise ValueError("prompt_key must be a valid UUID")

    async with AsyncSessionLocal() as session:
        try:
            # Get the prompt
            repository = RefinedPromptRepository(session)
            prompt = await repository.get_by_prompt_key(prompt_uuid)

            if not prompt:
                raise ValueError(f"Prompt not found: {prompt_key}")

            # Deactivate the prompt
            if not prompt.is_active:
                return {
                    "success": True,
                    "prompt_key": prompt_key,
                    "is_active": False,
                    "message": "Prompt was already inactive",
                }

            prompt.is_active = False
            await session.flush()
            await session.commit()

            log.info(
                "deactivate_prompt_completed",
                prompt_id=str(prompt.id),
            )

            return {
                "success": True,
                "prompt_key": prompt_key,
                "is_active": False,
                "message": "Prompt deactivated successfully",
            }

        except Exception as e:
            await session.rollback()
            log.error("deactivate_prompt_failed", error=str(e))
            raise


async def health_check() -> dict[str, Any]:
    """Health check endpoint.

    Returns:
        Dictionary with status, service, version, timestamp
    """
    return {
        "status": "healthy",
        "service": "simpa-mcp",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }
