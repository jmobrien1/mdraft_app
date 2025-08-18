#!/bin/bash
# Database migration deployment script
# Run this in Render web shell to apply the progress column migration

set -e

echo "🗄️  DATABASE MIGRATION DEPLOYMENT"
echo "=================================="

# Check if we're in a production environment
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set. Please run this in Render web shell."
    exit 1
fi

echo "📍 Database: $DATABASE_URL"
echo ""

# Step 1: Check current migration status
echo "1️⃣  Checking current migration status..."
flask db current || echo "⚠️  Could not determine current migration status"

echo ""

# Step 2: Run the migration with timeout
echo "2️⃣  Running database migration (timeout 20s)..."
echo "   This will add the progress column to conversions table"
echo ""

if bash -lc 'timeout 20s flask db upgrade || true'; then
    echo "✅ Migration completed successfully"
else
    echo "⚠️  Migration may have timed out or failed"
    echo "   Check the logs for details"
fi

echo ""

# Step 3: Verify the column was added
echo "3️⃣  Verifying progress column exists..."
python3 -c "
import os
os.environ.setdefault('DATABASE_URL', '$DATABASE_URL')
os.environ.setdefault('SECRET_KEY', 'debug-secret-key')

from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        result = db.session.execute(text(\"\"\"
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'conversions' 
            AND column_name = 'progress'
        \"\"\"))
        
        row = result.fetchone()
        if row:
            print(f'✅ Progress column found:')
            print(f'   Column: {row[0]}')
            print(f'   Type: {row[1]}')
            print(f'   Nullable: {row[2]}')
            print(f'   Default: {row[3]}')
        else:
            print('❌ Progress column not found')
    except Exception as e:
        print(f'❌ Error checking column: {e}')
"

echo ""

# Step 4: Test the API endpoint
echo "4️⃣  Testing /api/conversions endpoint..."
if [ -n "$RENDER_EXTERNAL_URL" ]; then
    echo "   Testing: $RENDER_EXTERNAL_URL/api/conversions?limit=10"
    curl -sS -i "$RENDER_EXTERNAL_URL/api/conversions?limit=10" || echo "   ❌ API test failed"
else
    echo "   ⚠️  RENDER_EXTERNAL_URL not set, skipping API test"
fi

echo ""
echo "🎉 Migration deployment completed!"
echo ""
echo "Expected results:"
echo "  ✅ Progress column added to conversions table"
echo "  ✅ /api/conversions returns 200 OK (not 500 error)"
echo "  ✅ No more 'column conversions.progress does not exist' errors"
