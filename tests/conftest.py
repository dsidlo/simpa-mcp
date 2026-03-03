"""Pytest configuration and fixtures for SIMPA tests."""

import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

from simpa.config import Settings
from simpa.db.models import Base, Project, PromptHistory, RefinedPrompt
from simpa.prompts.selector import PromptSelector


# -----------------------------------------------------------------------------
# Test Settings Fixture
# -----------------------------------------------------------------------------


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with overridden values."""
    return Settings(
        database_url="postgresql://test:test@localhost:5432/test",
        sigmoid_k=1.5,
        sigmoid_mu=3.0,
        min_refinement_probability=0.05,
        embedding_dimensions=768,
        vector_search_limit=5,
        vector_similarity_threshold=0.7,
        log_level="DEBUG",
        json_logging=False,
    )


# -----------------------------------------------------------------------------
# Database Fixtures
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def postgres_container() -> AsyncGenerator[PostgresContainer, None]:
    """Start PostgreSQL container with pgvector for tests."""
    # Skip if Docker is not available
    try:
        import subprocess
        subprocess.run(
            ["docker", "version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Docker not available - skipping DB tests", allow_module_level=True)
        return
    
    # Use official pgvector image
    container = PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="test",
        password="test",
        dbname="simpa_test",
    )
    container.start()
    
    # Wait for pgvector extension to be available
    import time
    time.sleep(3)  # Give more time for container startup
    
    yield container
    
    container.stop()


# Module-level cache for container URL to avoid recreating per test
_postgres_url_cache: str | None = None

@pytest.fixture(scope="session")
def postgres_url(postgres_container: PostgresContainer) -> str:
    """Get PostgreSQL connection URL - session scoped (synchronous, just returns string)."""
    global _postgres_url_cache
    if _postgres_url_cache is None:
        if not postgres_container:
            pytest.skip("PostgreSQL container not available")
        db_url = postgres_container.get_connection_url()
        _postgres_url_cache = db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    return _postgres_url_cache


@pytest_asyncio.fixture
async def db_engine(postgres_url: str):
    """Create async SQLAlchemy engine - function scoped for event loop isolation."""
    engine = create_async_engine(
        postgres_url,
        echo=False,
        future=True,
        # Use NullPool to ensure connections are closed after each test
        poolclass=None,
    )
    
    # Create/drop tables for each test to ensure isolation
    async with engine.connect() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Drop tables if they exist
        await conn.execute(text("DROP TABLE IF EXISTS projects CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS prompt_history CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS refined_prompts CASCADE"))
        await conn.commit()
    
    # Create tables fresh
    async with engine.begin() as conn:
        await conn.run_sync(lambda conn: Base.metadata.create_all(conn, checkfirst=False))
    
    yield engine
    
    # Cleanup immediately after test
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async_session = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        # Don't rollback - let the engine dispose handle cleanup


@pytest_asyncio.fixture
async def patch_async_session_local(db_engine):
    """Patch AsyncSessionLocal to use the test database engine."""
    from unittest.mock import patch
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    
    # Create a test session factory that uses our test engine
    test_session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Patch AsyncSessionLocal to use our test factory
    with patch('simpa.db.engine.AsyncSessionLocal', test_session_factory):
        with patch('simpa.mcp_server.AsyncSessionLocal', test_session_factory):
            with patch('simpa.db.repository.AsyncSessionLocal', test_session_factory):
                yield test_session_factory


# -----------------------------------------------------------------------------
# Mock Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """Create a mock embedding service."""
    service = MagicMock()
    service.embed = AsyncMock(return_value=[0.1] * 768)
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Create a mock LLM service."""
    service = MagicMock()
    service.complete = AsyncMock(return_value="Refined: This is a test prompt.")
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_context() -> MagicMock:
    """Create a mock MCP context."""
    context = MagicMock()
    context.request_context = MagicMock()
    # Set up mock services with AsyncMock for async methods
    embedding_service = MagicMock()
    embedding_service.embed = AsyncMock(return_value=[0.1] * 768)
    embedding_service.close = AsyncMock()
    
    llm_service = MagicMock()
    llm_service.complete = AsyncMock(return_value="Refined: This is a test prompt.")
    llm_service.close = AsyncMock()
    
    context.request_context.lifespan_context = {
        "embedding_service": embedding_service,
        "llm_service": llm_service,
    }
    return context


