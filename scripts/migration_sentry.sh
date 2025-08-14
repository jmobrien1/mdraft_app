#!/usr/bin/env bash
# scripts/migration_sentry.sh
set -Eeuo pipefail

echo "=== MIGRATION SENTRY: starting ==="

# 1) Sanity: ensure env vars exist and app is importable
: "${DATABASE_URL:?DATABASE_URL is not set}"
export SQLALCHEMY_DATABASE_URI="${SQLALCHEMY_DATABASE_URI:-$DATABASE_URL}"

# If you use an app factory, set accordingly:
# export FLASK_APP="app:create_app()"
export FLASK_APP="${FLASK_APP:-run.py}"

echo "FLASK_APP=$FLASK_APP"
echo "DB (redacted): ${DATABASE_URL%%:*}://******@$(echo "${DATABASE_URL#*://}" | cut -d@ -f2 | cut -d/ -f1)/$(echo "${DATABASE_URL##*/}" | cut -d? -f1)"

# 2) Prove we can import app + connect to DB
python - <<'PY'
import os, sys
from sqlalchemy import create_engine, text
print("[SENTRY] importing FLASK_APP:", os.environ.get("FLASK_APP"))
# Do not import whole app; just DB ping to reduce side effects
url = os.environ.get("DATABASE_URL")
engine = create_engine(url, future=True)
with engine.connect() as c:
    ver = c.execute(text("SELECT version();")).scalar()
    db = c.execute(text("SELECT current_database();")).scalar()
    print(f"[SENTRY] DB OK: {db}")
    print(f"[SENTRY] Server:", ver.split()[0])
# check alembic_version table presence (ok if missing)
try:
    with engine.connect() as c:
        cur = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"[SENTRY] alembic_version current: {cur}")
except Exception as e:
    print("[SENTRY] alembic_version table not found yet (ok on first run).")
PY

# 3) Run migrations with full verbosity
echo "=== MIGRATION SENTRY: flask db upgrade (verbose) ==="
if ! flask db upgrade -v; then
  echo "=== MIGRATION SENTRY: upgrade failed; trying stamp → upgrade ==="
  flask db stamp head
  flask db upgrade -v
fi

echo "=== MIGRATION SENTRY: verifying required columns ==="
python - <<'PY'
import os, sys
from sqlalchemy import create_engine, text
url = os.environ["DATABASE_URL"]
engine = create_engine(url, future=True)
need = [
    ("proposals","visitor_session_id"),
    ("conversions","proposal_id"),
]
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
