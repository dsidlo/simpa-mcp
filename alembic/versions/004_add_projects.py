"""Add projects table and project_id foreign keys.

Revision ID: 004
Revises: 003
Create Date: 2026-03-03 07:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('main_language', sa.String(length=50), nullable=True),
        sa.Column('other_languages', sa.JSON(), nullable=True),
        sa.Column('library_dependencies', sa.JSON(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=True,
        ),
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_name'),
    )
    
    # Create indexes on projects table
    op.create_index(
        op.f('ix_projects_project_name'),
        'projects',
        ['project_name'],
        unique=False,
    )
    op.create_index(
        op.f('ix_projects_main_language'),
        'projects',
        ['main_language'],
        unique=False,
    )
    
    # Add project_id to refined_prompts table
    op.add_column(
        'refined_prompts',
        sa.Column('project_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f('fk_refined_prompts_project_id_projects'),
        'refined_prompts',
        'projects',
        ['project_id'],
        ['id'],
    )
    op.create_index(
        op.f('ix_refined_prompts_project_id'),
        'refined_prompts',
        ['project_id'],
        unique=False,
    )
    
    # Add project_id to prompt_history table
    op.add_column(
        'prompt_history',
        sa.Column('project_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f('fk_prompt_history_project_id_projects'),
        'prompt_history',
        'projects',
        ['project_id'],
        ['id'],
    )
    op.create_index(
        op.f('ix_prompt_history_project_id'),
        'prompt_history',
        ['project_id'],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes from prompt_history
    op.drop_index(
        op.f('ix_prompt_history_project_id'),
        table_name='prompt_history',
    )
    op.drop_constraint(
        op.f('fk_prompt_history_project_id_projects'),
        'prompt_history',
        type_='foreignkey',
    )
    op.drop_column('prompt_history', 'project_id')
    
    # Drop indexes from refined_prompts
    op.drop_index(
        op.f('ix_refined_prompts_project_id'),
        table_name='refined_prompts',
    )
    op.drop_constraint(
        op.f('fk_refined_prompts_project_id_projects'),
        'refined_prompts',
        type_='foreignkey',
    )
    op.drop_column('refined_prompts', 'project_id')
    
    # Drop indexes from projects
    op.drop_index(
        op.f('ix_projects_main_language'),
        table_name='projects',
    )
    op.drop_index(
        op.f('ix_projects_project_name'),
        table_name='projects',
    )
    
    # Drop projects table
    op.drop_table('projects')
