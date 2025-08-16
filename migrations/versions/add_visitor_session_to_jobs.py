"""Add visitor_session_id to jobs table

Revision ID: add_visitor_session_to_jobs
Revises: align_production_schema_20250815
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_visitor_session_to_jobs'
down_revision = 'align_production_schema_20250815'
branch_labels = None
depends_on = None


def upgrade():
    """Add visitor_session_id to jobs table and make user_id nullable."""
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # Add visitor_session_id column
        op.execute("ALTER TABLE IF EXISTS public.jobs ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);")
        
        # Create index on visitor_session_id
        op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_visitor_session_id ON public.jobs (visitor_session_id);")
        
        # Make user_id nullable
        op.execute("ALTER TABLE public.jobs ALTER COLUMN user_id DROP NOT NULL;")
        
        # Add check constraint to ensure at least one owner dimension is present
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_jobs_owner_present') THEN
                ALTER TABLE public.jobs
                ADD CONSTRAINT ck_jobs_owner_present
                CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
            END IF;
        END $$;
        """)
    else:
        # SQLite fallback
        with op.batch_alter_table('jobs') as batch_op:
            batch_op.add_column(sa.Column('visitor_session_id', sa.String(length=64), nullable=True))
            batch_op.create_index(batch_op.f('ix_jobs_visitor_session_id'), ['visitor_session_id'], unique=False)
            # Note: SQLite doesn't support altering column nullability easily
            # This would need a table recreation in practice


def downgrade():
    """Remove visitor_session_id from jobs table and make user_id not nullable."""
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # Remove check constraint
        op.execute("ALTER TABLE public.jobs DROP CONSTRAINT IF EXISTS ck_jobs_owner_present;")
        
        # Make user_id not nullable (this might fail if there are NULL values)
        op.execute("ALTER TABLE public.jobs ALTER COLUMN user_id SET NOT NULL;")
        
        # Drop index
        op.execute("DROP INDEX IF EXISTS ix_jobs_visitor_session_id;")
        
        # Drop column
        op.execute("ALTER TABLE public.jobs DROP COLUMN IF EXISTS visitor_session_id;")
    else:
        # SQLite fallback
        with op.batch_alter_table('jobs') as batch_op:
            batch_op.drop_index(batch_op.f('ix_jobs_visitor_session_id'))
            batch_op.drop_column('visitor_session_id')
