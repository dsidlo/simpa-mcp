"""Add project_structure column to projects table

Revision ID: 010
Revises: 009
Create Date: 2025-03-05 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'


def upgrade():
    # Add project_structure column to projects table
    op.add_column(
        'projects',
        sa.Column(
            'project_structure',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        )
    )
    
    # Create index for efficient JSONB queries
    op.create_index(
        'ix_projects_structure',
        'projects',
        ['project_structure'],
        postgresql_using='gin'
    )


def downgrade():
    # Remove index and column
    op.drop_index('ix_projects_structure', table_name='projects')
    op.drop_column('projects', 'project_structure')
