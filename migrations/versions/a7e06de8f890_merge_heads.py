"""merge heads

Revision ID: a7e06de8f890
Revises: 81368a6c088c, ensure_visitor_session_id_column
Create Date: 2025-08-18 17:38:07.834255

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7e06de8f890'
down_revision = ('81368a6c088c', 'ensure_visitor_session_id_column')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
