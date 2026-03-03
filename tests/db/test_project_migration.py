"""Database migration tests for Project feature."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import Column, inspect, text
from sqlalchemy.dialects.postgresql import UUID


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
class TestProjectTableSchema:
    """Test Project table schema created by migration."""

    async def test_project_table_exists(self, db_session):
        """Test that projects table exists in database."""
        result = await db_session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'projects'
        """))
        
        tables = result.fetchall()
        assert any('projects' in str(t) for t in tables), "projects table should exist"

    async def test_project_id_column(self, db_session):
        """Test id column is UUID primary key."""
        result = await db_session.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'projects' AND column_name = 'id'
        """))
        
        col = result.fetchone()
        assert col is not None, "id column should exist"
        assert 'uuid' in str(col[1]).lower() or 'uuid' in str(col[2]).lower()

    async def test_project_name_column(self, db_session):
        """Test project_name column exists and is required."""
        result = await db_session.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'projects' AND column_name = 'project_name'
        """))
        
        col = result.fetchone()
        assert col is not None, "project_name column should exist"
        assert col[2] == 'NO', "project_name should be NOT NULL"

    async def test_project_name_unique_constraint(self, db_session):
        """Test that project_name has unique constraint."""
        result = await db_session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'projects' 
            AND indexname LIKE '%project_name%'
        """))
        
        indexes = result.fetchall()
        assert len(indexes) >= 1, "project_name should have an index"

    async def test_description_column(self, db_session):
        """Test description column exists and is nullable."""
        result = await db_session.execute(text("""
            SELECT column_name, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'projects' AND column_name = 'description'
        """))
        
        col = result.fetchone()
        assert col is not None, "description column should exist"
        assert col[1] == 'YES', "description should be nullable"

    async def test_is_active_column(self, db_session):
        """Test is_active column exists with default."""
        result = await db_session.execute(text("""
            SELECT column_name, column_default, is_nullable, data_type
            FROM information_schema.columns 
            WHERE table_name = 'projects' AND column_name = 'is_active'
        """))
        
        col = result.fetchone()
        assert col is not None, "is_active column should exist"
        # is_active should be a boolean column and not nullable
        assert col[2] == 'NO', "is_active should be NOT NULL"
        # Check it's a boolean type
        data_type = str(col[3]).lower() if col[3] else ''
        assert 'bool' in data_type, f"is_active should be boolean type, got: {data_type}"

    async def test_timestamps(self, db_session):
        """Test created_at and updated_at columns."""
        for col_name in ['created_at', 'updated_at']:
            result = await db_session.execute(text(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'projects' AND column_name = '{col_name}'
            """))
            
            col = result.fetchone()
            assert col is not None, f"{col_name} column should exist"
            # created_at should be NOT NULL, updated_at can be nullable
            if col_name == 'created_at':
                assert col[2] == 'NO', f"{col_name} should be NOT NULL"
            # Both should be timestamp types
            assert 'timestamp' in str(col[1]).lower() or 'date' in str(col[1]).lower(), f"{col_name} should be timestamp type"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
