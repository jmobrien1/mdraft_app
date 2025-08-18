#!/bin/bash
# Deployment script with migration handling

set -e  # Exit on any error

echo "🚀 Starting mdraft deployment with migrations..."

# Check if we're in the right directory
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: alembic.ini not found. Please run this script from the project root."
    exit 1
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  Warning: DATABASE_URL not set. Using default SQLite database."
    export DATABASE_URL="sqlite:///instance/mdraft.db"
fi

echo "📊 Database URL: ${DATABASE_URL}"

# Run database migrations
echo "🔄 Running database migrations..."
if command -v alembic &> /dev/null; then
    # Check current migration status
    echo "📋 Current migration status:"
    alembic current || echo "No migrations applied yet"
    
    # Run migrations
    echo "⬆️  Applying migrations..."
    alembic upgrade head
    
    echo "✅ Migrations completed successfully"
else
    echo "❌ Error: alembic not found. Please install it with: pip install alembic"
    exit 1
fi

# Check if migrations were successful
echo "🔍 Verifying database schema..."
python3 -c "
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError

try:
    engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///instance/mdraft.db'))
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
        print('❌ jobs table not found')
        exit(1)
        
    print('✅ Database schema verification passed')
except Exception as e:
    print(f'❌ Database verification failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Database schema verification failed"
    exit 1
fi

# Start the application
echo "🚀 Starting mdraft application..."
if [ -n "$PORT" ]; then
    echo "🌐 Using port: $PORT"
    export FLASK_APP=run.py
    python3 -m flask run --host=0.0.0.0 --port=$PORT
else
    echo "🌐 Using default port: 5000"
    export FLASK_APP=run.py
    python3 -m flask run --host=0.0.0.0 --port=5000
fi
