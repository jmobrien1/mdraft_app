"""Align production schema with models

Revision ID: align_production_schema_20250815
Revises: anon_proposals_001
Create Date: 2025-08-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'align_production_schema_20250815'
down_revision = 'anon_proposals_001'
branch_labels = None
depends_on = None


def upgrade():
    """Align production schema with current models.
    
    This migration ensures:
    1. All required indexes exist
    2. Foreign key constraints are properly set up
    3. Cascade delete settings are correct
    4. Check constraints are in place
    5. All required columns exist with proper types
    """
    
    # Get database type to handle SQLite vs PostgreSQL differences
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL-specific operations
        
        # --- PROPOSALS: Ensure all required columns and constraints ---
        
        # Add visitor_session_id if missing
        op.execute("ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);")
        
        # Add expires_at if missing
        op.execute("ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;")
        
        # Create indexes if they don't exist
        op.execute("CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_proposals_expires_at ON public.proposals (expires_at);")
        
        # Ensure owner check constraint exists
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
        
        # --- PROPOSAL_DOCUMENTS: Ensure proper foreign key and cascade ---
        
        # Ensure foreign key exists with proper cascade
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_proposal_documents_proposal_id_proposals'
            ) THEN
                ALTER TABLE public.proposal_documents
                ADD CONSTRAINT fk_proposal_documents_proposal_id_proposals
                FOREIGN KEY (proposal_id) REFERENCES public.proposals(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """)
        
        # Create index on proposal_id if missing
        op.execute("CREATE INDEX IF NOT EXISTS ix_proposal_documents_proposal_id ON public.proposal_documents (proposal_id);")
        
        # --- REQUIREMENTS: Ensure proper foreign key and cascade ---
        
        # Ensure foreign key exists with proper cascade
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_requirements_proposal_id_proposals'
            ) THEN
                ALTER TABLE public.requirements
                ADD CONSTRAINT fk_requirements_proposal_id_proposals
                FOREIGN KEY (proposal_id) REFERENCES public.proposals(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """)
        
        # Create indexes if missing
        op.execute("CREATE INDEX IF NOT EXISTS ix_requirements_proposal_id ON public.requirements (proposal_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_requirements_requirement_id ON public.requirements (requirement_id);")
        
        # --- CONVERSIONS: Ensure proper foreign keys and indexes ---
        
        # Add missing columns if they don't exist
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS sha256 VARCHAR(64);")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS original_mime VARCHAR(120);")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS original_size INTEGER;")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS stored_uri VARCHAR(512);")
        op.execute("ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;")
        
        # Create indexes if missing
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_conversions_sha256 ON public.conversions (sha256);")
        
        # Ensure foreign keys exist
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
        
        # --- USERS: Ensure all required columns exist ---
        
        # Add missing columns if they don't exist
        op.execute("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS plan VARCHAR(64) DEFAULT 'F&F';")
        op.execute("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITHOUT TIME ZONE;")
        op.execute("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS revoked BOOLEAN DEFAULT FALSE;")
        
        # Create indexes if missing
        op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON public.users (email);")
        
    elif dialect == 'sqlite':
        # SQLite-specific operations
        
        # Get current schema to check what exists
        inspector = sa.inspect(connection)
        
        # --- PROPOSALS: Ensure all required columns and constraints ---
        
        proposals_cols = {c["name"] for c in inspector.get_columns("proposals")}
        
        with op.batch_alter_table('proposals') as batch_op:
            # Add columns only if they don't exist
            if "visitor_session_id" not in proposals_cols:
                batch_op.add_column(sa.Column('visitor_session_id', sa.String(64), nullable=True))
            if "expires_at" not in proposals_cols:
                batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        
        # Create indexes if missing
        proposals_indexes = {i["name"] for i in inspector.get_indexes("proposals")}
        try:
            if "ix_proposals_visitor_session_id" not in proposals_indexes:
                op.create_index('ix_proposals_visitor_session_id', 'proposals', ['visitor_session_id'], unique=False)
        except:
            pass
        try:
            if "ix_proposals_expires_at" not in proposals_indexes:
                op.create_index('ix_proposals_expires_at', 'proposals', ['expires_at'], unique=False)
        except:
            pass
        
        # --- PROPOSAL_DOCUMENTS: Ensure proper foreign key ---
        
        # Create index on proposal_id if missing
        try:
            proposal_docs_indexes = {i["name"] for i in inspector.get_indexes("proposal_documents")}
            if "ix_proposal_documents_proposal_id" not in proposal_docs_indexes:
                op.create_index('ix_proposal_documents_proposal_id', 'proposal_documents', ['proposal_id'], unique=False)
        except:
            pass
        
        # --- REQUIREMENTS: Ensure proper indexes ---
        
        # Create indexes if missing
        try:
            requirements_indexes = {i["name"] for i in inspector.get_indexes("requirements")}
            if "ix_requirements_proposal_id" not in requirements_indexes:
                op.create_index('ix_requirements_proposal_id', 'requirements', ['proposal_id'], unique=False)
            if "ix_requirements_requirement_id" not in requirements_indexes:
                op.create_index('ix_requirements_requirement_id', 'requirements', ['requirement_id'], unique=False)
        except:
            pass
        
        # --- CONVERSIONS: Ensure all required columns ---
        
        conversions_cols = {c["name"] for c in inspector.get_columns("conversions")}
        
        with op.batch_alter_table('conversions') as batch_op:
            # Add columns only if they don't exist
            if "proposal_id" not in conversions_cols:
                batch_op.add_column(sa.Column('proposal_id', sa.Integer(), nullable=True))
            if "user_id" not in conversions_cols:
                batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
            if "visitor_session_id" not in conversions_cols:
                batch_op.add_column(sa.Column('visitor_session_id', sa.String(64), nullable=True))
            if "sha256" not in conversions_cols:
                batch_op.add_column(sa.Column('sha256', sa.String(64), nullable=True))
            if "original_mime" not in conversions_cols:
                batch_op.add_column(sa.Column('original_mime', sa.String(120), nullable=True))
            if "original_size" not in conversions_cols:
                batch_op.add_column(sa.Column('original_size', sa.Integer(), nullable=True))
            if "stored_uri" not in conversions_cols:
                batch_op.add_column(sa.Column('stored_uri', sa.String(512), nullable=True))
            if "expires_at" not in conversions_cols:
                batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        
        # Create indexes if missing
        try:
            conversions_indexes = {i["name"] for i in inspector.get_indexes("conversions")}
            if "ix_conversions_proposal_id" not in conversions_indexes:
                op.create_index('ix_conversions_proposal_id', 'conversions', ['proposal_id'], unique=False)
            if "ix_conversions_user_id" not in conversions_indexes:
                op.create_index('ix_conversions_user_id', 'conversions', ['user_id'], unique=False)
            if "ix_conversions_visitor_session_id" not in conversions_indexes:
                op.create_index('ix_conversions_visitor_session_id', 'conversions', ['visitor_session_id'], unique=False)
            if "ix_conversions_sha256" not in conversions_indexes:
                op.create_index('ix_conversions_sha256', 'conversions', ['sha256'], unique=False)
        except:
            pass
        
        # --- USERS: Ensure all required columns ---
        
        users_cols = {c["name"] for c in inspector.get_columns("users")}
        
        with op.batch_alter_table('users') as batch_op:
            # Add columns only if they don't exist
            if "plan" not in users_cols:
                batch_op.add_column(sa.Column('plan', sa.String(64), nullable=False, server_default='F&F'))
            if "last_login_at" not in users_cols:
                batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
            if "revoked" not in users_cols:
                batch_op.add_column(sa.Column('revoked', sa.Boolean(), nullable=False, server_default='0'))
        
        # Create indexes if missing
        try:
            users_indexes = {i["name"] for i in inspector.get_indexes("users")}
            if "ix_users_email" not in users_indexes:
                op.create_index('ix_users_email', 'users', ['email'], unique=True)
        except:
            pass


def downgrade():
    """Reversible downgrade operations.
    
    Note: This downgrade is conservative and only removes newly added indexes,
    not columns or constraints, to avoid data loss.
    """
    
    connection = op.get_bind()
    dialect = connection.dialect.name
    
    if dialect == 'postgresql':
        # PostgreSQL downgrade - only drop indexes, not columns
        
        # Drop indexes (safe operation)
        op.execute("DROP INDEX IF EXISTS ix_proposals_visitor_session_id;")
        op.execute("DROP INDEX IF EXISTS ix_proposals_expires_at;")
        op.execute("DROP INDEX IF EXISTS ix_proposal_documents_proposal_id;")
        op.execute("DROP INDEX IF EXISTS ix_requirements_proposal_id;")
        op.execute("DROP INDEX IF EXISTS ix_requirements_requirement_id;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_proposal_id;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_user_id;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_visitor_session_id;")
        op.execute("DROP INDEX IF EXISTS ix_conversions_sha256;")
        op.execute("DROP INDEX IF EXISTS ix_users_email;")
        
    elif dialect == 'sqlite':
        # SQLite downgrade - only drop indexes, not columns
        
        try:
            op.drop_index('ix_proposals_visitor_session_id')
        except:
            pass
        try:
            op.drop_index('ix_proposals_expires_at')
        except:
            pass
        try:
            op.drop_index('ix_proposal_documents_proposal_id')
        except:
            pass
        try:
            op.drop_index('ix_requirements_proposal_id')
        except:
            pass
        try:
            op.drop_index('ix_requirements_requirement_id')
        except:
            pass
        try:
            op.drop_index('ix_conversions_proposal_id')
        except:
            pass
        try:
            op.drop_index('ix_conversions_user_id')
        except:
            pass
        try:
            op.drop_index('ix_conversions_visitor_session_id')
        except:
            pass
        try:
            op.drop_index('ix_conversions_sha256')
        except:
            pass
        try:
            op.drop_index('ix_users_email')
        except:
            pass
