"""add_email_verified_column_to_users

Revision ID: 81368a6c088c
Revises: d892bfcacae6
Create Date: 2025-08-18 15:58:58.046140

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '81368a6c088c'
down_revision = 'd892bfcacae6'
branch_labels = None
depends_on = None


def upgrade():
    """Add email_verified column to users table."""
    # Add email_verified column to users table
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    """Remove email_verified column from users table."""
    # Remove email_verified column from users table
    op.drop_column('users', 'email_verified')
