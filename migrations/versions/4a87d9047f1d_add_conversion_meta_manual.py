"""add conversion meta (manual)

Revision ID: 4a87d9047f1d
Revises: 475e4c1d7986
Create Date: 2025-08-11 17:05:25.289308

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4a87d9047f1d'
down_revision = '475e4c1d7986'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('conversions') as batch:
        batch.add_column(sa.Column('sha256', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('original_mime', sa.String(length=120), nullable=True))
        batch.add_column(sa.Column('original_size', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('stored_uri', sa.String(length=512), nullable=True))
        batch.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.create_index('ix_conversions_sha256', 'conversions', ['sha256'], unique=False)

def downgrade():
    op.drop_index('ix_conversions_sha256', table_name='conversions')
    with op.batch_alter_table('conversions') as batch:
        batch.drop_column('expires_at')
        batch.drop_column('stored_uri')
        batch.drop_column('original_size')
        batch.drop_column('original_mime')
        batch.drop_column('sha256')
