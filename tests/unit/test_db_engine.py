"""Unit tests for database engine."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from simpa.db.engine import (
    async_engine,
    AsyncSessionLocal,
    init_db,
    close_db,
    get_db_session,
    get_session,
    _async_database_url,
)
from simpa.db import models


class TestDatabaseUrl:
    """Test database URL conversion."""

    def test_url_converted_to_asyncpg(self):
        """Test that postgresql:// is converted to postgresql+asyncpg://."""
        assert "postgresql+asyncpg://" in _async_database_url
        assert "postgresql://" not in _async_database_url or "postgresql+asyncpg://" in _async_database_url


class TestAsyncEngine:
    """Test async engine configuration."""

    def test_engine_is_async(self):
        """Test that engine is an async engine."""
        assert isinstance(async_engine, AsyncEngine)

    def test_engine_has_pool_settings(self):
        """Test engine pool configuration."""
        # Pool size should be 10
        assert async_engine.pool.size() == 10
        # Max overflow should be 20
        assert async_engine.pool._max_overflow == 20


@pytest.mark.asyncio
class TestInitDb:
    """Test database initialization."""

    async def test_init_db_creates_extensions(self):
        """Test that init_db creates pgvector extension."""
        with patch("simpa.db.engine.async_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(models.Base, "metadata", MagicMock()):
                await init_db()

                # Verify pgvector extension was created
                assert mock_conn.execute.called
                assert mock_conn.execute.call_count >= 1
                # First call should be CREATE EXTENSION (wrapped in text())
                assert mock_conn.execute.call_count >= 1

    async def test_init_db_creates_tables(self):
        """Test that init_db creates all tables."""
        with patch("simpa.db.engine.async_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_metadata = MagicMock()
            with patch.object(models.Base, "metadata", mock_metadata):
                await init_db()

                # Verify create_all was called
                mock_conn.run_sync.assert_called_once_with(mock_metadata.create_all)


@pytest.mark.asyncio
class TestCloseDb:
    """Test database cleanup."""

    async def test_close_db_disposes_engine(self):
        """Test that close_db disposes the engine."""
        with patch("simpa.db.engine.async_engine") as mock_engine:
            mock_engine.dispose = AsyncMock()

            await close_db()

            mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
class TestGetDbSession:
    """Test get_db_session context manager."""

    async def test_get_db_session_commits_on_success(self):
        """Test that session commits on successful exit."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("simpa.db.engine.AsyncSessionLocal") as mock_session_local:
            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)

            async with get_db_session() as session:
                assert session == mock_session

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()

    async def test_get_db_session_rolls_back_on_exception(self):
        """Test that session rolls back on exception."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("simpa.db.engine.AsyncSessionLocal") as mock_session_local:
            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ValueError, match="Test error"):
                async with get_db_session() as session:
                    raise ValueError("Test error")

        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
class TestGetSession:
    """Test get_session generator."""

    async def test_get_session_yields_session(self):
        """Test that get_session yields a session."""
        mock_session = AsyncMock()

        with patch("simpa.db.engine.AsyncSessionLocal") as mock_session_local:
            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)

            async for session in get_session():
                assert session == mock_session
                break  # Only iterate once


class TestSessionFactory:
    """Test AsyncSessionLocal configuration."""

    def test_session_factory_config(self):
        """Test session factory is configured correctly."""
        # Should not expire on commit
        assert AsyncSessionLocal.kw.get("expire_on_commit") == False
        # Should not autoflush
        assert AsyncSessionLocal.kw.get("autoflush") == False
        # Should not autocommit
        assert AsyncSessionLocal.kw.get("autocommit") == False
