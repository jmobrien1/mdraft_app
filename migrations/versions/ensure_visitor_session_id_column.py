"""Ensure visitor_session_id column exists in jobs table

Revision ID: ensure_visitor_session_id_column
Revises: add_visitor_session_to_jobs
Create Date: 2025-08-18 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ensure_visitor_session_id_column'
down_revision = 'add_visitor_session_to_jobs'
branch_labels = None
depends_on = None


def upgrade():
    """Ensure visitor_session_id column exists in jobs table."""
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # Check if column exists
        inspector = sa.inspect(connection)
        columns = [col['name'] for col in inspector.get_columns('jobs')]
        
        if 'visitor_session_id' not in columns:
            # Add visitor_session_id column
            op.execute("ALTER TABLE public.jobs ADD COLUMN visitor_session_id VARCHAR(64);")
            
            # Create index on visitor_session_id
            op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_visitor_session_id ON public.jobs (visitor_session_id);")
            
            # Make user_id nullable if not already
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
            # Column exists, just ensure index and constraints
            op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_visitor_session_id ON public.jobs (visitor_session_id);")
            
            # Add check constraint if it doesn't exist
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
            # Add column if it doesn't exist
            try:
                batch_op.add_column(sa.Column('visitor_session_id', sa.String(length=64), nullable=True))
                batch_op.create_index(batch_op.f('ix_jobs_visitor_session_id'), ['visitor_session_id'], unique=False)
            except Exception:
                # Column might already exist, just ensure index
                batch_op.create_index(batch_op.f('ix_jobs_visitor_session_id'), ['visitor_session_id'], unique=False)


def downgrade():
    """This migration is safe to run multiple times, no downgrade needed."""
    pass
