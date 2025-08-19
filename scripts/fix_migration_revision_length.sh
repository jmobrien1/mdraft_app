#!/bin/bash
# Fix migration revision length issue on Render
set -e

echo "🔧 Fixing migration revision length issue on Render..."
echo "This will stamp the problematic migration and run the fixed one."

# First, stamp the problematic migration as completed
echo "Step 1: Stamping problematic migration as completed..."
python3 -c "
import os
from app import create_app
from flask_migrate import stamp

app = create_app()
with app.app_context():
    print('Stamping migration 20250818_add_progress_to_conversions as completed...')
    stamp(revision='20250818_add_progress_to_conversions')
    print('✅ Problematic migration stamped successfully')
"

# Then run the visitor session migration
echo "Step 2: Running visitor session migration..."
python3 -c "
import os
from app import create_app
from flask_migrate import upgrade

app = create_app()
with app.app_context():
    print('Running visitor session migration...')
    upgrade()
    print('✅ Migration completed successfully')
"

echo "✅ Migration revision length fix completed"
echo ""
echo "Next steps:"
echo "1. Test file upload functionality"
echo "2. Test compliance matrix document upload"
echo "3. Verify all endpoints are working"
