"""add_hot_indexes

Revision ID: 2a301fa09a8a
Revises: align_production_schema_20250815
Create Date: 2025-08-16 09:33:09.955144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a301fa09a8a'
down_revision = 'add_visitor_session_to_jobs'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes for hot queries to improve performance.
    
    This migration adds indexes for frequently queried columns:
    
    conversions table:
    - sha256 (already exists, but ensure it's optimized)
    - status (for filtering by conversion status)
    - user_id (for user-specific queries)
    - visitor_session_id (for anonymous user queries)
    
    jobs table:
    - user_id (for user-specific job queries)
    - status (for filtering by job status)
    - created_at (for time-based queries and sorting)
    
    users table:
    - email (already exists, but ensure it's optimized)
    """
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL-specific operations
        
        # --- CONVERSIONS TABLE INDEXES ---
        
        # Ensure sha256 index exists (may already exist from baseline)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_sha256 ON public.conversions (sha256);")
        
        # Add status index for filtering conversions by status
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_status ON public.conversions (status);")
        
        # Add user_id index for user-specific conversion queries
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);")
        
        # Add visitor_session_id index for anonymous user queries
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);")
        
        # --- JOBS TABLE INDEXES ---
        
        # Add user_id index for user-specific job queries
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON public.jobs (user_id);")
        
        # Add status index for filtering jobs by status
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_status ON public.jobs (status);")
        
        # Add created_at index for time-based queries and sorting
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_created_at ON public.jobs (created_at);")
        
        # --- USERS TABLE INDEXES ---
        
        # Ensure email index exists (may already exist from baseline)
        op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON public.users (email);")
        
        # Add composite index for common query pattern: sha256 + status
        # This optimizes queries like: Conversion.query.filter_by(sha256=..., status="COMPLETED")
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_sha256_status ON public.conversions (sha256, status);")
        
    else:
        # SQLite-specific operations (for development/testing)
        
        # --- CONVERSIONS TABLE INDEXES ---
        op.create_index('ix_conversions_sha256', 'conversions', ['sha256'], unique=False)
        op.create_index('ix_conversions_status', 'conversions', ['status'], unique=False)
        op.create_index('ix_conversions_user_id', 'conversions', ['user_id'], unique=False)
        op.create_index('ix_conversions_visitor_session_id', 'conversions', ['visitor_session_id'], unique=False)
        op.create_index('ix_conversions_sha256_status', 'conversions', ['sha256', 'status'], unique=False)
        
        # --- JOBS TABLE INDEXES ---
        op.create_index('ix_jobs_user_id', 'jobs', ['user_id'], unique=False)
        op.create_index('ix_jobs_status', 'jobs', ['status'], unique=False)
        op.create_index('ix_jobs_created_at', 'jobs', ['created_at'], unique=False)
        
        # --- USERS TABLE INDEXES ---
        op.create_index('ix_users_email', 'users', ['email'], unique=False)


def downgrade():
    """Remove indexes added by this migration."""
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL-specific operations
        
        # Drop indexes in reverse order
        op.execute("DROP INDEX IF EXISTS ix_conversions_sha256_status;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_visitor_session_id;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_user_id;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_status;")
        # Note: Don't drop ix_conversions_sha256 as it may have been created in baseline
        
        op.execute("DROP INDEX IF EXISTS ix_jobs_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_jobs_status;")
        op.execute("DROP INDEX IF EXISTS ix_jobs_user_id;")
        
        # Note: Don't drop ix_users_email as it may have been created in baseline
        
    else:
        # SQLite-specific operations
        op.drop_index('ix_conversions_sha256_status', table_name='conversions')
        op.drop_index('ix_conversions_visitor_session_id', table_name='conversions')
        op.drop_index('ix_conversions_user_id', table_name='conversions')
        op.drop_index('ix_conversions_status', table_name='conversions')
        op.drop_index('ix_conversions_sha256', table_name='conversions')
        
        op.drop_index('ix_jobs_created_at', table_name='jobs')
        op.drop_index('ix_jobs_status', table_name='jobs')
        op.drop_index('ix_jobs_user_id', table_name='jobs')
        
        op.drop_index('ix_users_email', table_name='users')
