#!/bin/bash
# Fix migration state on Render

set -e

echo "🔧 Fixing migration state on Render..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable not set"
    exit 1
fi

echo "📊 Database URL: ${DATABASE_URL}"

# Run the fix with Flask app context
python3 -c "
import os
from app import create_app
from flask_migrate import stamp

app = create_app()
with app.app_context():
    print('Checking current migration state...')
    
    # Stamp the database to mark the problematic migration as completed
    # This tells Alembic that the migration has been applied without actually running it
    print('Stamping migration dfd980eee75b as completed...')
    stamp(revision='dfd980eee75b')
    
    print('✅ Migration state fixed successfully')
"

echo "✅ Migration state fix completed"
echo ""
echo "📋 Next steps:"
echo "1. Run: flask --app app:create_app db upgrade"
echo "2. This should now complete successfully"
