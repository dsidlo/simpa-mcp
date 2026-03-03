"""FastMCP server for SIMPA service."""

import hashlib
import re
import structlog
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field, field_validator

from simpa.config import settings
from simpa.db.engine import AsyncSessionLocal, get_db_session
from simpa.db.repository import PromptHistoryRepository, RefinedPromptRepository
from simpa.embedding.service import EmbeddingService
from simpa.llm.service import LLMService
from simpa.prompts.refiner import PromptRefiner
from simpa.core.diff_saliency import SalientDiffFilter

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.json_logging else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


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


# Pydantic models for request/response validation
class RefinePromptRequest(BaseModel):
    """Request to refine a prompt."""
    agent_type: str = Field(..., min_length=1, max_length=100)
    original_prompt: str = Field(..., min_length=10, max_length=settings.max_prompt_length)
    context: dict[str, Any] | None = Field(default=None)
    main_language: str | None = Field(default=None, max_length=50)
    other_languages: list[str] | None = Field(default=None, max_length=10)
    domain: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=20)
    
    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", v):
            raise ValueError("agent_type must start with a letter and contain only alphanumeric characters, underscores, and hyphens")
        return v
    
    @field_validator("original_prompt")
    @classmethod
    def validate_no_pii(cls, v: str) -> str:
        """Check for high-risk PII in prompt."""
        if settings.enable_pii_detection:
            _, detected = sanitize_pii(v)
            should_block, message = should_block_request(detected)
            if should_block:
                raise ValueError(message)
        return v


class RefinePromptResponse(BaseModel):
    """Response from prompt refinement."""
    refined_prompt: str
    prompt_key: str
    source: str = Field(..., pattern="^(new|reused|refined)$")
    confidence_score: float | None = None
    similar_prompts_found: int = 0
    average_score: float | None = None
    usage_count: int | None = None


class UpdatePromptResultsRequest(BaseModel):
    """Request to update prompt results."""
    prompt_key: str
    action_score: float = Field(..., ge=1.0, le=5.0)
    files_modified: list[str] | None = Field(default=None, max_length=100)
    files_added: list[str] | None = Field(default=None, max_length=100)
    files_deleted: list[str] | None = Field(default=None, max_length=100)
    diffs: dict[str, Any] | None = Field(default=None)
    validation_results: dict[str, Any] | None = Field(default=None)
    executed_by_agent: str | None = Field(default=None, max_length=100)
    execution_duration_ms: int | None = Field(default=None)
    test_passed: bool | None = Field(default=None)
    lint_score: float | None = Field(default=None, ge=0.0, le=1.0)
    security_scan_passed: bool | None = Field(default=None)
    
    @field_validator("prompt_key")
    @classmethod
    def validate_prompt_key(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("prompt_key must be a valid UUID")
        return v


class UpdatePromptResultsResponse(BaseModel):
    """Response from updating prompt results."""
    success: bool
    usage_count: int
    average_score: float
    last_used_at: str | None = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    timestamp: str


# Lifespan context for MCP server
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage application lifecycle."""
    logger.info("simpa_server_starting")
    
    # Initialize services
    embedding_service = EmbeddingService()
    llm_service = LLMService()
    
    yield {
        "embedding_service": embedding_service,
        "llm_service": llm_service,
    }
    
    # Cleanup
    await embedding_service.close()
    await llm_service.close()
    logger.info("simpa_server_stopped")


# Create FastMCP server
mcp = FastMCP(
    "simpa",
    lifespan=app_lifespan,
    instructions="SIMPA - Self-Improving Meta Prompt Agent. Refine prompts before agent execution.",
)


@mcp.tool()
async def refine_prompt(
    request: RefinePromptRequest,
    ctx: Context,
) -> RefinePromptResponse:
    """Refine a prompt before sending to an agent.
    
    Given an original prompt and context, either selects an existing refined prompt
    or creates a new one optimized for the agent type and language.
    
    Args:
        request: Refinement request with prompt details
        
    Returns:
        Refined or selected prompt with metadata
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        agent_type=request.agent_type,
        main_language=request.main_language,
    )
    log.info("refine_prompt_called")
    
    async with AsyncSessionLocal() as session:
        try:
            # Sanitize prompt (log detection but allow through if not high-risk)
            sanitized_prompt, detected_pii = sanitize_pii(request.original_prompt)
            if detected_pii:
                log.warning("pii_detected", entities=list(detected_pii.keys()))
            
            # Get services from lifespan context
            embedding_service = ctx.request_context.lifespan_context["embedding_service"]
            llm_service = ctx.request_context.lifespan_context["llm_service"]
            
            # Create repository and refiner
            repository = RefinedPromptRepository(session)
            refiner = PromptRefiner(
                repository=repository,
                embedding_service=embedding_service,
                llm_service=llm_service,
            )
            
            # Compute hash of original prompt for deduplication
            original_hash = compute_hash(request.original_prompt)
            
            # Perform refinement
            result = await refiner.refine(
                original_prompt=sanitized_prompt,
                agent_type=request.agent_type,
                main_language=request.main_language,
                other_languages=request.other_languages,
                domain=request.domain,
                tags=request.tags,
                original_hash=original_hash,
                context=request.context,
            )
            
            await session.commit()
            
            log.info(
                "refine_prompt_completed",
                source=result["source"],
                prompt_key=result["prompt_key"],
            )
            
            return RefinePromptResponse(
                refined_prompt=result["refined_prompt"],
                prompt_key=result["prompt_key"],
                source=result["source"],
                confidence_score=result.get("confidence_score"),
                similar_prompts_found=result.get("similar_prompts_found", 0),
                average_score=result.get("average_score"),
                usage_count=result.get("usage_count"),
            )
            
        except Exception as e:
            await session.rollback()
            log.error("refine_prompt_failed", error=str(e))
            raise


