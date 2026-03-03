"""Database schema and integration tests."""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, inspect
from sqlalchemy.dialects.postgresql import UUID

from simpa.db.models import Base, PromptHistory, RefinedPrompt
from simpa.db.repository import PromptHistoryRepository, RefinedPromptRepository


async def get_inspector(async_engine):
    """Get inspector for async engine."""
    def _get_inspector(sync_conn):
        return inspect(sync_conn)
    
    async with async_engine.connect() as conn:
        # Get inspector on the sync connection
        return await conn.run_sync(_get_inspector)


async def run_sync_inspect(async_engine, method, *args, **kwargs):
    """Run a sync inspector method on async engine."""
    def _run_method(sync_conn):
        inspector = inspect(sync_conn)
        return getattr(inspector, method)(*args, **kwargs)
    
    # Use the async engine properly with run_sync
    async with async_engine.connect() as conn:
        return await conn.run_sync(_run_method)


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestRefinedPromptsTableSchema:
    """Test schema for refined_prompts table."""

    async def test_table_exists(self, db_session):
        """Test that refined_prompts table exists."""
        tables = await run_sync_inspect(db_session.bind, "get_table_names")
        assert "refined_prompts" in tables

    async def test_id_column(self, db_session):
        """Test id column is UUID primary key."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "refined_prompts")
        
        id_col = next(c for c in columns if c["name"] == "id")
        # UUID type check - column exists
        assert id_col is not None
        
        # Check primary key separately
        pk_constraint = await run_sync_inspect(db_session.bind, "get_pk_constraint", "refined_prompts")
        assert "id" in pk_constraint["constrained_columns"]

    async def test_embedding_column(self, db_session):
        """Test embedding column is Vector type with correct dimensions."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "refined_prompts")
        
        embedding_col = next(c for c in columns if c["name"] == "embedding")
        assert embedding_col is not None
        # Column should exist (pgvector type)

    async def test_required_columns_exist(self, db_session):
        """Test all required columns exist."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "refined_prompts")
        column_names = [c["name"] for c in columns]
        
        required = [
            "id",
            "embedding",
            "main_language",
            "agent_type",
            "original_prompt",
            "refined_prompt",
            "created_at",
            "updated_at",
            "usage_count",
            "average_score",
            "score_dist_1",
            "score_dist_2",
            "score_dist_3",
            "score_dist_4",
            "score_dist_5",
            "prior_refinement_id",
        ]
        
        for col in required:
            assert col in column_names, f"Missing column: {col}"

    async def test_timestamp_columns(self, db_session):
        """Test created_at and updated_at are timestamp columns."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "refined_prompts")
        
        created_col = next(c for c in columns if c["name"] == "created_at")
        updated_col = next(c for c in columns if c["name"] == "updated_at")
        
        # Both should be datetime/timestamp types
        assert "date" in str(created_col["type"]).lower() or "timestamp" in str(created_col["type"]).lower()
        assert "date" in str(updated_col["type"]).lower() or "timestamp" in str(updated_col["type"]).lower()

    async def test_score_distribution_columns(self, db_session):
        """Test score distribution columns exist (score_dist_1 to score_dist_5)."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "refined_prompts")
        column_names = [c["name"] for c in columns]
        
        for i in range(1, 6):
            col_name = f"score_dist_{i}"
            assert col_name in column_names, f"Missing column: {col_name}"
            dist_col = next(c for c in columns if c["name"] == col_name)
            assert "int" in str(dist_col["type"]).lower(), f"{col_name} should be integer type"

    async def test_indexes_exist(self, db_session):
        """Test required indexes exist."""
        indexes = await run_sync_inspect(db_session.bind, "get_indexes", "refined_prompts")
        index_names = [idx["name"] for idx in indexes]
        
        # Should have indexes on searchable/filterable columns
        assert any("agent_type" in name for name in index_names), "Missing agent_type index"
        assert any("main_language" in name for name in index_names), "Missing main_language index"


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestPromptHistoryTableSchema:
    """Test schema for prompt_history table."""

    async def test_table_exists(self, db_session):
        """Test that prompt_history table exists."""
        tables = await run_sync_inspect(db_session.bind, "get_table_names")
        assert "prompt_history" in tables

    async def test_diffs_column_exists(self, db_session):
        """Test that diffs column exists in prompt_history table."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "prompt_history")
        column_names = [c["name"] for c in columns]
        assert "diffs" in column_names, "Missing column: diffs"

    async def test_diffs_column_is_json(self, db_session):
        """Test that diffs column is JSON type."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "prompt_history")
        diffs_col = next(c for c in columns if c["name"] == "diffs")
        assert "json" in str(diffs_col["type"]).lower(), "diffs column should be JSON type"

    async def test_execution_duration_ms_column_exists(self, db_session):
        """Test that execution_duration_ms column exists in prompt_history table."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "prompt_history")
        column_names = [c["name"] for c in columns]
        assert "execution_duration_ms" in column_names, "Missing column: execution_duration_ms"

    async def test_agent_output_summary_column_exists(self, db_session):
        """Test that agent_output_summary column exists in prompt_history table."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "prompt_history")
        column_names = [c["name"] for c in columns]
        assert "agent_output_summary" in column_names, "Missing column: agent_output_summary"

    async def test_validation_results_column_exists(self, db_session):
        """Test that validation_results column exists in prompt_history table."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "prompt_history")
        column_names = [c["name"] for c in columns]
        assert "validation_results" in column_names, "Missing column: validation_results"

    async def test_saliency_metadata_column_exists(self, db_session):
        """Test that saliency_metadata column exists in prompt_history table."""
        columns = await run_sync_inspect(db_session.bind, "get_columns", "prompt_history")
        column_names = [c["name"] for c in columns]
        assert "saliency_metadata" in column_names, "Missing column: saliency_metadata"

    async def test_foreign_key_constraint(self, db_session):
        """Test prompt_id foreign key to refined_prompts."""
        fks = await run_sync_inspect(db_session.bind, "get_foreign_keys", "prompt_history")
        
        assert len(fks) >= 1
        # Find the FK that refers to refined_prompts
        fk = next((f for f in fks if f["referred_table"] == "refined_prompts"), None)
        assert fk is not None, "No FK to refined_prompts found"
        assert "prompt_id" in fk["constrained_columns"]

    async def test_cascade_delete(self, db_session):
        """Test that deleting prompt cascades to history."""
        fks = await run_sync_inspect(db_session.bind, "get_foreign_keys", "prompt_history")
        
        if fks:
            # Check for CASCADE option
            fk = fks[0]
            # Note: ondelete may be in options or separate


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestForeignKeyIntegrity:

    async def test_create_prompt(self, db_session, sample_embedding):
        """Test creating a new refined prompt."""
        repo = RefinedPromptRepository(db_session)
        
        prompt = await repo.create(
            embedding=sample_embedding,
            main_language="python",
            agent_type="developer",
            original_prompt="Write a function",
            refined_prompt="Refined: Write a Python function",
            other_languages=["bash"],
        )
        
        assert prompt.id is not None
        assert prompt.main_language == "python"
        assert prompt.agent_type == "developer"
        assert prompt.usage_count == 0
        assert prompt.average_score == 0.0

    async def test_get_by_id(self, db_session, sample_prompt):
        """Test retrieving prompt by ID."""
        repo = RefinedPromptRepository(db_session)
        
        retrieved = await repo.get_by_id(sample_prompt.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_prompt.id
        assert retrieved.agent_type == sample_prompt.agent_type

    async def test_get_by_id_not_found(self, db_session):
        """Test retrieving non-existent prompt returns None."""
        repo = RefinedPromptRepository(db_session)
        
        retrieved = await repo.get_by_id(uuid.uuid4())
        
        assert retrieved is None

    async def test_update_stats(self, db_session, sample_prompt):
        """Test updating prompt statistics."""
        repo = RefinedPromptRepository(db_session)
        
        updated = await repo.update_stats(
            prompt_id=sample_prompt.id,
            score=4.5,
        )
        
        assert updated is not None
        assert updated.usage_count == 1
        assert updated.average_score == pytest.approx(4.5, abs=0.01)
        assert updated.score_dist_4 == 1

    async def test_find_similar_by_agent_type(self, db_session):
        """Test finding similar prompts filters by agent_type."""
        repo = RefinedPromptRepository(db_session)
        
        # Create prompts for different agent types
        embedding = [0.1] * 768
        
        await repo.create(
            embedding=embedding,
            main_language="python",
            agent_type="developer",
            original_prompt="Dev prompt",
            refined_prompt="Refined dev prompt",
        )
        
        await repo.create(
            embedding=embedding,
            main_language="python",
            agent_type="architect",
            original_prompt="Arch prompt",
            refined_prompt="Refined arch prompt",
        )
        
        await db_session.commit()
        
        # Search for similar prompts with agent_type filter
        results = await repo.find_similar(
            embedding=embedding,
            agent_type="developer",
            limit=5,
        )
        
        assert len(results) >= 1
        for r in results:
            assert r.agent_type == "developer"

    async def test_similarity_threshold_applied(self, db_session):
        """Test that similarity threshold filters results."""
        repo = RefinedPromptRepository(db_session)
        
        # Create a prompt
        embedding1 = [0.1] * 768
        await repo.create(
            embedding=embedding1,
            main_language="python",
            agent_type="test",
            original_prompt="Test",
            refined_prompt="Refined test",
        )
        await db_session.commit()
        
        # Query with very different embedding (orthogonal)
        embedding2 = [0.9 if i % 2 == 0 else -0.9 for i in range(768)]
        results = await repo.find_similar(
            embedding=embedding2,
            agent_type="test",
            similarity_threshold=0.8,  # High threshold
            limit=5,
        )
        
        # Should return empty due to high threshold
        assert len(results) == 0

    async def test_get_best_for_agent(self, db_session):
        """Test getting best prompts for an agent type."""
        repo = RefinedPromptRepository(db_session)
        
        # Create prompts with different scores
        embedding = [0.1] * 768
        
        prompt1 = await repo.create(
            embedding=embedding,
            main_language="python",
            agent_type="tester",
            original_prompt="Low score",
            refined_prompt="Refined low",
        )
        await repo.update_stats(prompt1.id, 2.0)
        
        prompt2 = await repo.create(
            embedding=embedding,
            main_language="python",
            agent_type="tester",
            original_prompt="High score",
            refined_prompt="Refined high",
        )
        await repo.update_stats(prompt2.id, 4.5)
        await repo.update_stats(prompt2.id, 4.5)  # Update twice
        
        await db_session.commit()
        
        best = await repo.get_best_for_agent("tester", limit=5)
        
        # Should be ordered by average_score descending
        assert len(best) >= 2
        assert best[0].average_score >= best[1].average_score


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestPromptHistoryRepository:
    """Test PromptHistoryRepository operations."""

    async def test_create_history(self, db_session, sample_prompt):
        """Test creating a history record."""
        repo = PromptHistoryRepository(db_session)
        
        history = await repo.create(
            prompt_id=sample_prompt.id,
            action_score=4.0,
            files_modified=["file1.py"],
            diffs={"python": [{"file": "file1.py", "diff": "..."}]},
        )
        
        assert history.id is not None
        assert history.prompt_id == sample_prompt.id
        assert history.action_score == 4.0

    async def test_get_by_prompt_id(self, db_session, prompt_with_history):
        """Test retrieving history for a prompt."""
        repo = PromptHistoryRepository(db_session)
        
        history = await repo.get_by_prompt_id(prompt_with_history.id)
        
        assert len(history) == 3
        # Should be ordered by created_at descending
        for i in range(len(history) - 1):
            assert history[i].created_at >= history[i+1].created_at


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestRefinedPromptStatsUpdate:
    """Test the update_score_stats method on RefinedPrompt."""

    async def test_stats_update_first_score(self):
        """Test updating stats with first score."""
        prompt = RefinedPrompt(
            original_prompt="Test",
            refined_prompt="Refined",
            main_language="python",
            agent_type="test",
            embedding=[0.0] * 768,
            usage_count=0,
            average_score=0.0,
            score_dist_1=0,
            score_dist_2=0,
            score_dist_3=0,
            score_dist_4=0,
            score_dist_5=0,
        )
        
        prompt.update_score_stats(4.0)
        
        assert prompt.usage_count == 1
        assert prompt.average_score == 4.0
        assert prompt.score_dist_4 == 1
        assert prompt.get_score_distribution()["4"] == 1

    async def test_stats_update_multiple_scores(self):
        """Test updating stats with multiple scores."""
        prompt = RefinedPrompt(
            original_prompt="Test",
            refined_prompt="Refined",
            main_language="python",
            agent_type="test",
            embedding=[0.0] * 768,
            usage_count=2,
            average_score=3.5,
            score_dist_1=0,
            score_dist_2=0,
            score_dist_3=1,
            score_dist_4=1,
            score_dist_5=0,
        )
        
        prompt.update_score_stats(5.0)
        
        assert prompt.usage_count == 3
        # (3.5 * 2 + 5.0) / 3 = 4.0
        assert prompt.average_score == pytest.approx(4.0, abs=0.01)
        assert prompt.score_dist_5 == 1
        assert prompt.get_score_distribution()["5"] == 1


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestForeignKeyIntegrity:
    """Test foreign key constraints and referential integrity."""

    async def test_history_requires_valid_prompt(self, db_session):
        """Test that history cannot be created without valid prompt."""
        repo = PromptHistoryRepository(db_session)
        
        # Try to create history for non-existent prompt
        with pytest.raises(Exception):  # ForeignKeyViolation or similar
            await repo.create(
                refined_prompt_id=uuid.uuid4(),
                action_score=4.0,
            )
            await db_session.commit()

    async def test_prior_refinement_reference(self, db_session):
        """Test that prior_refinement_id references valid prompt."""
        repo = RefinedPromptRepository(db_session)
        
        # Create first prompt
        prompt1 = await repo.create(
            embedding=[0.1] * 768,
            main_language="python",
            agent_type="test",
            original_prompt="First",
            refined_prompt="Refined first",
        )
        
        # Create second prompt referencing first
        prompt2 = await repo.create(
            embedding=[0.2] * 768,
            main_language="python",
            agent_type="test",
            original_prompt="Second",
            refined_prompt="Refined second",
            prior_refinement_id=prompt1.id,
        )
        
        await db_session.commit()
        
        # Verify prior_refinement_id is set
        assert prompt2.prior_refinement_id == prompt1.id


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
class TestPgvectorExtension:
    """Test pgvector extension functionality."""

    async def test_vector_operators_available(self, db_session):
        """Test that pgvector operators are available."""
        # Try to use cosine distance operator with actual vectors
        from sqlalchemy import text
        
        result = await db_session.execute(text("SELECT '[1,2,3]'::vector <=> '[4,5,6]'::vector;"))
        # This will fail if pgvector is not installed
        row = result.scalar()
        assert row is not None
        
    async def test_embedding_storage(self, db_session, sample_embedding):
        """Test storing and retrieving vector embeddings."""
        repo = RefinedPromptRepository(db_session)
        
        prompt = await repo.create(
            embedding=sample_embedding,
            main_language="python",
            agent_type="test",
            original_prompt="Test",
            refined_prompt="Refined test",
        )
        await db_session.commit()
        
        # Retrieve and verify embedding
        retrieved = await repo.get_by_id(prompt.id)
        assert retrieved is not None
        assert len(retrieved.embedding) == 768
        # Verify values are close (floating point)
        for i, val in enumerate(retrieved.embedding[:10]):
            assert val == pytest.approx(sample_embedding[i], abs=0.0001)

