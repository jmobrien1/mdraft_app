"""add_conversion_idempotency_constraints

Revision ID: add_conversion_idempotency_constraints
Revises: 2a301fa09a8a
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_conversion_idempotency_constraints'
down_revision = '2a301fa09a8a'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique constraints and indexes for atomic upload→job creation.
    
    This migration adds:
    1. Unique constraint on (sha256, owner_user_id NULLS FIRST, owner_visitor_id NULLS FIRST)
       to ensure only one conversion per file per owner
    2. Index on (status, owner_user_id) for efficient lookups
    3. Index on (status, visitor_session_id) for anonymous user lookups
    
    These constraints ensure idempotent upload processing under concurrency.
    """
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL-specific operations
        
        # Add unique constraint for idempotency
        # This ensures only one conversion per SHA256 per owner
        op.execute("""
            ALTER TABLE conversions 
            ADD CONSTRAINT uq_conversions_sha256_owner 
            UNIQUE (sha256, user_id NULLS FIRST, visitor_session_id NULLS FIRST)
            WHERE sha256 IS NOT NULL
        """)
        
        # Add composite index for status + user_id lookups
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_conversions_status_user_id 
            ON conversions (status, user_id) 
            WHERE user_id IS NOT NULL
        """)
        
        # Add composite index for status + visitor_session_id lookups
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_conversions_status_visitor_id 
            ON conversions (status, visitor_session_id) 
            WHERE visitor_session_id IS NOT NULL
        """)
        
    else:
        # SQLite-specific operations (for development/testing)
        # Note: SQLite doesn't support partial indexes, so we create full indexes
        
        # Add unique constraint (SQLite doesn't support partial unique constraints)
        op.create_unique_constraint(
            'uq_conversions_sha256_owner', 
            'conversions', 
            ['sha256', 'user_id', 'visitor_session_id']
        )
        
        # Add composite indexes
        op.create_index(
            'ix_conversions_status_user_id', 
            'conversions', 
            ['status', 'user_id']
        )
        op.create_index(
            'ix_conversions_status_visitor_id', 
            'conversions', 
            ['status', 'visitor_session_id']
        )


def downgrade():
    """Remove constraints and indexes added by this migration."""
    
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # Remove unique constraint
        op.execute("ALTER TABLE conversions DROP CONSTRAINT IF EXISTS uq_conversions_sha256_owner")
        
        # Remove indexes
        op.execute("DROP INDEX IF EXISTS ix_conversions_status_user_id")
        op.execute("DROP INDEX IF EXISTS ix_conversions_status_visitor_id")
        
    else:
        # SQLite operations
        op.drop_constraint('uq_conversions_sha256_owner', 'conversions', type_='unique')
        op.drop_index('ix_conversions_status_user_id')
        op.drop_index('ix_conversions_status_visitor_id')
