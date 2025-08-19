#!/bin/bash
# Simple migration fix for Render
set -e

echo "🔧 Simple migration fix for Render..."
echo "This will stamp the merge migration and verify the database schema."

# Step 1: Stamp the merge migration directly
echo "Step 1: Stamping merge migration as completed..."
python3 -c "
import os
from app import create_app
from flask_migrate import stamp

app = create_app()
with app.app_context():
    print('Stamping merge_all_heads_final as completed...')
    stamp(revision='merge_all_heads_final')
    print('✅ Merge migration stamped successfully')
"

# Step 2: Verify database schema
echo "Step 2: Verifying database schema..."
python3 -c "
import os
from app import create_app
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    engine = app.extensions['sqlalchemy'].db.engine
    inspector = inspect(engine)
    
    # Check jobs table
    print('Checking jobs table...')
    jobs_columns = [col['name'] for col in inspector.get_columns('jobs')]
    print(f'Jobs columns: {jobs_columns}')
    
    if 'visitor_session_id' in jobs_columns:
        print('✅ visitor_session_id column exists in jobs table')
    else:
        print('❌ visitor_session_id column missing from jobs table')
        print('Adding visitor_session_id column manually...')
        
        # Add the column manually if missing
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_jobs_visitor_session_id ON jobs (visitor_session_id)'))
            print('✅ visitor_session_id column added manually')
    
    # Check conversions table
    print('\\nChecking conversions table...')
    conversions_columns = [col['name'] for col in inspector.get_columns('conversions')]
    print(f'Conversions columns: {conversions_columns}')
    
    if 'progress' in conversions_columns:
        print('✅ progress column exists in conversions table')
    else:
        print('❌ progress column missing from conversions table')
        print('Adding progress column manually...')
        
        # Add the column manually if missing
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE conversions ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0 NOT NULL'))
            print('✅ progress column added manually')
"

echo "✅ Simple migration fix completed"
echo ""
echo "Next steps:"
echo "1. Test file upload functionality"
echo "2. Test compliance matrix document upload"
echo "3. Verify all endpoints are working"
echo "4. Check that Celery worker starts correctly"
