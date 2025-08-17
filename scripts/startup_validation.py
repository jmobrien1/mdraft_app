#!/usr/bin/env python3
"""
Startup validation script for mdraft application.

This script performs comprehensive validation of the application startup
process to help troubleshoot deployment issues on Render.
"""
import os
import sys
import traceback
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def validate_environment():
    """Validate environment variables and configuration."""
    print("=== Environment Validation ===")
    
    # Check critical environment variables
    critical_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'FLASK_ENV',
    ]
    
    for var in critical_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}... (length: {len(value)})")
        else:
            print(f"❌ {var}: NOT SET")
    
    # Check optional but important variables
    optional_vars = [
        'REDIS_URL',
        'SESSION_BACKEND',
        'LOG_LEVEL',
        'SENTRY_DSN',
    ]
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}... (length: {len(value)})")
        else:
            print(f"⚠️  {var}: NOT SET (optional)")
    
    print()

def validate_imports():
    """Validate that all required modules can be imported."""
    print("=== Import Validation ===")
    
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
    ]
    
    all_successful = True
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}: Imported successfully")
        except ImportError as e:
            print(f"❌ {module}: Import failed - {e}")
            all_successful = False
        except Exception as e:
            print(f"⚠️  {module}: Import error - {e}")
            all_successful = False
    
    print()
    return all_successful

def validate_app_imports():
    """Validate that app modules can be imported."""
    print("=== App Module Import Validation ===")
    
    # Test core app import first
    try:
        import app
        print(f"✅ app: Imported successfully from {app.__file__}")
    except ImportError as e:
        print(f"❌ app: Import failed - {e}")
        return False
    except Exception as e:
        print(f"⚠️  app: Import error - {e}")
        return False
    
    # Test key modules
    key_modules = [
        'app.config',
        'app.models',
        'app.ui',
        'app.routes',
        'app.health',
    ]
    
    for module in key_modules:
        try:
            __import__(module)
            print(f"✅ {module}: Imported successfully")
        except ImportError as e:
            print(f"❌ {module}: Import failed - {e}")
        except Exception as e:
            print(f"⚠️  {module}: Import error - {e}")
    
    print()
    return True

def validate_configuration():
    """Validate configuration loading."""
    print("=== Configuration Validation ===")
    
    try:
        from app.config import get_config, ConfigurationError
        
        print("Loading configuration...")
        config = get_config()
        print("✅ Configuration loaded successfully")
        
        print("Validating configuration...")
        config.validate()
        print("✅ Configuration validation passed")
        
        # Test some configuration values
        print(f"Database URL type: {type(config.DATABASE_URL)}")
        print(f"Database URL length: {len(config.DATABASE_URL) if config.DATABASE_URL else 0}")
        print(f"Session backend: {config.SESSION_BACKEND}")
        print(f"Login disabled: {config.LOGIN_DISABLED}")
        
    except ConfigurationError as e:
        print(f"❌ Configuration validation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        return False
    
    print()
    return True

def validate_database():
    """Validate database connectivity."""
    print("=== Database Validation ===")
    
    try:
        from app.config import get_config
        from app.utils.db_url import normalize_db_url
        
        config = get_config()
        db_url = normalize_db_url(config.DATABASE_URL)
        
        print(f"Database URL normalized successfully")
        print(f"Database URL type: {type(db_url)}")
        print(f"Database URL length: {len(db_url) if db_url else 0}")
        
        # Try to create a test connection
        from sqlalchemy import create_engine, text
        
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection test successful")
            
    except Exception as e:
        print(f"❌ Database validation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        return False
    
    print()
    return True

def validate_app_creation():
    """Validate Flask app creation."""
    print("=== Flask App Creation Validation ===")
    
    try:
        from app import create_app
        
        print("Creating Flask app...")
        app = create_app()
        print("✅ Flask app created successfully")
        
        # Check if critical routes are registered
        root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
        print(f"Root routes: {len(root_routes)}")
        for route in root_routes:
            print(f"  - {route.endpoint}")
        
        health_routes = [r for r in app.url_map.iter_rules() if "health" in r.rule]
        print(f"Health routes: {len(health_routes)}")
        for route in health_routes:
            print(f"  - {route.rule} -> {route.endpoint}")
        
        total_routes = len(list(app.url_map.iter_rules()))
        print(f"Total routes: {total_routes}")
        
        return app
        
    except Exception as e:
        print(f"❌ Flask app creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

def validate_app_context():
    """Validate app context operations."""
    print("=== App Context Validation ===")
    
    try:
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            print("✅ App context created successfully")
            
            # Test database operations
            from app import db
            from sqlalchemy import text
            
            result = db.session.execute(text("SELECT 1"))
            print("✅ Database query in app context successful")
            
            # Test configuration access
            from flask import current_app
            print(f"App name: {current_app.name}")
            print(f"App config keys: {len(current_app.config)}")
            
    except Exception as e:
        print(f"❌ App context validation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        return False
    
    print()
    return True

def main():
    """Run all validation checks."""
    print("🚀 Starting mdraft application validation...")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print()
    
    # Run validation checks
    validate_environment()
    
    if not validate_imports():
        print("❌ Import validation failed")
        return 1
    
    if not validate_app_imports():
        print("❌ App module import validation failed")
        return 1
    
    if not validate_configuration():
        print("❌ Configuration validation failed")
        return 1
    
    if not validate_database():
        print("❌ Database validation failed")
        return 1
    
    app = validate_app_creation()
    if not app:
        print("❌ Flask app creation failed")
        return 1
    
    if not validate_app_context():
        print("❌ App context validation failed")
        return 1
    
    print("🎉 All validation checks passed!")
    print("The application should be ready to start.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