# -----------------------------------------------------------------------------
# PromptSelector Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def prompt_selector(test_settings: Settings) -> PromptSelector:
    """Create a PromptSelector with test settings."""
    selector = PromptSelector()
    selector.k = test_settings.sigmoid_k
    selector.mu = test_settings.sigmoid_mu
    selector.min_probability = test_settings.min_refinement_probability
    return selector


# -----------------------------------------------------------------------------
# Test Data Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_embedding() -> list[float]:
    """Return a sample 768-dimensional embedding vector."""
    return [0.1] * 768


@pytest.fixture
def sample_prompt_data() -> dict[str, Any]:
    """Return sample data for creating a RefinedPrompt."""
    return {
        "main_language": "python",
        "agent_type": "developer",
        "original_prompt": "Write a function to sort a list",
        "refined_prompt": "Refined: Write a Python function that takes a list of integers and returns a sorted list using an efficient algorithm.",
        "other_languages": ["bash"],
    }


@pytest_asyncio.fixture
async def sample_prompt(
    db_session: AsyncSession,
    sample_embedding: list[float],
    sample_prompt_data: dict[str, Any],
) -> RefinedPrompt:
    """Create and return a sample RefinedPrompt in the database."""
    prompt = RefinedPrompt(
        id=uuid.uuid4(),
        embedding=sample_embedding,
        **sample_prompt_data,
    )
    db_session.add(prompt)
    await db_session.flush()
    await db_session.refresh(prompt)
    return prompt


@pytest_asyncio.fixture
async def high_score_prompt(
    db_session: AsyncSession,
    sample_embedding: list[float],
) -> RefinedPrompt:
    """Create a high-scoring prompt (score=4.5)."""
    prompt = RefinedPrompt(
        id=uuid.uuid4(),
        embedding=sample_embedding,
        main_language="python",
        agent_type="developer",
        original_prompt="Write a test",
        refined_prompt="Refined test prompt",
        usage_count=10,
        average_score=4.5,
        score_dist_1=0,
        score_dist_2=0,
        score_dist_3=1,
        score_dist_4=2,
        score_dist_5=7,
    )
    db_session.add(prompt)
    await db_session.flush()
    await db_session.refresh(prompt)
    return prompt


@pytest_asyncio.fixture
async def low_score_prompt(
    db_session: AsyncSession,
    sample_embedding: list[float],
) -> RefinedPrompt:
    """Create a low-scoring prompt (score=1.5)."""
    prompt = RefinedPrompt(
        id=uuid.uuid4(),
        embedding=sample_embedding,
        main_language="python",
        agent_type="developer",
        original_prompt="Write a test",
        refined_prompt="Refined test prompt",
        usage_count=5,
        average_score=1.5,
        score_dist_1=3,
        score_dist_2=2,
        score_dist_3=0,
        score_dist_4=0,
        score_dist_5=0,
    )
    db_session.add(prompt)
    await db_session.flush()
    await db_session.refresh(prompt)
    return prompt


@pytest_asyncio.fixture
async def prompt_with_history(
    db_session: AsyncSession,
    sample_embedding: list[float],
) -> RefinedPrompt:
    """Create a prompt with history records."""
    prompt = RefinedPrompt(
        id=uuid.uuid4(),
        embedding=sample_embedding,
        main_language="python",
        agent_type="developer",
        original_prompt="Write a function",
        refined_prompt="Refined function prompt",
        usage_count=3,
        average_score=3.5,
        score_dist_1=0,
        score_dist_2=0,
        score_dist_3=1,
        score_dist_4=2,
        score_dist_5=0,
    )
    db_session.add(prompt)
    await db_session.flush()
    
    # Add history records
    for i, score in enumerate([3.0, 4.0, 3.5], 1):
        history = PromptHistory(
            prompt_id=prompt.id,
            action_score=score,
            files_modified=[f"file{i}.py"],
            diffs={f"file{i}.py": "..."},
        )
        db_session.add(history)
    
    await db_session.flush()
    await db_session.refresh(prompt)
    return prompt


# -----------------------------------------------------------------------------
# Deterministic Random Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def deterministic_random_high() -> Generator[None, None, None]:
    """Patch random.random to always return 0.9 (high - will not refine)."""
    with patch("simpa.prompts.selector.random.random", return_value=0.9):
        yield


