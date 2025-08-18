#!/bin/bash
# Manual migration script for Render deployment

set -e

echo "🔄 Running database migrations manually..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable not set"
    exit 1
fi

echo "📊 Database URL: ${DATABASE_URL}"

# Run migrations with Flask app context
python3 -c "
import os
from app import create_app
from flask_migrate import upgrade

# Create app and run migrations
app = create_app()
with app.app_context():
    print('Running database migrations...')
    upgrade()
    print('✅ Migrations completed successfully')
"

echo "✅ Manual migration script completed"
