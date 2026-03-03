"""Update schema for architecture specifications.

Revision ID: 002
Revises: 001
Create Date: 2026-03-03 04:38:00.000000

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to refined_prompts table
    op.add_column('refined_prompts', sa.Column('prompt_key', postgresql.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')))
    op.add_column('refined_prompts', sa.Column('original_prompt_hash', sa.String(length=64), nullable=True))
    op.add_column('refined_prompts', sa.Column('domain', sa.String(length=100), nullable=True))
    op.add_column('refined_prompts', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('refined_prompts', sa.Column('refinement_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('refined_prompts', sa.Column('score_weighted', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('refined_prompts', sa.Column('score_dist_1', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('refined_prompts', sa.Column('score_dist_2', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('refined_prompts', sa.Column('score_dist_3', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('refined_prompts', sa.Column('score_dist_4', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('refined_prompts', sa.Column('score_dist_5', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('refined_prompts', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('refined_prompts', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    # Make embedding nullable for testing without embeddings
    op.alter_column('refined_prompts', 'embedding',
                    existing_type=pgvector.sqlalchemy.Vector(768),
                    nullable=True)
    
    # Make main_language nullable
    op.alter_column('refined_prompts', 'main_language',
                    existing_type=sa.String(length=50),
                    nullable=True)
    
    # Create unique index on prompt_key
    op.create_unique_constraint('uq_refined_prompts_prompt_key', 'refined_prompts', ['prompt_key'])
    
    # Create index on domain
    op.create_index(op.f('ix_refined_prompts_domain'), 'refined_prompts', ['domain'], unique=False)
    
    # Add new columns to prompt_history table
    op.add_column('prompt_history', sa.Column('request_id', postgresql.UUID(), nullable=True))
    op.add_column('prompt_history', sa.Column('executed_by_agent', sa.String(length=100), nullable=True))
    op.add_column('prompt_history', sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('prompt_history', sa.Column('test_passed', sa.Boolean(), nullable=True))
    op.add_column('prompt_history', sa.Column('lint_score', sa.Float(), nullable=True))
    op.add_column('prompt_history', sa.Column('security_scan_passed', sa.Boolean(), nullable=True))
    op.add_column('prompt_history', sa.Column('files_added', sa.JSON(), nullable=True))
    op.add_column('prompt_history', sa.Column('files_deleted', sa.JSON(), nullable=True))
    op.add_column('prompt_history', sa.Column('execution_duration_ms', sa.Integer(), nullable=True))
    op.add_column('prompt_history', sa.Column('agent_output_summary', sa.Text(), nullable=True))
    
    # Rename refined_prompt_id to prompt_id for consistency
    op.alter_column('prompt_history', 'refined_prompt_id', new_column_name='prompt_id')
    op.drop_index('ix_prompt_history_refined_prompt_id', table_name='prompt_history')
    op.create_index(op.f('ix_prompt_history_prompt_id'), 'prompt_history', ['prompt_id'], unique=False)
    
    # Create index on executed_at
    op.create_index(op.f('ix_prompt_history_executed_at'), 'prompt_history', ['executed_at'], unique=False)
    
    # Create SQL functions for stored procedures
    op.execute("""
        CREATE OR REPLACE FUNCTION find_similar_prompts(
            query_embedding VECTOR(768),
            target_agent_type VARCHAR(100),
            match_threshold FLOAT DEFAULT 0.7,
            max_results INTEGER DEFAULT 5
        )
        RETURNS TABLE(
            prompt_id INTEGER,
            prompt_key UUID,
            similarity FLOAT,
            average_score DECIMAL(3,2),
            usage_count INTEGER,
            refined_prompt TEXT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                rp.id as prompt_id,
                rp.prompt_key,
                1 - (rp.embedding <=> query_embedding) as similarity,
                rp.average_score,
                rp.usage_count,
                rp.refined_prompt
            FROM refined_prompts rp
            WHERE rp.agent_type = target_agent_type
                AND rp.is_active = TRUE
                AND 1 - (rp.embedding <=> query_embedding) > match_threshold
                AND rp.usage_count > 0
            ORDER BY similarity DESC, rp.average_score DESC
            LIMIT max_results;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Drop stored procedure
    op.execute("DROP FUNCTION IF EXISTS find_similar_prompts(VECTOR(768), VARCHAR(100), FLOAT, INTEGER)")
    
    # Drop new indexes
    op.drop_index(op.f('ix_prompt_history_executed_at'), table_name='prompt_history')
    op.drop_index(op.f('ix_prompt_history_prompt_id'), table_name='prompt_history')
    op.drop_index(op.f('ix_refined_prompts_domain'), table_name='refined_prompts')
    
    # Revert column renames
    op.alter_column('prompt_history', 'prompt_id', new_column_name='refined_prompt_id')
    op.create_index('ix_prompt_history_refined_prompt_id', 'prompt_history', ['refined_prompt_id'])
    
    # Drop columns from prompt_history
    op.drop_column('prompt_history', 'agent_output_summary')
    op.drop_column('prompt_history', 'execution_duration_ms')
    op.drop_column('prompt_history', 'files_deleted')
    op.drop_column('prompt_history', 'files_added')
    op.drop_column('prompt_history', 'security_scan_passed')
    op.drop_column('prompt_history', 'lint_score')
    op.drop_column('prompt_history', 'test_passed')
    op.drop_column('prompt_history', 'executed_at')
    op.drop_column('prompt_history', 'executed_by_agent')
    op.drop_column('prompt_history', 'request_id')
    
    # Drop unique constraint and columns from refined_prompts
    op.drop_constraint('uq_refined_prompts_prompt_key', 'refined_prompts', type_='unique')
    
    op.drop_column('refined_prompts', 'is_active')
    op.drop_column('refined_prompts', 'last_used_at')
    op.drop_column('refined_prompts', 'score_dist_5')
    op.drop_column('refined_prompts', 'score_dist_4')
    op.drop_column('refined_prompts', 'score_dist_3')
    op.drop_column('refined_prompts', 'score_dist_2')
    op.drop_column('refined_prompts', 'score_dist_1')
    op.drop_column('refined_prompts', 'score_weighted')
    op.drop_column('refined_prompts', 'refinement_version')
    op.drop_column('refined_prompts', 'tags')
    op.drop_column('refined_prompts', 'domain')
    op.drop_column('refined_prompts', 'original_prompt_hash')
    op.drop_column('refined_prompts', 'prompt_key')
    
    # Revert nullable changes
    op.alter_column('refined_prompts', 'embedding',
                    existing_type=pgvector.sqlalchemy.Vector(768),
                    nullable=False)
    op.alter_column('refined_prompts', 'main_language',
                    existing_type=sa.String(length=50),
                    nullable=False)
