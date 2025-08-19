#!/bin/bash
# Fix migration state on Render

set -e

echo "🔧 Fixing migration state on Render..."
echo "This will stamp the problematic migration as completed to allow subsequent migrations to run."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable not set"
    exit 1
fi

echo "📊 Database URL: ${DATABASE_URL}"

# Run the migration state fix within Flask app context
python3 -c "
import os
from app import create_app
from flask_migrate import stamp

app = create_app()
with app.app_context():
    print('Stamping migration dfd980eee75b as completed...')
    stamp(revision='dfd980eee75b')
    print('✅ Migration state fixed successfully')
"

echo "✅ Migration state fix completed"
echo ""
echo "Next steps:"
echo "1. Run: ./scripts/run_visitor_session_migration.sh"
echo "2. This should now complete successfully"
echo "3. Test file upload functionality"
echo "4. Test compliance matrix document upload"
