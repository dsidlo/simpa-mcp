"""Add BM25 search tables

Revision ID: 009
Revises: 008
Create Date: 2026-03-04 15:00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009f2b8c6e3a'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # BM25 document statistics table
    op.create_table(
        'bm25_doc_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('total_docs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_doc_length', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # BM25 term statistics table
    op.create_table(
        'bm25_term_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('term', sa.String(), nullable=False),
        sa.Column('doc_freq', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('term')
    )
    
    # BM25 term frequency per document table
    op.create_table(
        'bm25_term_freq',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('term', sa.String(), nullable=False),
        sa.Column('term_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('doc_length', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prompt_id', 'term')
    )
    
    # Indexes
    op.create_index('idx_bm25_term_freq_term', 'bm25_term_freq', ['term'])
    op.create_index('idx_bm25_term_freq_prompt_id', 'bm25_term_freq', ['prompt_id'])
    op.create_index('idx_bm25_term_stats_term', 'bm25_term_stats', ['term'])
    
    # Foreign key to refined_prompts
    op.create_foreign_key(
        'fk_bm25_term_freq_prompt_id',
        'bm25_term_freq', 'refined_prompts',
        ['prompt_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    op.drop_constraint('fk_bm25_term_freq_prompt_id', 'bm25_term_freq', type_='foreignkey')
    op.drop_index('idx_bm25_term_freq_term', table_name='bm25_term_freq')
    op.drop_index('idx_bm25_term_freq_prompt_id', table_name='bm25_term_freq')
    op.drop_index('idx_bm25_term_stats_term', table_name='bm25_term_stats')
    op.drop_table('bm25_term_freq')
    op.drop_table('bm25_term_stats')
    op.drop_table('bm25_doc_stats')
