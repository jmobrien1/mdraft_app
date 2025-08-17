#!/bin/bash
"""
Production Debugging Script for Render Deployment

This script helps identify the root cause of 500 errors in production.
Run this on Render to get detailed debugging information.
"""

set -e

echo "🔍 PRODUCTION DEBUGGING SCRIPT"
echo "================================"

# Environment information
echo "=== ENVIRONMENT INFO ==="
echo "Working directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Python path: $PYTHONPATH"
echo "Flask environment: $FLASK_ENV"
echo "Flask debug: $FLASK_DEBUG"

# Check critical environment variables
echo ""
echo "=== ENVIRONMENT VARIABLES ==="
critical_vars=("DATABASE_URL" "SECRET_KEY" "REDIS_URL" "SESSION_REDIS_URL" "FLASK_LIMITER_STORAGE_URI")

for var in "${critical_vars[@]}"; do
    value="${!var}"
    if [ -n "$value" ]; then
        echo "✅ $var: ${value:0:20}... (length: ${#value})"
        # Check for trailing whitespace
        if [ "$value" != "${value% }" ]; then
            echo "   ⚠️  WARNING: $var has trailing whitespace!"
        fi
    else
        echo "❌ $var: NOT SET"
    fi
done

# Test Python imports
echo ""
echo "=== PYTHON IMPORTS ==="
python3 -c "
import sys
modules = ['flask', 'flask_sqlalchemy', 'flask_limiter', 'redis', 'sqlalchemy', 'psycopg']
for module in modules:
    try:
        __import__(module)
        print(f'✅ {module}: Imported successfully')
    except ImportError as e:
        print(f'❌ {module}: Import failed - {e}')
    except Exception as e:
        print(f'⚠️  {module}: Import error - {e}')
"

# Test app creation
echo ""
echo "=== APP CREATION TEST ==="
python3 -c "
import sys
import traceback
try:
    from app import create_app
    print('✅ create_app imported successfully')
    
    app = create_app()
    print('✅ App created successfully')
    
    # Test route registration
    root_routes = [r for r in app.url_map.iter_rules() if r.rule == '/']
    print(f'✅ Root routes found: {len(root_routes)}')
    for route in root_routes:
        print(f'   - {route.endpoint}')
        
except Exception as e:
    print(f'❌ App creation failed: {e}')
    print(f'Error type: {type(e).__name__}')
    print('Traceback:')
    traceback.print_exc()
"

# Test WSGI app loading
echo ""
echo "=== WSGI APP TEST ==="
python3 -c "
import sys
import traceback
try:
    from wsgi import app
    print('✅ WSGI app loaded successfully')
    print(f'App name: {app.name}')
    print(f'App debug: {app.debug}')
    print(f'App testing: {app.testing}')
except Exception as e:
    print(f'❌ WSGI app loading failed: {e}')
    print(f'Error type: {type(e).__name__}')
    print('Traceback:')
    traceback.print_exc()
"

# Test database connection
echo ""
echo "=== DATABASE CONNECTION TEST ==="
python3 -c "
import os
import sys
import traceback
try:
    from sqlalchemy import create_engine, text
    from app.utils.db_url import normalize_db_url
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('❌ DATABASE_URL: NOT SET')
    else:
        normalized_url = normalize_db_url(db_url)
        print('✅ Database URL normalized successfully')
        
        engine = create_engine(normalized_url, pool_pre_ping=True)
        print('✅ Database engine created successfully')
        
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1'))
            print('✅ Database connection test successful')
            
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    print(f'Error type: {type(e).__name__}')
    print('Traceback:')
    traceback.print_exc()
"

# Test Redis connections
echo ""
echo "=== REDIS CONNECTION TEST ==="
python3 -c "
import os
import sys
import traceback
try:
    import redis
    
    redis_urls = [
        ('REDIS_URL', os.getenv('REDIS_URL')),
        ('SESSION_REDIS_URL', os.getenv('SESSION_REDIS_URL')),
        ('FLASK_LIMITER_STORAGE_URI', os.getenv('FLASK_LIMITER_STORAGE_URI'))
    ]
    
    for name, url in redis_urls:
        if not url:
            print(f'⚠️  {name}: NOT SET')
            continue
            
        try:
            client = redis.from_url(url.strip(), decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
            client.ping()
            print(f'✅ {name}: Connection successful')
        except Exception as e:
            print(f'❌ {name}: Connection failed - {e}')
            print(f'   URL: {url[:20]}... (length: {len(url)})')
            
except ImportError:
    print('⚠️  redis package not available')
except Exception as e:
    print(f'❌ Redis testing failed: {e}')
    print(f'Error type: {type(e).__name__}')
    print('Traceback:')
    traceback.print_exc()
"

# Test Gunicorn configuration
echo ""
echo "=== GUNICORN CONFIGURATION TEST ==="
if [ -f "gunicorn.conf.py" ]; then
    echo "✅ gunicorn.conf.py exists"
    python3 -c "
import gunicorn.conf
print('✅ Gunicorn configuration module loaded successfully')
"
else
    echo "❌ gunicorn.conf.py not found"
fi

echo ""
echo "🔍 DEBUGGING COMPLETE"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Check the output above for any ❌ failures"
echo "2. If app creation fails, that's likely the root cause"
echo "3. If Redis connections fail, check Redis URL configuration"
echo "4. If database connection fails, check DATABASE_URL"
echo "5. If imports fail, check requirements.txt installation"
echo "6. Check Render logs for additional error details"
