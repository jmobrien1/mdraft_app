#!/usr/bin/env python3
"""
Schema Guard - Ensures database schema matches application expectations.

This script runs idempotent SQL to guarantee the database has all required
columns, indexes, and constraints, even if migrations failed or are out of sync.

Safe to run on every boot - all operations use IF NOT EXISTS or similar guards.
"""

import os
import sys
from sqlalchemy import create_engine, text


def run():
    """Execute schema guard operations."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[schema_guard] DATABASE_URL not set; skipping.")
        return 0

    print("[schema_guard] Ensuring database schema...")
    
    engine = create_engine(db_url, future=True)
    
    # All statements are idempotent - safe to run multiple times
    stmts = [
        # --- PROPOSALS: columns ---
        "ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);",
        "ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;",
        
        # --- PROPOSALS: indexes ---
        "CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);",
        "CREATE INDEX IF NOT EXISTS ix_proposals_expires_at ON public.proposals (expires_at);",
        
        # --- PROPOSALS: owner check constraint (at least one owner) ---
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_proposals_owner_present') THEN
                ALTER TABLE public.proposals
                ADD CONSTRAINT ck_proposals_owner_present
                CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
            END IF;
        END $$;
        """,
        
        # --- CONVERSIONS: columns ---
        "ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;",
        "ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);",
        "ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;",
        
        # --- CONVERSIONS: indexes ---
        "CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);",
        "CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);",
        "CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);",
        
        # --- CONVERSIONS: optional FK to users (safe no-op if already present) ---
        """
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
        """,
        
        # --- CONVERSIONS: optional FK to proposals (safe no-op if already present) ---
        """
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
        """,
        
        # --- BACKFILL owners on conversions from proposals (proposal_id) ---
        """
        UPDATE public.conversions c
        SET user_id = p.user_id
        FROM public.proposals p
        WHERE c.proposal_id = p.id
          AND c.user_id IS NULL
          AND p.user_id IS NOT NULL;
        """,
        
        """
        UPDATE public.conversions c
        SET visitor_session_id = p.visitor_session_id
        FROM public.proposals p
        WHERE c.proposal_id = p.id
          AND c.visitor_session_id IS NULL
          AND p.visitor_session_id IS NOT NULL;
        """,
    ]

    try:
        with engine.begin() as conn:
            for i, stmt in enumerate(stmts, 1):
                print(f"[schema_guard] Executing statement {i}/{len(stmts)}...")
                conn.execute(text(stmt))
        
        print("[schema_guard] ✅ Schema guard completed successfully.")
        return 0
        
    except Exception as e:
        print(f"[schema_guard] ❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run())
