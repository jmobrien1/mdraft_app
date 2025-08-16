"""add_composite_indexes_for_hot_read_paths

Revision ID: eea987b32a73
Revises: 2fdc7f5bc1b4
Create Date: 2025-08-16 13:52:56.001289

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eea987b32a73'
down_revision = '2fdc7f5bc1b4'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite indexes for hot read paths to optimize common query patterns.
    
    This migration adds composite indexes for frequently used query patterns:
    
    Jobs table:
    - (status, created_at) - for filtering by status and sorting by date
    - (user_id, status) - for user-specific status queries
    - (user_id, created_at) - for user-specific date range queries
    - (visitor_session_id, status) - for anonymous user status queries
    - (visitor_session_id, created_at) - for anonymous user date range queries
    
    Conversions table:
    - (status, created_at) - for filtering by status and sorting by date
    - (user_id, status) - for user-specific status queries
    - (user_id, created_at) - for user-specific date range queries
    - (visitor_session_id, status) - for anonymous user status queries
    - (visitor_session_id, created_at) - for anonymous user date range queries
    - (sha256, status) - for idempotency checks (already exists, but ensure it's optimized)
    
    These indexes will significantly improve performance for:
    - Job/Conversion listing with status filtering
    - User-specific queries with date ranges
    - Worker processing queries
    - Idempotency checks
    """
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL-specific operations
        
        # --- JOBS TABLE COMPOSITE INDEXES ---
        
        # Index for status + created_at (common pattern for listing with sorting)
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_status_created_at ON public.jobs (status, created_at DESC);")
        
        # Index for user_id + status (user-specific status queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id_status ON public.jobs (user_id, status);")
        
        # Index for user_id + created_at (user-specific date range queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id_created_at ON public.jobs (user_id, created_at DESC);")
        
        # Index for visitor_session_id + status (anonymous user status queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_visitor_session_id_status ON public.jobs (visitor_session_id, status);")
        
        # Index for visitor_session_id + created_at (anonymous user date range queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_visitor_session_id_created_at ON public.jobs (visitor_session_id, created_at DESC);")
        
        # --- CONVERSIONS TABLE COMPOSITE INDEXES ---
        
        # Index for status + created_at (common pattern for listing with sorting)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_status_created_at ON public.conversions (status, created_at DESC);")
        
        # Index for user_id + status (user-specific status queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_user_id_status ON public.conversions (user_id, status);")
        
        # Index for user_id + created_at (user-specific date range queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_user_id_created_at ON public.conversions (user_id, created_at DESC);")
        
        # Index for visitor_session_id + status (anonymous user status queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id_status ON public.conversions (visitor_session_id, status);")
        
        # Index for visitor_session_id + created_at (anonymous user date range queries)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id_created_at ON public.conversions (visitor_session_id, created_at DESC);")
        
        # Ensure sha256 + status index exists (for idempotency checks)
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_sha256_status ON public.conversions (sha256, status);")
        
    else:
        # SQLite-specific operations (for development/testing)
        
        # --- JOBS TABLE COMPOSITE INDEXES ---
        op.create_index('ix_jobs_status_created_at', 'jobs', ['status', 'created_at'], unique=False)
        op.create_index('ix_jobs_user_id_status', 'jobs', ['user_id', 'status'], unique=False)
        op.create_index('ix_jobs_user_id_created_at', 'jobs', ['user_id', 'created_at'], unique=False)
        op.create_index('ix_jobs_visitor_session_id_status', 'jobs', ['visitor_session_id', 'status'], unique=False)
        op.create_index('ix_jobs_visitor_session_id_created_at', 'jobs', ['visitor_session_id', 'created_at'], unique=False)
        
        # --- CONVERSIONS TABLE COMPOSITE INDEXES ---
        op.create_index('ix_conversions_status_created_at', 'conversions', ['status', 'created_at'], unique=False)
        op.create_index('ix_conversions_user_id_status', 'conversions', ['user_id', 'status'], unique=False)
        op.create_index('ix_conversions_user_id_created_at', 'conversions', ['user_id', 'created_at'], unique=False)
        op.create_index('ix_conversions_visitor_session_id_status', 'conversions', ['visitor_session_id', 'status'], unique=False)
        op.create_index('ix_conversions_visitor_session_id_created_at', 'conversions', ['visitor_session_id', 'created_at'], unique=False)
        op.create_index('ix_conversions_sha256_status', 'conversions', ['sha256', 'status'], unique=False)


def downgrade():
    """Remove composite indexes added by this migration."""
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL-specific operations
        
        # Drop indexes in reverse order
        op.execute("DROP INDEX IF EXISTS ix_conversions_sha256_status;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_visitor_session_id_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_visitor_session_id_status;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_user_id_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_user_id_status;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_status_created_at;")
        
        op.execute("DROP INDEX IF EXISTS ix_jobs_visitor_session_id_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_jobs_visitor_session_id_status;")
        op.execute("DROP INDEX IF EXISTS ix_jobs_user_id_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_jobs_user_id_status;")
        op.execute("DROP INDEX IF EXISTS ix_jobs_status_created_at;")
        
    else:
        # SQLite-specific operations
        op.drop_index('ix_conversions_sha256_status', table_name='conversions')
        op.drop_index('ix_conversions_visitor_session_id_created_at', table_name='conversions')
        op.drop_index('ix_conversions_visitor_session_id_status', table_name='conversions')
        op.drop_index('ix_conversions_user_id_created_at', table_name='conversions')
        op.drop_index('ix_conversions_user_id_status', table_name='conversions')
        op.drop_index('ix_conversions_status_created_at', table_name='conversions')
        
        op.drop_index('ix_jobs_visitor_session_id_created_at', table_name='jobs')
        op.drop_index('ix_jobs_visitor_session_id_status', table_name='jobs')
        op.drop_index('ix_jobs_user_id_created_at', table_name='jobs')
        op.drop_index('ix_jobs_user_id_status', table_name='jobs')
        op.drop_index('ix_jobs_status_created_at', table_name='jobs')
