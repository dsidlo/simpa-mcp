"""Add hash index for exact refined prompt matching.

Revision ID: 007
Revises: 006_remove_score_distribution.py
Create Date: 2025-03-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_refined_prompt_hash_index'
down_revision = '006_remove_score_distribution'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add functional index for exact text matching."""
    # Create functional index using md5 hash for efficient exact matching
    # This allows O(1) lookups for duplicate refined prompts
    op.create_index(
        'idx_refined_prompt_md5_hash',
        'refined_prompts',
        [sa.text('md5(refined_prompt)')],
        unique=False,
        postgresql_using='hash'
    )
    
    # Also create index for original_prompt hash for completeness
    op.create_index(
        'idx_original_prompt_md5_hash',
        'refined_prompts',
        [sa.text('md5(original_prompt)')],
        unique=False,
        postgresql_using='hash'
    )


def downgrade() -> None:
    """Remove hash indexes."""
    op.drop_index('idx_refined_prompt_md5_hash', table_name='refined_prompts')
    op.drop_index('idx_original_prompt_md5_hash', table_name='refined_prompts')
