#!/usr/bin/env bash
# scripts/predeploy.sh
# Improved pre-deployment script for Render

set -Eeuo pipefail

echo "=== PREDEPLOY: starting ==="

# Load secrets from Render secrets file
if [[ -f /etc/secrets/mdraft-web ]]; then
    echo "Loading secrets from /etc/secrets/mdraft-web"
    export $(cat /etc/secrets/mdraft-web | xargs)
else
    echo "WARNING: /etc/secrets/mdraft-web not found"
fi

# Set required environment variables for pre-deployment
export PYTHONPATH="${PYTHONPATH:-/opt/render/project/src}"
export FLASK_APP="${FLASK_APP:-wsgi.py}"
export FLASK_ENV="${FLASK_ENV:-production}"

# Set session configuration for pre-deployment script
# This ensures Flask-Session doesn't fail during database migrations
export SESSION_BACKEND="${SESSION_BACKEND:-filesystem}"
export SESSION_TYPE="${SESSION_TYPE:-filesystem}"

# Log configuration for debugging
echo "PYTHONPATH=$PYTHONPATH"
echo "FLASK_APP=$FLASK_APP"
echo "FLASK_ENV=$FLASK_ENV"
echo "SESSION_BACKEND=$SESSION_BACKEND"
echo "SESSION_TYPE=$SESSION_TYPE"

# Check if DATABASE_URL is set
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is not set"
    exit 1
fi

# Run the migration sentry script
echo "=== PREDEPLOY: running migration sentry ==="
bash scripts/migration_sentry.sh

echo "=== PREDEPLOY: completed successfully ==="
