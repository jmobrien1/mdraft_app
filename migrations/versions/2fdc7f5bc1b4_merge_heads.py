"""merge_heads

Revision ID: 2fdc7f5bc1b4
Revises: add_conversion_idempotency_constraints, add_email_verification_fields
Create Date: 2025-08-16 13:52:52.598261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2fdc7f5bc1b4'
down_revision = ('add_conversion_idempotency_constraints', 'add_email_verification_fields')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
