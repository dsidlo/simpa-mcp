"""Add optimization schema for caching and diff saliency.

Revision ID: 003
Revises: 002
Create Date: 2026-03-03 05:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index on original_prompt_hash for fast lookups
    op.create_index(
        op.f('ix_refined_prompts_original_prompt_hash'),
        'refined_prompts',
        ['original_prompt_hash'],
        unique=False
    )
    
    # Add composite index for hash + agent_type lookups
    op.create_index(
        op.f('ix_refined_prompts_hash_agent'),
        'refined_prompts',
        ['original_prompt_hash', 'agent_type'],
        unique=False
    )
    
    # Add saliency_metadata column to prompt_history
    op.add_column(
        'prompt_history',
        sa.Column('saliency_metadata', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    # Drop saliency_metadata column
    op.drop_column('prompt_history', 'saliency_metadata')
    
    # Drop hash indexes
    op.drop_index(
        op.f('ix_refined_prompts_hash_agent'),
        table_name='refined_prompts'
    )
    op.drop_index(
        op.f('ix_refined_prompts_original_prompt_hash'),
        table_name='refined_prompts'
    )
