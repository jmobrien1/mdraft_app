"""merge all heads final

Revision ID: merge_all_heads_final
Revises: add_visitor_session_to_jobs, ensure_visitor_session_id_column, add_progress_to_conversions_fixed
Create Date: 2025-08-19 02:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_all_heads_final'
down_revision = None
branch_labels = None
depends_on = None

# Multiple heads to merge
depends_on = ('add_visitor_session_to_jobs', 'ensure_visitor_session_id_column', 'add_progress_to_conversions_fixed')


def upgrade():
    """Merge all divergent heads."""
    # This is a merge migration - no schema changes needed
    # The actual schema changes are handled by the individual migrations
    pass


def downgrade():
    """This is a merge migration - no downgrade needed."""
    pass
