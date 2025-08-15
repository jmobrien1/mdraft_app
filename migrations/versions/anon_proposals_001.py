"""Allow anonymous proposals (user_id nullable; add visitor_session_id, expires_at)

Revision ID: anon_proposals_001
Revises: defensive_schema_guard_20250814
Create Date: 2025-08-15 09:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "anon_proposals_001"
down_revision = "defensive_schema_guard_20250814"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("proposals")}

    # Make user_id nullable (safe even if already nullable)
    with op.batch_alter_table("proposals", schema=None) as batch:
        batch.alter_column("user_id",
                           existing_type=sa.Integer(),
                           existing_nullable=False,
                           nullable=True)

        if "visitor_session_id" not in cols:
            batch.add_column(sa.Column("visitor_session_id", sa.String(length=64), nullable=True))
            batch.create_index("ix_proposals_visitor_session_id", ["visitor_session_id"], unique=False)

        if "expires_at" not in cols:
            batch.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
            batch.create_index("ix_proposals_expires_at", ["expires_at"], unique=False)

def downgrade():
    # Best-effort downgrade: drop newly-added columns/indexes; making user_id NOT NULL again
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("proposals")}

    with op.batch_alter_table("proposals", schema=None) as batch:
        if "ix_proposals_expires_at" in {i["name"] for i in insp.get_indexes("proposals")}:
            batch.drop_index("ix_proposals_expires_at")
        if "expires_at" in cols:
            batch.drop_column("expires_at")

        if "ix_proposals_visitor_session_id" in {i["name"] for i in insp.get_indexes("proposals")}:
            batch.drop_index("ix_proposals_visitor_session_id")
        if "visitor_session_id" in cols:
            batch.drop_column("visitor_session_id")

        # If you truly need to enforce NOT NULL again:
        batch.alter_column("user_id",
                           existing_type=sa.Integer(),
                           existing_nullable=True,
                           nullable=False)
