"""add progress to conversions

Revision ID: 20250818_add_progress_to_conversions
Revises: 013cba34ee27
Create Date: 2025-08-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250818_add_progress_to_conversions"
down_revision = "013cba34ee27"
branch_labels = None
depends_on = None


def upgrade():
    # add column if missing
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns("conversions")]
    if "progress" not in cols:
        op.add_column(
            "conversions",
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns("conversions")]
    if "progress" in cols:
        op.drop_column("conversions", "progress")
