"""add_progress_field_to_conversions

Revision ID: 013cba34ee27
Revises: eea987b32a73
Create Date: 2025-08-16 14:35:43.071564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013cba34ee27'
down_revision = 'eea987b32a73'
branch_labels = None
depends_on = None


def upgrade():
    # Add progress column to conversions table
    op.add_column('conversions', sa.Column('progress', sa.Integer(), nullable=True))


def downgrade():
    # Remove progress column from conversions table
    op.drop_column('conversions', 'progress')
