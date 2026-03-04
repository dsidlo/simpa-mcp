"""Add refinement_type column to refined_prompts.

Revision ID: 008
Revises: 007
Create Date: 2026-03-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add refinement_type column to track how prompt was created."""
    # Add refinement_type column with default 'sigmoid'
    op.add_column(
        "refined_prompts",
        sa.Column(
            "refinement_type",
            sa.String(20),
            nullable=False,
            server_default="sigmoid",
        ),
    )
    
    # Create index for filtering by refinement type
    op.create_index(
        "idx_refined_prompts_refinement_type",
        "refined_prompts",
        ["refinement_type"],
    )


def downgrade() -> None:
    """Remove refinement_type column."""
    op.drop_index("idx_refined_prompts_refinement_type", table_name="refined_prompts")
    op.drop_column("refined_prompts", "refinement_type")
