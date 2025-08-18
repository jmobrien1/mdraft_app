"""merge heads

Revision ID: d892bfcacae6
Revises: 20250818_add_progress_to_conversions, dfd980eee75b
Create Date: 2025-08-17 22:04:15.863742

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd892bfcacae6'
down_revision = ('20250818_add_progress_to_conversions', 'dfd980eee75b')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
