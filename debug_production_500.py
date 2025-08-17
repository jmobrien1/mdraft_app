#!/usr/bin/env python3
"""
Production 500 Error Debugging Script

This script helps identify the root cause of 500 Internal Server Error
in production when local testing succeeds.

Usage:
    python debug_production_500.py
"""

import os
import sys
import traceback
import importlib
from pathlib import Path

def debug_environment():
    """Debug environment differences between local and production."""
    print("=== ENVIRONMENT DEBUGGING ===")
    
    # Check critical environment variables
    env_vars = [
        'FLASK_ENV', 'FLASK_DEBUG', 'PYTHONPATH', 'DATABASE_URL',
        'SECRET_KEY', 'REDIS_URL', 'SESSION_REDIS_URL', 'FLASK_LIMITER_STORAGE_URI'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}... (length: {len(value)})")
            # Check for whitespace issues
            if value != value.strip():
                print(f"   ⚠️  WARNING: {var} has trailing whitespace!")
                print(f"   Original: {repr(value)}")
                print(f"   Stripped: {repr(value.strip())}")
        else:
            print(f"❌ {var}: NOT SET")
    
    print(f"Working Directory: {os.getcwd()}")
    print(f"Python Version: {sys.version}")
    print(f"Python Path: {sys.path}")
    print()

def debug_imports():
    """Debug import issues that might cause production failures."""
    print("=== IMPORT DEBUGGING ===")
    
    modules_to_test = [
        'flask',
        'flask_sqlalchemy', 
        'flask_migrate',
        'flask_limiter',
        'flask_bcrypt',
        'flask_login',
        'flask_wtf',
        'flask_session',
        'sqlalchemy',
        'psycopg',
        'redis',
        'celery',
        'gunicorn'
    ]
    
    failed_imports = []
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}: Imported successfully")
        except ImportError as e:
            print(f"❌ {module}: Import failed - {e}")
            failed_imports.append(module)
        except Exception as e:
            print(f"⚠️  {module}: Import error - {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n❌ FAILED IMPORTS: {failed_imports}")
    else:
        print("\n✅ All imports successful")
    print()

def debug_app_creation():
    """Debug Flask app creation process."""
    print("=== APP CREATION DEBUGGING ===")
    
    try:
        # Test basic imports
        print("Testing basic imports...")
        from app import create_app
        print("✅ create_app imported successfully")
        
        # Test configuration loading
        print("Testing configuration loading...")
        from app.config import get_config
        config = get_config()
        print("✅ Configuration loaded successfully")
        
        # Test configuration validation
        print("Testing configuration validation...")
        config.validate()
        print("✅ Configuration validation passed")
        
        # Test app creation
        print("Testing app creation...")
        app = create_app()
        print("✅ App created successfully")
        
        # Test route registration
        print("Testing route registration...")
        root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
        print(f"✅ Root routes found: {len(root_routes)}")
        for route in root_routes:
            print(f"   - {route.endpoint}")
        
        # Test view function
        print("Testing view function...")
        with app.test_request_context('/'):
            view_func = app.view_functions.get('ui.index')
            if view_func:
                print("✅ View function found")
                # Don't actually call it to avoid side effects
            else:
                print("❌ View function not found")
        
        return True
        
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        return False

def debug_gunicorn_issues():
    """Debug Gunicorn-specific issues."""
    print("=== GUNICORN DEBUGGING ===")
    
    # Check Gunicorn environment
    gunicorn_vars = [
        'GUNICORN_CMD_ARGS',
        'GUNICORN_APP_MODULE',
        'GUNICORN_APP_NAME'
    ]
    
    for var in gunicorn_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: NOT SET")
    
    # Test WSGI app loading
    try:
        print("Testing WSGI app loading...")
        from wsgi import app
        print("✅ WSGI app loaded successfully")
        
        # Test app attributes
        print(f"App name: {app.name}")
        print(f"App debug: {app.debug}")
        print(f"App testing: {app.testing}")
        
        return True
    except Exception as e:
        print(f"❌ WSGI app loading failed: {e}")
        print(f"Error type: {type(e).__name__}")
        print("Traceback:")
        traceback.print_exc()
        return False

def debug_redis_connections():
    """Debug Redis connection issues."""
    print("=== REDIS DEBUGGING ===")
    
    redis_urls = [
        ('REDIS_URL', os.getenv('REDIS_URL')),
        ('SESSION_REDIS_URL', os.getenv('SESSION_REDIS_URL')),
        ('FLASK_LIMITER_STORAGE_URI', os.getenv('FLASK_LIMITER_STORAGE_URI'))
    ]
    
    for name, url in redis_urls:
        if not url:
            print(f"⚠️  {name}: NOT SET")
            continue
            
        try:
            import redis
            client = redis.from_url(url.strip(), decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
            client.ping()
            print(f"✅ {name}: Connection successful")
        except Exception as e:
            print(f"❌ {name}: Connection failed - {e}")
            print(f"   URL: {url[:20]}... (length: {len(url)})")

def debug_database_connection():
    """Debug database connection issues."""
    print("=== DATABASE DEBUGGING ===")
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL: NOT SET")
        return False
    
    try:
        from sqlalchemy import create_engine, text
        from app.utils.db_url import normalize_db_url
        
        # Test URL normalization
        normalized_url = normalize_db_url(db_url)
        print(f"✅ Database URL normalized successfully")
        print(f"   Original length: {len(db_url)}")
        print(f"   Normalized length: {len(normalized_url)}")
        
        # Test engine creation
        engine = create_engine(normalized_url, pool_pre_ping=True)
        print("✅ Database engine created successfully")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection test successful")
        
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print(f"Error type: {type(e).__name__}")
        print("Traceback:")
        traceback.print_exc()
        return False

def main():
    """Run all debugging checks."""
    print("🔍 PRODUCTION 500 ERROR DEBUGGING")
    print("=" * 50)
    
    # Run all debugging functions
    debug_environment()
    debug_imports()
    debug_redis_connections()
    debug_database_connection()
    debug_gunicorn_issues()
    debug_app_creation()
    
    print("=" * 50)
    print("🔍 DEBUGGING COMPLETE")
    print("\nNext steps:")
    print("1. Check the output above for any ❌ failures")
    print("2. If app creation fails, that's likely the root cause")
    print("3. If Redis connections fail, check Redis URL configuration")
    print("4. If database connection fails, check DATABASE_URL")
    print("5. If imports fail, check requirements.txt installation")

if __name__ == "__main__":
    main()
