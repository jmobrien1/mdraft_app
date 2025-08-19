"""Add ingestion fields to proposal_documents table

Revision ID: add_ingestion_fields
Revises: 013cba34ee27
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_ingestion_fields'
down_revision = '013cba34ee27'
branch_labels = None
depends_on = None


def upgrade():
    # Add ingestion status field with default
    op.add_column('proposal_documents', sa.Column('ingestion_status', sa.String(20), nullable=False, server_default='none'))
    
    # Add available sections field (JSON array) with default
    op.add_column('proposal_documents', sa.Column('available_sections', postgresql.JSONB(), nullable=False, server_default='[]'))
    
    # Add ingestion error field
    op.add_column('proposal_documents', sa.Column('ingestion_error', sa.Text(), nullable=True))
    
    # Add section mapping field (JSON) with default
    op.add_column('proposal_documents', sa.Column('section_mapping', postgresql.JSONB(), nullable=True))
    
    # Create index for ingestion status
    op.create_index('ix_proposal_documents_ingestion_status', 'proposal_documents', ['ingestion_status'])
    
    # Backfill existing rows with sensible defaults
    op.execute("""
        UPDATE proposal_documents
        SET ingestion_status = CASE
            WHEN parsed_text IS NOT NULL AND length(coalesce(parsed_text, '')) > 0 THEN 'ready'
            ELSE 'none'
        END
        WHERE ingestion_status = 'none';
    """)


def downgrade():
    # Remove the columns in reverse order
    op.drop_index('ix_proposal_documents_ingestion_status', table_name='proposal_documents')
    op.drop_column('proposal_documents', 'section_mapping')
    op.drop_column('proposal_documents', 'ingestion_error')
    op.drop_column('proposal_documents', 'available_sections')
    op.drop_column('proposal_documents', 'ingestion_status')
