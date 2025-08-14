"""Add anonymous proposal support

Revision ID: add_anonymous_proposal_support
Revises: dc5d95cfb925
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_anonymous_proposal_support'
down_revision = 'dc5d95cfb925'
branch_labels = None
depends_on = None


def upgrade():
    # Add visitor_session_id column to proposals table
    op.add_column('proposals', sa.Column('visitor_session_id', sa.String(length=64), nullable=True))
    
    # Add expires_at column for anonymous proposal TTL
    op.add_column('proposals', sa.Column('expires_at', sa.DateTime(), nullable=True))
    
    # For SQLite, we need to recreate the table to make user_id nullable
    # This is a simplified approach - in production with PostgreSQL, use ALTER COLUMN
    with op.batch_alter_table('proposals') as batch_op:
        batch_op.alter_column('user_id', nullable=True)
    
    # Add check constraint to ensure at least one owner is present
    # Note: SQLite doesn't support CHECK constraints in the same way
    # This will be handled at the application level
    
    # Add index on visitor_session_id for performance
    op.create_index('ix_proposals_visitor_session_id', 'proposals', ['visitor_session_id'])
    
    # Add index on expires_at for cleanup queries
    op.create_index('ix_proposals_expires_at', 'proposals', ['expires_at'])


def downgrade():
    # Remove indexes
    op.drop_index('ix_proposals_expires_at', 'proposals')
    op.drop_index('ix_proposals_visitor_session_id', 'proposals')
    
    # Remove columns
    op.drop_column('proposals', 'expires_at')
    op.drop_column('proposals', 'visitor_session_id')
    
    # Make user_id non-nullable again
    with op.batch_alter_table('proposals') as batch_op:
        batch_op.alter_column('user_id', nullable=False)
