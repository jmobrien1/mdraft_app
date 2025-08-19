#!/bin/bash
# Run visitor_session_id migration on Render
set -e

echo "🔧 Running visitor_session_id migration on Render..."
echo "This will add the missing visitor_session_id column to the jobs table."

# Run the migration within Flask app context
python3 -c "
import os
from app import create_app
from flask_migrate import upgrade

app = create_app()
with app.app_context():
    print('Running migration to add visitor_session_id column...')
    upgrade()
    print('✅ Migration completed successfully')
"

echo "✅ Migration script completed"
echo ""
echo "Next steps:"
echo "1. Test file upload functionality"
echo "2. Test compliance matrix document upload"
echo "3. Verify all endpoints are working"
