#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== Starting mdraft application ==="
echo "PORT=$PORT"
echo "PYTHONPATH=$PYTHONPATH"
echo "FLASK_APP=$FLASK_APP"

# Ensure we're in the right directory
cd /opt/render/project/src

# Start Gunicorn as PID 1 (no backgrounding, no wrapper processes)
exec gunicorn \
  --bind 0.0.0.0:$PORT \
  --workers 2 \
  --threads 8 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  wsgi:app
