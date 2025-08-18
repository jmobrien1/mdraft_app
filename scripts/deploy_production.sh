#!/bin/bash
# Comprehensive production deployment script for mdraft

set -e  # Exit on any error

echo "🚀 Starting mdraft production deployment..."

# Check if we're in the right directory
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: alembic.ini not found. Please run this script from the project root."
    exit 1
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable not set"
    exit 1
fi

echo "📊 Database URL: ${DATABASE_URL}"

# Step 1: Check migration state
echo "🔍 Step 1: Checking migration state..."
python3 -c "
import os
from app import create_app
from flask_migrate import current

app = create_app()
with app.app_context():
    try:
        current()
        print('✅ Migration state check completed')
    except Exception as e:
        print(f'⚠️  Migration state issue: {e}')
"

# Step 2: Merge any divergent heads
echo "🔀 Step 2: Checking for divergent migration heads..."
python3 -c "
import os
import subprocess
from app import create_app

app = create_app()
with app.app_context():
    try:
        # Check for multiple heads
        result = subprocess.run(['alembic', 'heads'], capture_output=True, text=True)
        if 'head' in result.stdout and result.stdout.count('head') > 1:
            print('⚠️  Multiple heads detected, attempting merge...')
            # Get the head revisions
            lines = result.stdout.strip().split('\n')
            heads = []
            for line in lines:
                if '(head)' in line:
                    revision = line.split()[0]
                    heads.append(revision)
            
            if len(heads) >= 2:
                merge_cmd = ['alembic', 'merge', '-m', 'merge heads'] + heads
                subprocess.run(merge_cmd, check=True)
                print('✅ Migration heads merged successfully')
        else:
            print('✅ Single migration head detected')
    except Exception as e:
        print(f'⚠️  Head check issue: {e}')
"

# Step 3: Run database migrations
echo "🔄 Step 3: Running database migrations..."
python3 -c "
import os
from app import create_app
from flask_migrate import upgrade

app = create_app()
with app.app_context():
    print('Running database migrations...')
    upgrade()
    print('✅ Migrations completed successfully')
"

# Step 4: Verify database schema
echo "🔍 Step 4: Verifying database schema..."
python3 -c "
import os
from sqlalchemy import create_engine, inspect
from app import create_app

app = create_app()
with app.app_context():
    engine = create_engine(os.getenv('DATABASE_URL'))
    inspector = inspect(engine)
    
    # Check if jobs table has visitor_session_id column
    if 'jobs' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('jobs')]
        if 'visitor_session_id' in columns:
            print('✅ visitor_session_id column exists in jobs table')
        else:
            print('❌ visitor_session_id column missing from jobs table')
            exit(1)
    else:
        print('⚠️  jobs table not found - this may be expected in some environments')
    
    # Check if conversions table exists
    if 'conversions' in inspector.get_table_names():
        print('✅ conversions table exists')
    else:
        print('⚠️  conversions table not found')
    
    # Check if users table exists
    if 'users' in inspector.get_table_names():
        print('✅ users table exists')
    else:
        print('⚠️  users table not found')
    
    print('✅ Database schema verification completed')
"

# Step 5: Test Celery configuration
echo "🧪 Step 5: Testing Celery configuration..."
python3 -c "
import os
from celery_worker import celery, celery_app

# Verify celery exports
assert celery is celery_app, 'celery and celery_app should be the same object'
assert hasattr(celery, 'conf'), 'celery should have conf attribute'
assert hasattr(celery, 'send_task'), 'celery should have send_task method'

print('✅ Celery configuration verified')
"

# Step 6: Test blueprint imports
echo "🧪 Step 6: Testing blueprint imports..."
python3 -c "
try:
    from app.api_convert import bp as convert_bp
    from app.api_estimate import bp as estimate_bp
    from app.api_queue import bp as queue_bp
    from app.api.agents import bp as agents_bp
    print('✅ All blueprint imports successful')
except Exception as e:
    print(f'❌ Blueprint import failed: {e}')
    exit(1)
"

echo "🎉 Production deployment preparation completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Deploy to Render with updated render.yaml"
echo "2. Monitor deployment logs for any issues"
echo "3. Verify all endpoints are working correctly"
echo ""
echo "🔧 If you need to run migrations manually on Render:"
echo "   flask --app app:create_app db upgrade"
