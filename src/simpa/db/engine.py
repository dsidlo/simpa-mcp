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
from simpa.utils.logging import get_logger

logger = get_logger(__name__)

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
    
    # Mask password in logs
    safe_url = url
    if "@" in url:
        # Replace password with *** for logging
        parts = url.split("@")
        creds = parts[0].split(":")
        if len(creds) >= 3:
            safe_url = f"{creds[0]}:***@{parts[1]}"
    
    logger.debug("creating_database_engine", url=safe_url, pool_size=pool_size)
    
    # Use NullPool when pool_size is None (for tests) to avoid connection reuse issues
    if pool_size is None:
        logger.info("database_engine_created", pool_type="NullPool", url=safe_url)
        return create_async_engine(
            url,
            echo=settings.log_level == "DEBUG",
            future=True,
            poolclass=NullPool,
        )
    
    logger.info(
        "database_engine_created",
        pool_type="QueuePool",
        pool_size=pool_size,
        max_overflow=20,
        url=safe_url,
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

    logger.info("database_initialization_started")
    
    try:
        async with async_engine.begin() as conn:
            # Enable pgvector extension
            logger.debug("creating_pgvector_extension")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.debug("pgvector_extension_ready")
            
            # Create all tables
            logger.debug("creating_database_tables")
            await conn.run_sync(Base.metadata.create_all)
            logger.debug("database_tables_created")
        
        logger.info("database_initialization_complete")
        
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e), exc_info=True)
        raise


async def close_db() -> None:
    """Close database connections."""
    logger.info("database_closing_connections")
    await async_engine.dispose()
    logger.info("database_connections_closed")


def reset_engine(database_url: str | None = None, pool_size: int | None = None) -> None:
    """Reset the global engine and session factory.
    
    This is useful for tests to ensure connections are properly
    disposed and recreated on a new event loop.
    
    Args:
        database_url: Optional new database URL
        pool_size: Optional pool size (None = NullPool for tests)
    """
    global async_engine, AsyncSessionLocal
    
    logger.info("database_engine_reset")
    
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
    logger.info("database_engine_reset_complete")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as an async context manager."""
    session_id = id(async_engine)
    logger.debug("database_session_acquired", session_id=session_id)
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            logger.debug("database_session_committed", session_id=session_id)
        except Exception as e:
            await session.rollback()
            logger.error("database_session_rollback", session_id=session_id, error=str(e))
            raise
        finally:
            await session.close()
            logger.debug("database_session_closed", session_id=session_id)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session (for dependency injection)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
