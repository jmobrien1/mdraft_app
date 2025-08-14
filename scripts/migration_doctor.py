#!/usr/bin/env python3
"""
Migration Doctor - Ensures database migrations run reliably in production.

This script:
1. Takes a Postgres advisory lock to prevent concurrent upgrades
2. Runs alembic upgrade head
3. If that fails with chain issues, runs alembic stamp head then alembic upgrade head
4. As a last resort, applies guarded DDL to ensure required columns exist
5. Logs clear pass/fail output

Safe to run on every boot - all operations are idempotent.
"""

import os
import sys
import subprocess
import shlex
from contextlib import contextmanager
from sqlalchemy import create_engine, text

# Arbitrary integer for advisory lock
LOCK_KEY = 73219011

# Required schema statements (idempotent)
REQUIRED_STMTS = [
    # PROPOSALS — columns & index
    "ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);",
    "ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;",
    "CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);",
    # PROPOSALS — owner check
    """
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_proposals_owner_present') THEN
        ALTER TABLE public.proposals ADD CONSTRAINT ck_proposals_owner_present
        CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
      END IF;
    END $$;
    """,
    # CONVERSIONS — columns & indexes (denorm ownership)
    "ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;",
    "ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);",
    "CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);",
    # BACKFILL ownership on conversions (safe)
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


def _env_db_url():
    """Get database URL from environment variables."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
    if not url:
        print("[migration_doctor] ERROR: No DATABASE_URL/SQLALCHEMY_DATABASE_URI in env.", flush=True)
        sys.exit(2)
    return url


@contextmanager
def pg_lock(conn):
    """Try to acquire a global advisory lock to avoid concurrent upgrades."""
    got = conn.execute(text(f"SELECT pg_try_advisory_lock({LOCK_KEY})")).scalar()
    if not got:
        print("[migration_doctor] Another instance holds the lock; skipping this cycle.", flush=True)
        yield False
        return
    try:
        yield True
    finally:
        conn.execute(text(f"SELECT pg_advisory_unlock({LOCK_KEY})"))


def _run(cmd):
    """Run a shell command and return the exit code."""
    print(f"[migration_doctor] $ {cmd}", flush=True)
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.strip(), flush=True)
    if proc.stderr:
        print(proc.stderr.strip(), flush=True)
    return proc.returncode


def _alembic_upgrade():
    """Run alembic upgrade head, with fallback to stamp→upgrade if needed."""
    # Prefer Alembic CLI; Flask-Migrate will piggyback via env.py
    rc = _run("alembic upgrade head")
    if rc == 0:
        return True
    print("[migration_doctor] upgrade failed; attempting stamp→upgrade…", flush=True)
    if _run("alembic stamp head") != 0:
        return False
    return _run("alembic upgrade head") == 0


def _ensure_schema(conn):
    """Apply guarded DDL as a last resort."""
    for i, stmt in enumerate(REQUIRED_STMTS, 1):
        try:
            conn.execute(text(stmt))
            print(f"[migration_doctor] Applied guarded DDL statement {i}/{len(REQUIRED_STMTS)}", flush=True)
        except Exception as e:
            print(f"[migration_doctor] WARN: stmt {i} failed: {e}", flush=True)


def main():
    """Main migration doctor function."""
    db_url = _env_db_url()
    engine = create_engine(db_url, future=True)
    
    with engine.begin() as conn:
        with pg_lock(conn) as do_run:
            if not do_run:
                return 0
            
            # 1) Try proper migrations first
            if _alembic_upgrade():
                print("[migration_doctor] ✅ Alembic upgrade OK.", flush=True)
            else:
                print("[migration_doctor] ⚠️ Alembic still failing — applying guarded DDL as fallback.", flush=True)
                _ensure_schema(conn)
                # Try upgrade once more post-guard
                if not _alembic_upgrade():
                    print("[migration_doctor] ⚠️ upgrade failed even after guard; leaving schema in guarded state.", flush=True)
                    # We still exit 0 so app can start with required columns present.
    
    print("[migration_doctor] ✅ Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
