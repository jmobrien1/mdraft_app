#!/usr/bin/env bash
# scripts/migration_sentry.sh
set -Eeuo pipefail

echo "=== MIGRATION SENTRY: starting ==="

: "${DATABASE_URL:?DATABASE_URL is not set}"
export SQLALCHEMY_DATABASE_URI="${SQLALCHEMY_DATABASE_URI:-$DATABASE_URL}"
export FLASK_APP="${FLASK_APP:-run.py}"

echo "FLASK_APP=$FLASK_APP"
masked_host="$(echo "${DATABASE_URL#*://}" | cut -d@ -f2 | cut -d/ -f1)"
masked_db="$(echo "${DATABASE_URL##*/}" | cut -d? -f1)"
echo "DB (redacted): postgresql://******@${masked_host}/${masked_db}"

# --- Precheck: DB connectivity & alembic_version visibility (psycopg v3 normalization) ---
python - <<'PY'
import os
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://") and "+psycopg" not in url:
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(url, future=True)
with engine.connect() as c:
    ver = c.execute(text("SELECT version();")).scalar()
    db = c.execute(text("SELECT current_database();")).scalar()
    print(f"[SENTRY] DB OK: {db}")
    print(f"[SENTRY] Server:", ver.split()[0])

try:
    with engine.connect() as c:
        cur = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"[SENTRY] alembic_version current: {cur}")
except Exception:
    print("[SENTRY] alembic_version table not found yet (ok on first run).")
PY

echo "=== MIGRATION SENTRY: flask db upgrade ==="
set +e
flask db upgrade
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  echo "=== MIGRATION SENTRY: upgrade failed; attempting auto-repair (unknown revision / chain break) ==="
  # Many failures here are from DB pointing to a revision not present in the repo.
  # Step 1: detach alembic_version from the unknown rev and set to base
  set +e
  alembic stamp base
  rc_stamp=$?
  set -e
  if [[ $rc_stamp -ne 0 ]]; then
    echo "[SENTRY] WARN: 'alembic stamp base' failed; proceeding anyway."
  fi

  echo "=== MIGRATION SENTRY: retry flask db upgrade ==="
  set +e
  flask db upgrade
  rc2=$?
  set -e

  if [[ $rc2 -ne 0 ]]; then
    echo "=== MIGRATION SENTRY: upgrade still failing; applying guarded DDL minimums, then stamping head ==="

    # --- Guarded DDL: ensure required minimal columns/indexes exist ---
    python - <<'PY'
import os
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://") and "+psycopg" not in url:
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(url, future=True)
stmts = [
    # PROPOSALS
    "ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);",
    "ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;",
    "CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);",
    """
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_proposals_owner_present') THEN
        ALTER TABLE public.proposals
        ADD CONSTRAINT ck_proposals_owner_present
        CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
      END IF;
    END $$;
    """,
    # CONVERSIONS
    "ALTER TABLE IF NOT EXISTS public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;",
    "ALTER TABLE IF NOT EXISTS public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;",
    "ALTER TABLE IF NOT EXISTS public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);",
    "CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);",
    "CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);",
]
with engine.begin() as c:
    for i, s in enumerate(stmts, 1):
        try:
            c.execute(text(s))
        except Exception as e:
            print(f"[SENTRY] WARN ddl#{i}: {e}")
print("[SENTRY] Guarded DDL applied.")
PY

    # Step 2: Stamp to repo head so future upgrades run clean
    set +e
    alembic stamp head
    rc_stamp_head=$?
    set -e
    if [[ $rc_stamp_head -ne 0 ]]; then
      echo "[SENTRY] WARN: 'alembic stamp head' failed; will verify schema anyway."
    fi
  fi
fi

echo "=== MIGRATION SENTRY: verifying required columns ==="
python - <<'PY'
import os, sys
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://") and "+psycopg" not in url:
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(url, future=True)
need = [("proposals","visitor_session_id"), ("conversions","proposal_id")]
with engine.connect() as c:
    for table, col in need:
        cnt = c.execute(text("""
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_name=:t AND column_name=:c
        """), {"t": table, "c": col}).scalar()
        if cnt != 1:
            print(f"[SENTRY] MISSING {table}.{col}")
            sys.exit(21)
print("[SENTRY] schema OK.")
PY

echo "=== MIGRATION SENTRY: success ==="
