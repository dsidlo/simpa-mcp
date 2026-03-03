"""Database engine and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool

from simpa.config import settings

# Convert PostgreSQL DSN to async format
_async_database_url = str(settings.database_url).replace(
    "postgresql://",
    "postgresql+asyncpg://",
)

# Track if we're in test mode to use NullPool
_test_engine: AsyncEngine | None = None


def _create_engine(database_url: str | None = None, pool_size: int | None = None) -> AsyncEngine:
    """Create an async engine with proper configuration.
    
    Args:
        database_url: Optional database URL (defaults to settings)
        pool_size: Optional pool size (None = use NullPool for tests)
        
    Returns:
        Configured AsyncEngine
    """
    url = database_url or _async_database_url
    
    # Use NullPool when pool_size is None (for tests) to avoid connection reuse issues
    if pool_size is None:
        return create_async_engine(
            url,
            echo=settings.log_level == "DEBUG",
            future=True,
            poolclass=NullPool,
        )
    
    return create_async_engine(
        url,
        echo=settings.log_level == "DEBUG",
        future=True,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=20,
        pool_reset_on_return=True,
    )


# Create async engine with proper pooling for production
async_engine = _create_engine(pool_size=10)

# Create session factory bound to the engine
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@event.listens_for(async_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable pgvector extension on connection (sync fallback)."""
    pass  # pragma: no cover


async def init_db() -> None:
    """Initialize database extensions and tables."""
    from sqlalchemy import text

    from simpa.db.models import Base

    async with async_engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await async_engine.dispose()


def reset_engine(database_url: str | None = None, pool_size: int | None = None) -> None:
    """Reset the global engine and session factory.
    
    This is useful for tests to ensure connections are properly
    disposed and recreated on a new event loop.
    
    Args:
        database_url: Optional new database URL
        pool_size: Optional pool size (None = NullPool for tests)
    """
    global async_engine, AsyncSessionLocal
    
    # Dispose the old engine if it exists
    if async_engine:
        # Note: dispose() is async, but we're in a sync context here
        # The caller should handle proper disposal if needed
        pass
    
    # Create new engine and session factory
    async_engine = _create_engine(database_url, pool_size)
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as an async context manager."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session (for dependency injection)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
