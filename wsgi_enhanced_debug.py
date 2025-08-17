#!/usr/bin/env python3
"""
Enhanced WSGI Error Trap for Production Debugging

This version provides even more detailed error information to help identify
the exact cause of the 500 error in production.
"""

import os
import sys
import traceback
import logging
from pathlib import Path

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

print("=== ENHANCED WSGI DEBUG STARTING ===")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")
print(f"Environment: {os.getenv('FLASK_ENV', 'development')}")

# Check critical environment variables
critical_vars = ['DATABASE_URL', 'SECRET_KEY', 'REDIS_URL', 'SESSION_REDIS_URL', 'FLASK_LIMITER_STORAGE_URI']
for var in critical_vars:
    value = os.getenv(var)
    if value:
        print(f"✅ {var}: {'*' * min(len(value), 10)}... (length: {len(value)})")
        # Check for trailing whitespace
        if value != value.strip():
            print(f"   ⚠️  WARNING: {var} has trailing whitespace!")
    else:
        print(f"❌ {var}: NOT SET")

# Test basic imports
print("\n=== TESTING BASIC IMPORTS ===")
modules_to_test = ['flask', 'flask_sqlalchemy', 'flask_limiter', 'redis', 'sqlalchemy']
for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}: Imported successfully")
    except ImportError as e:
        print(f"❌ {module}: Import failed - {e}")
    except Exception as e:
        print(f"⚠️  {module}: Import error - {e}")

# Test app creation with detailed error handling
print("\n=== ATTEMPTING APP CREATION ===")
try:
    print("Step 1: Importing create_app...")
    from app import create_app
    print("✅ create_app imported successfully")
    
    print("Step 2: Testing configuration loading...")
    from app.config import get_config
    config = get_config()
    print("✅ Configuration loaded successfully")
    
    print("Step 3: Testing configuration validation...")
    config.validate()
    print("✅ Configuration validation passed")
    
    print("Step 4: Creating Flask app...")
    app = create_app()
    print("✅ Flask app created successfully")
    
    print("Step 5: Testing route registration...")
    root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
    print(f"✅ Root routes found: {len(root_routes)}")
    for route in root_routes:
        print(f"   - {route.endpoint}")
    
    print("✅ ALL STEPS COMPLETED SUCCESSFULLY")
    
except Exception as e:
    print(f"\n❌❌❌ FATAL: Exception occurred during app creation ❌❌❌")
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print("Full traceback:")
    traceback.print_exc()
    
    # Additional debugging information
    print(f"\n=== ADDITIONAL DEBUG INFO ===")
    print(f"Exception class: {e.__class__.__name__}")
    print(f"Exception module: {e.__class__.__module__}")
    
    # Check if it's an import error
    if isinstance(e, ImportError):
        print("This is an ImportError - likely missing dependency or path issue")
        print(f"Missing module: {e.name}")
    
    # Check if it's a configuration error
    if "config" in str(e).lower() or "configuration" in str(e).lower():
        print("This appears to be a configuration error")
    
    # Check if it's a database error
    if "database" in str(e).lower() or "connection" in str(e).lower():
        print("This appears to be a database connection error")
    
    # Check if it's a Redis error
    if "redis" in str(e).lower():
        print("This appears to be a Redis connection error")
    
    # Exit with error code
    sys.exit(1)

# Create middleware for request-level error trapping
class EnhancedExceptionTrapMiddleware:
    def __init__(self, app):
        self.app = app
        print("✅ Exception trap middleware initialized")

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except Exception as e:
            print(f"\n❌❌❌ FATAL: Exception occurred during request ❌❌❌")
            print(f"Request path: {environ.get('PATH_INFO', 'unknown')}")
            print(f"Request method: {environ.get('REQUEST_METHOD', 'unknown')}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()
            
            # Try to return a 500 error response
            try:
                start_response('500 INTERNAL SERVER ERROR', [
                    ('Content-Type', 'text/plain; charset=utf-8'),
                    ('Content-Length', '0')
                ])
                return [b'Internal Server Error']
            except:
                # If even the error response fails, return minimal response
                return [b'Server Error']

# Wrap the app with the enhanced middleware
app.wsgi_app = EnhancedExceptionTrapMiddleware(app.wsgi_app)

print("\n=== ENHANCED WSGI DEBUG COMPLETE ===")
print("✅ Application is wrapped and ready to serve requests")
print("Any errors will now be logged with full details")
