#!/usr/bin/env python3
"""
Startup validation script for mdraft application.

This script validates that the application can start without errors
and identifies any missing dependencies or configuration issues.
"""

import os
import sys
import traceback

def check_environment():
    """Check required environment variables."""
    print("=== Environment Check ===")
    required_vars = [
        'PYTHONPATH',
        'FLASK_APP',
        'DATABASE_URL',
        'GCS_BUCKET_NAME',
        'GCS_PROCESSED_BUCKET_NAME',
        'GOOGLE_CLOUD_PROJECT'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'password' in var.lower() or 'secret' in var.lower() or 'key' in var.lower():
                print(f"✅ {var}: [SET]")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT_SET")

def check_python_path():
    """Check Python path and imports."""
    print("\n=== Python Path Check ===")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path[0]}")
    
    # Check if we can import the app
    try:
        import app
        print(f"✅ App imported from: {app.__file__}")
    except Exception as e:
        print(f"❌ Failed to import app: {e}")
        traceback.print_exc()
        return False
    
    return True

def check_flask_app():
    """Check if Flask app can be created."""
    print("\n=== Flask App Check ===")
    try:
        from app import create_app
        app = create_app()
        print("✅ Flask app created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create Flask app: {e}")
        traceback.print_exc()
        return False

def check_database():
    """Check database connectivity."""
    print("\n=== Database Check ===")
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        from sqlalchemy import create_engine, text
        
        # Normalize URL for psycopg
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        
        engine = create_engine(database_url, future=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_optional_dependencies():
    """Check optional dependencies."""
    print("\n=== Optional Dependencies Check ===")
    
    optional_deps = [
        ('markitdown', 'Document conversion library'),
        ('onnxruntime', 'Machine learning runtime'),
        ('azure.ai.documentintelligence', 'Azure Document AI'),
    ]
    
    for module, description in optional_deps:
        try:
            __import__(module)
            print(f"✅ {module}: {description}")
        except ImportError:
            print(f"⚠️  {module}: {description} (not available - will use fallbacks)")

def main():
    """Run all validation checks."""
    print("=== MDRAFT STARTUP VALIDATION ===")
    
    # Set default environment variables for testing
    if not os.getenv('PYTHONPATH'):
        os.environ['PYTHONPATH'] = '/opt/render/project/src'
    if not os.getenv('FLASK_APP'):
        os.environ['FLASK_APP'] = 'wsgi.py'
    
    checks = [
        check_environment,
        check_python_path,
        check_flask_app,
        check_database,
        check_optional_dependencies,
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with exception: {e}")
            traceback.print_exc()
            results.append(False)
    
    print("\n=== SUMMARY ===")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total} checks")
    
    if passed == total:
        print("✅ All checks passed - application should start successfully")
        return 0
    else:
        print("❌ Some checks failed - review the output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