@mcp.tool()
async def update_prompt_results(
    request: UpdatePromptResultsRequest,
    ctx: Context,
) -> UpdatePromptResultsResponse:
    """Update prompt performance metrics after agent execution.
    
    Records the outcome of using a refined prompt and updates
    the prompt's statistics for future refinement decisions.
    
    Args:
        request: Update request with prompt key and results
        
    Returns:
        Updated statistics
    """
    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        prompt_key=request.prompt_key,
        score=request.action_score,
    )
    log.info("update_result_called")
    
    async with AsyncSessionLocal() as session:
        try:
            # Parse prompt key
            prompt_uuid = uuid.UUID(request.prompt_key)
            
            # Get the prompt
            repository = RefinedPromptRepository(session)
            prompt = await repository.get_by_prompt_key(prompt_uuid)
            
            if not prompt:
                raise ValueError(f"Prompt not found: {request.prompt_key}")
            
            # Update prompt statistics
            await repository.update_stats(
                prompt_key=prompt_uuid,
                score=request.action_score,
            )
            
            # Apply diff saliency filtering
            diff_filter = SalientDiffFilter()
            filtered_diffs = request.diffs or {}
            saliency_metadata = None
            
            if request.diffs:
                from simpa.embedding.service import EmbeddingService
                embedding_service = ctx.request_context.lifespan_context["embedding_service"]
                # Get context embedding if available
                context_embedding = None
                # Filter diffs
                filtered_diffs, saliency_metadata = await diff_filter.filter_diffs(
                    request.diffs,
                    context_embedding=context_embedding
                )
            
            # Create history record
            history_repo = PromptHistoryRepository(session)
            await history_repo.create(
                prompt_id=prompt.id,
                action_score=request.action_score,
                request_id=uuid.UUID(trace_id),
                executed_by_agent=request.executed_by_agent,
                files_modified=request.files_modified,
                files_added=request.files_added,
                files_deleted=request.files_deleted,
                diffs=filtered_diffs,
                test_passed=request.test_passed,
                lint_score=request.lint_score,
                security_scan_passed=request.security_scan_passed,
                execution_duration_ms=request.execution_duration_ms,
                validation_results=request.validation_results,
                saliency_metadata=saliency_metadata,
            )
            
            await session.commit()
            
            log.info(
                "update_result_completed",
                prompt_id=prompt.id,
                usage_count=prompt.usage_count,
                average_score=prompt.average_score,
            )
            
            return UpdatePromptResultsResponse(
                success=True,
                usage_count=prompt.usage_count,
                average_score=prompt.average_score,
                last_used_at=prompt.last_used_at.isoformat() if prompt.last_used_at else None,
            )
            
        except Exception as e:
            await session.rollback()
            log.error("update_result_failed", error=str(e))
            raise


@mcp.tool()
async def health_check() -> HealthCheckResponse:
    """Health check endpoint.
    
    Returns:
        Service health status
    """
    return HealthCheckResponse(
        status="healthy",
        service="simpa-mcp",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
    )


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport=settings.mcp_transport)


if __name__ == "__main__":
    main()
