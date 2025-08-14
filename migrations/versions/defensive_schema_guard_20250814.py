"""defensive schema guard 20250814

Revision ID: defensive_schema_guard_20250814
Revises: d4ef9d459d1a
Create Date: 2025-08-14 15:07:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'defensive_schema_guard_20250814'
down_revision = 'd4ef9d459d1a'
branch_labels = None
depends_on = None


def upgrade():
    """Mirror schema_guard operations - idempotent DDL."""
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # --- PROPOSALS: columns (PostgreSQL) ---
        op.execute("ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);")
        op.execute("ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;")
        
        # --- PROPOSALS: indexes (PostgreSQL) ---
        op.execute("CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_proposals_expires_at ON public.proposals (expires_at);")
        
        # --- PROPOSALS: owner check constraint (PostgreSQL) ---
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_proposals_owner_present') THEN
                ALTER TABLE public.proposals
                ADD CONSTRAINT ck_proposals_owner_present
                CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
            END IF;
        END $$;
        """)
        
        # --- CONVERSIONS: columns (PostgreSQL) ---
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;")
        
        # --- CONVERSIONS: indexes (PostgreSQL) ---
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);")
        
        # --- CONVERSIONS: optional FK to users (PostgreSQL) ---
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_conversions_user_id_users'
            ) THEN
                ALTER TABLE public.conversions
                ADD CONSTRAINT fk_conversions_user_id_users
                FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """)
        
        # --- CONVERSIONS: optional FK to proposals (PostgreSQL) ---
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_conversions_proposal_id_proposals'
            ) THEN
                ALTER TABLE public.conversions
                ADD CONSTRAINT fk_conversions_proposal_id_proposals
                FOREIGN KEY (proposal_id) REFERENCES public.proposals(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """)
        
        # --- BACKFILL owners on conversions from proposals (PostgreSQL) ---
        op.execute("""
        UPDATE public.conversions c
        SET user_id = p.user_id
        FROM public.proposals p
        WHERE c.proposal_id = p.id
          AND c.user_id IS NULL
          AND p.user_id IS NOT NULL;
        """)
        
        op.execute("""
        UPDATE public.conversions c
        SET visitor_session_id = p.visitor_session_id
        FROM public.proposals p
        WHERE c.proposal_id = p.id
          AND c.visitor_session_id IS NULL
          AND p.visitor_session_id IS NOT NULL;
        """)
        
    elif dialect == 'sqlite':
        # For SQLite, use Alembic operations which handle the dialect differences
        # These operations are safe to run multiple times
        
        # --- PROPOSALS: columns (SQLite) ---
        with op.batch_alter_table('proposals') as batch_op:
            # Add columns - SQLite batch_alter_table handles duplicates gracefully
            batch_op.add_column(sa.Column('visitor_session_id', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        
        # --- PROPOSALS: indexes (SQLite) ---
        # These will fail gracefully if indexes already exist
        try:
            op.create_index('ix_proposals_visitor_session_id', 'proposals', ['visitor_session_id'], unique=False)
        except:
            pass
        try:
            op.create_index('ix_proposals_expires_at', 'proposals', ['expires_at'], unique=False)
        except:
            pass
        
        # --- CONVERSIONS: columns (SQLite) ---
        with op.batch_alter_table('conversions') as batch_op:
            # Add columns - SQLite batch_alter_table handles duplicates gracefully
            batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('visitor_session_id', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('proposal_id', sa.Integer(), nullable=True))
        
        # --- CONVERSIONS: indexes (SQLite) ---
        # These will fail gracefully if indexes already exist
        try:
            op.create_index('ix_conversions_user_id', 'conversions', ['user_id'], unique=False)
        except:
            pass
        try:
            op.create_index('ix_conversions_visitor_session_id', 'conversions', ['visitor_session_id'], unique=False)
        except:
            pass
        try:
            op.create_index('ix_conversions_proposal_id', 'conversions', ['proposal_id'], unique=False)
        except:
            pass
        
        # Note: SQLite doesn't support the complex UPDATE with FROM clause
        # The backfill will be handled by the schema_guard script in production


def downgrade():
    """Leave empty to avoid destructive downgrades in production."""
    pass
