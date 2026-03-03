"""Rename diffs_by_language to diffs in prompt_history.

Revision ID: 005
Revises: 004
Create Date: 2026-03-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename diffs_by_language to diffs in prompt_history table
    op.alter_column(
        'prompt_history',
        'diffs_by_language',
        new_column_name='diffs'
    )


def downgrade() -> None:
    # Revert: rename diffs back to diffs_by_language
    op.alter_column(
        'prompt_history',
        'diffs',
        new_column_name='diffs_by_language'
    )