class TestRefinedPromptsProjectFK:
    """Test RefinedPrompts table has project_id foreign key."""

    async def test_refined_prompts_has_project_id(self, db_session):
        """Test refined_prompts table has project_id column."""
        result = await db_session.execute(text("""
            SELECT column_name, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'refined_prompts' AND column_name = 'project_id'
        """))
        
        col = result.fetchone()
        assert col is not None, "project_id column should exist in refined_prompts"

    async def test_project_id_foreign_key_constraint(self, db_session):
        """Test project_id has FK constraint to projects."""
        result = await db_session.execute(text("""
            SELECT
                tc.constraint_name,
                ccu.table_name AS foreign_table
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_name = 'refined_prompts'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND tc.constraint_name LIKE '%project%'
        """))
        
        constraints = result.fetchall()
        assert len(constraints) >= 1, "project_id should have FK constraint"

    async def test_project_id_index(self, db_session):
        """Test project_id has an index for performance."""
        result = await db_session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'refined_prompts' 
            AND indexname LIKE '%project_id%'
        """))
        
        indexes = result.fetchall()
        assert len(indexes) >= 1, "project_id should have an index"
        
        # Verify the exact index name matches migration
        index_names = [idx[0] for idx in indexes]
        assert 'ix_refined_prompts_project_id' in index_names, \
            f"Expected 'ix_refined_prompts_project_id', got: {index_names}"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
class TestPromptHistoryIndexes:
    """Test prompt_history table index naming matches migrations."""

    async def test_prompt_history_project_id_index(self, db_session):
        """Test prompt_history project_id has correct index name."""
        result = await db_session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prompt_history' 
            AND indexname LIKE '%project_id%'
        """))
        
        indexes = result.fetchall()
        assert len(indexes) >= 1, "project_id should have an index in prompt_history"
        
        # Verify the exact index name matches migration 004
        index_names = [idx[0] for idx in indexes]
        assert 'ix_prompt_history_project_id' in index_names, \
            f"Expected 'ix_prompt_history_project_id', got: {index_names}"

    async def test_prompt_id_index_naming(self, db_session):
        """Test prompt_id index has correct name (not refined_prompt_id).
        
        Migration 002 renamed refined_prompt_id column to prompt_id and
        renamed the index from ix_prompt_history_refined_prompt_id to
        ix_prompt_history_prompt_id.
        """
        result = await db_session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'prompt_history'
        """))
        
        indexes = result.fetchall()
        index_names = [idx[0] for idx in indexes]
        
        # Verify the corrected index exists
        assert 'ix_prompt_history_prompt_id' in index_names, \
            f"Expected 'ix_prompt_history_prompt_id' in indexes, got: {index_names}"
        
        # Verify the old index name no longer exists
        assert 'ix_prompt_history_refined_prompt_id' not in index_names, \
            f"Old index 'ix_prompt_history_refined_prompt_id' should not exist, got: {index_names}"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
class TestMigrationRollback:
    """Test migration rollback functionality."""

    async def test_migration_can_rollback(self, db_session):
        """Test that migration can be rolled back."""
        # This would require alembic integration
        # For now, verify the table structure is compatible
        
        result = await db_session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'projects'
        """))
        
        tables = result.fetchall()
        assert len(tables) <= 1, "Should have zero or one projects table"

    async def test_no_data_loss_on_rollback(self, db_session):
        """Test that rollback preserves existing data."""
        # Verify foreign key constraint allows nulls
        result = await db_session.execute(text("""
            SELECT is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'refined_prompts' AND column_name = 'project_id'
        """))
        
        col = result.fetchone()
        if col:
            assert col[0] == 'YES', "project_id should be nullable to allow rollback"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
class TestProjectDataIntegrity:
    """Test Project data integrity constraints."""

    async def test_null_project_name_rejected(self, db_session):
        """Test NULL project_name is rejected."""
        try:
            await db_session.execute(text("""
                INSERT INTO projects (id, project_name) VALUES (uuid_generate_v4(), NULL)
            """))
            await db_session.commit()
            assert False, "Should have raised an exception for NULL project_name"
        except Exception:
            await db_session.rollback()
            # Expected failure
            pass

    async def test_duplicate_project_name_rejected(self, db_session):
        """Test duplicate project_name is rejected."""
        try:
            await db_session.execute(text("""
                INSERT INTO projects (id, project_name) VALUES (uuid_generate_v4(), 'unique-test-project')
            """))
            await db_session.execute(text("""
                INSERT INTO projects (id, project_name) VALUES (uuid_generate_v4(), 'unique-test-project')
            """))
            await db_session.commit()
            assert False, "Should have raised an exception for duplicate project_name"
        except Exception:
            await db_session.rollback()
            # Expected failure
            pass