@pytest.fixture
def deterministic_random_low() -> Generator[None, None, None]:
    """Patch random.random to always return 0.1 (low - will refine)."""
    with patch("simpa.prompts.selector.random.random", return_value=0.1):
        yield


# -----------------------------------------------------------------------------
# Cache Isolation Fixture
# -----------------------------------------------------------------------------


@pytest.fixture(scope="function")
def _clear_caches() -> Generator[None, None, None]:
    """Clear caches before each test to ensure isolation."""
    from simpa.llm.cache import LLMResponseCache
    from simpa.embedding.service import EmbeddingCache
    from simpa.config import settings
    
    # Create temporary cache instances and clear them
    _llm_cache = LLMResponseCache()
    if _llm_cache.enabled:
        _llm_cache.clear_all()
        _llm_cache.close()
    
    # Clear embedding cache singleton
    _embedding_cache = EmbeddingCache()
    _embedding_cache.clear()
    
    yield
    
    # Cleanup after test
    try:
        _llm_cache = LLMResponseCache()
        if _llm_cache.enabled:
            _llm_cache.clear_all()
            _llm_cache.close()
    except Exception:
        pass  # Ignore cleanup errors
    
    try:
        _embedding_cache = EmbeddingCache()
        _embedding_cache.clear()
    except Exception:
        pass  # Ignore cleanup errors


# -----------------------------------------------------------------------------
# Project Fixtures
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_project(db_session: AsyncSession) -> AsyncGenerator[Any, None]:
    """Create and return a sample Project in the database."""
    try:
        from simpa.db.models import Project
        
        project = Project(
            id=uuid.uuid4(),
            project_name="test-project",
            description="A test project for SIMPA",
        )
        db_session.add(project)
        await db_session.flush()
        await db_session.refresh(project)
        yield project
    except ImportError:
        pytest.skip("Project model not yet implemented")
        yield None


@pytest_asyncio.fixture
async def another_project(db_session: AsyncSession) -> AsyncGenerator[Any, None]:
    """Create a second sample Project."""
    try:
        from simpa.db.models import Project
        
        project = Project(
            id=uuid.uuid4(),
            project_name="another-project",
            description="Another test project",
        )
        db_session.add(project)
        await db_session.flush()
        await db_session.refresh(project)
        yield project
    except ImportError:
        pytest.skip("Project model not yet implemented")
        yield None


@pytest_asyncio.fixture
async def deleted_project(db_session: AsyncSession) -> AsyncGenerator[Any, None]:
    """Create a Project that is marked as deleted (inactive)."""
    try:
        from simpa.db.models import Project
        
        project = Project(
            id=uuid.uuid4(),
            project_name="deleted-project",
            description="This project is inactive",
            is_active=False,
        )
        db_session.add(project)
        await db_session.flush()
        await db_session.refresh(project)
        yield project
    except ImportError:
        pytest.skip("Project model not yet implemented")
        yield None


@pytest_asyncio.fixture
async def project_with_prompts(
    db_session: AsyncSession,
    sample_project: Any,
    sample_prompt: RefinedPrompt,
) -> AsyncGenerator[Any, None]:
    """Create a Project with associated prompts."""
    try:
        from simpa.db.models import Project
        
        # Associate prompt with project
        sample_prompt.project_id = sample_project.id
        await db_session.flush()
        await db_session.refresh(sample_project)
        yield sample_project
    except (ImportError, AttributeError):
        pytest.skip("Project model or project_id field not yet implemented")
        yield sample_project


# -----------------------------------------------------------------------------
# MCP Integration Test Helper Fixture
# -----------------------------------------------------------------------------


@pytest.fixture(scope="function")
def patch_async_session_local(db_session: AsyncSession):
    """Patch AsyncSessionLocal to return the test session for MCP tools.
    
    This allows MCP server tools to use the test database session instead of
    creating their own, which prevents event loop conflicts and session mismatches.
    """
    from unittest.mock import patch
    
    class MockSessionContextManager:
        def __init__(self, session):
            self.session = session
        
        async def __aenter__(self):
            return self.session
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Don't actually close - let the fixture handle it
            pass
    
    def mock_session_local():
        return MockSessionContextManager(db_session)
    
    # Patch all modules that import AsyncSessionLocal
    with patch("simpa.mcp_server.AsyncSessionLocal", mock_session_local):
        with patch("simpa.db.engine.AsyncSessionLocal", mock_session_local):
            yield
