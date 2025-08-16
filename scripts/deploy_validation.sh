#!/usr/bin/env bash
# scripts/deploy_validation.sh
set -Eeuo pipefail

echo "=== DEPLOYMENT VALIDATION: starting ==="

# Check environment variables
echo "Environment check:"
echo "PYTHONPATH=${PYTHONPATH:-NOT_SET}"
echo "FLASK_APP=${FLASK_APP:-NOT_SET}"
echo "DATABASE_URL=${DATABASE_URL:-NOT_SET}"
echo "GCS_BUCKET_NAME=${GCS_BUCKET_NAME:-NOT_SET}"
echo "GCS_PROCESSED_BUCKET_NAME=${GCS_PROCESSED_BUCKET_NAME:-NOT_SET}"
echo "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT:-NOT_SET}"

# Check Python path
echo "Python path check:"
python -c "import sys; print('Python executable:', sys.executable)"
python -c "import sys; print('Python path:', sys.path[0])"

# Check if app can be imported
echo "App import check:"
python -c "import app; print('App imported successfully from:', app.__file__)"

# Check Flask app
echo "Flask app check:"
python -c "from app import create_app; app = create_app(); print('Flask app created successfully')"

# Check database connectivity (if DATABASE_URL is set)
if [[ -n "${DATABASE_URL:-}" ]]; then
    echo "Database connectivity check:"
    python -c "
import os
from sqlalchemy import create_engine, text
url = os.environ['DATABASE_URL']
if url.startswith('postgres://'):
    url = url.replace('postgres://', 'postgresql+psycopg://', 1)
elif url.startswith('postgresql://') and '+psycopg' not in url:
    url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(url, future=True)
with engine.connect() as c:
    result = c.execute(text('SELECT 1'))
    print('Database connection successful')
"
else
    echo "Database connectivity check: SKIPPED (no DATABASE_URL)"
fi

echo "=== DEPLOYMENT VALIDATION: completed ==="
