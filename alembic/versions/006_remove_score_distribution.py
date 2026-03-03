"""Remove score_distribution column from refined_prompts.

Revision ID: 006
Revises: 005
Create Date: 2026-03-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop score_distribution column (it was added manually but is not in the model)
    op.drop_column('refined_prompts', 'score_distribution')


def downgrade() -> None:
    # Add back the score_distribution column
    op.add_column('refined_prompts', sa.Column('score_distribution', sa.JSON(), nullable=False, server_default='{}'))
