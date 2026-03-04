"""LLM response caching module for SIMPA."""

import hashlib
import sqlite3
import structlog
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from simpa.config import settings

logger = structlog.get_logger()


class LLMResponseCache:
    """SQLite-based cache for LLM responses with TTL support."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the cache.
        
        Args:
            db_path: Path to SQLite database file. Defaults to settings.llm_cache_db_path
        """
        self.db_path = db_path or settings.llm_cache_db_path
        self.enabled = settings.llm_cache_enabled
        self.ttl_seconds = settings.llm_cache_ttl_seconds
        self.max_entries = settings.llm_cache_max_entries
        self._connection: Optional[sqlite3.Connection] = None
        
        if self.enabled:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database and create tables if needed."""
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON llm_cache(expires_at)
            """)
            conn.commit()
            conn.close()
            logger.debug("llm_cache_initialized", db_path=self.db_path)
        except sqlite3.Error as e:
            logger.error("llm_cache_init_error", db_path=self.db_path, error=str(e))
            # Disable cache on init error
            self.enabled = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._connection

    def _compute_key(self, system_prompt: str, user_prompt: str) -> str:
        """Compute cache key from prompts."""
        combined = f"{system_prompt}:{user_prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Retrieve cached response if exists and not expired.
        
        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            
        Returns:
            Cached response or None if not found/expired
        """
        if not self.enabled:
            return None
            
        try:
            key = self._compute_key(system_prompt, user_prompt)
            conn = self._get_connection()
            
            cursor = conn.execute(
                "SELECT response, expires_at FROM llm_cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                logger.debug("cache_miss", key=key[:16])
                return None
            
            response, expires_at_str = row
            expires_at = datetime.fromisoformat(expires_at_str)
            
            if datetime.now(timezone.utc) > expires_at:
                # Expired, delete it
                conn.execute("DELETE FROM llm_cache WHERE key = ?", (key,))
                conn.commit()
                logger.debug("cache_expired", key=key[:16])
                return None
            
            logger.info("cache_hit", key=key[:16])
            return response
            
        except (sqlite3.Error, ValueError, TypeError) as e:
            logger.error("cache_get_error", error=str(e))
            return None

    def set(self, system_prompt: str, user_prompt: str, response: str) -> None:
        """Store response in cache.
        
        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            response: LLM response to cache
        """
        if not self.enabled:
            return
            
        key = self._compute_key(system_prompt, user_prompt)
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(seconds=self.ttl_seconds)
        
        conn = self._get_connection()
        
        try:
            # Check current entry count and cleanup if needed
            cursor = conn.execute("SELECT COUNT(*) FROM llm_cache")
            count = cursor.fetchone()[0]
            
            # Delete enough entries to make room for the new one
            if count >= self.max_entries:
                to_delete = count - self.max_entries + 1
                conn.execute(
                    """DELETE FROM llm_cache WHERE key IN (
                        SELECT key FROM llm_cache 
                        ORDER BY created_at ASC LIMIT ?
                    )""",
                    (to_delete,)
                )
                logger.debug("cache_cleanup", removed=to_delete)
            
            # Insert or replace
            conn.execute(
                """INSERT OR REPLACE INTO llm_cache 
                   (key, response, created_at, expires_at) VALUES (?, ?, ?, ?)""",
                (key, response, created_at.isoformat(), expires_at.isoformat())
            )
            conn.commit()
            logger.debug("cache_set", key=key[:16], expires_at=expires_at.isoformat())
            
        except sqlite3.Error as e:
            logger.error("cache_set_error", error=str(e))

    def invalidate(self, system_prompt: str, user_prompt: str) -> bool:
        """Remove entry from cache.
        
        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            
        Returns:
            True if entry was found and removed
        """
        if not self.enabled:
            return False
            
        key = self._compute_key(system_prompt, user_prompt)
        conn = self._get_connection()
        
        try:
            cursor = conn.execute("DELETE FROM llm_cache WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("cache_invalidate_error", error=str(e))
            return False

    def clear_expired(self) -> int:
        """Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        if not self.enabled:
            return 0
            
        conn = self._get_connection()
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            cursor = conn.execute(
                "DELETE FROM llm_cache WHERE expires_at < ?",
                (now,)
            )
            conn.commit()
            removed = cursor.rowcount
            if removed > 0:
                logger.info("cache_expired_cleared", count=removed)
            return removed
        except sqlite3.Error as e:
            logger.error("cache_clear_error", error=str(e))
            return 0

    def clear_all(self) -> int:
        """Clear all cached entries.
        
        Returns:
            Number of entries removed
        """
        if not self.enabled:
            return 0
            
        conn = self._get_connection()
        
        try:
            cursor = conn.execute("DELETE FROM llm_cache")
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error("cache_clear_all_error", error=str(e))
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dict with entry_count, expired_count
        """
        if not self.enabled:
            return {"enabled": False}
            
        conn = self._get_connection()
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM llm_cache")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM llm_cache WHERE expires_at < ?",
                (now,)
            )
            expired = cursor.fetchone()[0]
            
            return {
                "enabled": True,
                "entry_count": total,
                "expired_count": expired,
                "db_path": self.db_path,
                "ttl_seconds": self.ttl_seconds,
            }
        except sqlite3.Error as e:
            logger.error("cache_stats_error", error=str(e))
            return {"enabled": True, "error": str(e)}

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
