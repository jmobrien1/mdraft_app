#!/usr/bin/env python3
"""
Startup Validation for mdraft application.

This script validates that all critical components are working before
the application starts. It's designed to be run during deployment
to catch issues early.
"""

import os
import sys
import logging
import time
from typing import Dict, Any, List
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_environment() -> Dict[str, Any]:
    """Validate environment variables and configuration."""
    logger.info("Validating environment configuration...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    # Required environment variables
    required_vars = [
        'FLASK_ENV',
        'SECRET_KEY',
        'DATABASE_URL'
    ]
    
    for var in required_vars:
        if not os.environ.get(var):
            results['errors'].append(f"Missing required environment variable: {var}")
    
    # Optional but recommended variables
    optional_vars = [
        'SENTRY_DSN',
        'REDIS_URL',
        'GCS_BUCKET_NAME'
    ]
    
    for var in optional_vars:
        if not os.environ.get(var):
            results['warnings'].append(f"Missing optional environment variable: {var}")
    
    # Validate Flask environment
    flask_env = os.environ.get('FLASK_ENV', 'development')
    if flask_env not in ['development', 'production', 'testing']:
        results['warnings'].append(f"Unusual FLASK_ENV value: {flask_env}")
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def validate_database() -> Dict[str, Any]:
    """Validate database connectivity and schema."""
    logger.info("Validating database connectivity...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        from sqlalchemy import create_engine, text, inspect
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            results['errors'].append("DATABASE_URL not set")
            results['status'] = 'error'
            return results
        
        # Test connectivity
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Check required tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        required_tables = ['proposals', 'conversions', 'users', 'api_keys']
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            results['warnings'].append(f"Missing tables: {missing_tables}")
        
        # Check proposals table schema
        if 'proposals' in existing_tables:
            columns = [col['name'] for col in inspector.get_columns('proposals')]
            required_columns = ['id', 'title', 'created_at']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                results['warnings'].append(f"Missing columns in proposals table: {missing_columns}")
        
        logger.info(f"Database validation: {len(existing_tables)} tables found")
        
    except Exception as e:
        results['errors'].append(f"Database validation failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def validate_redis() -> Dict[str, Any]:
    """Validate Redis connectivity if configured."""
    logger.info("Validating Redis connectivity...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        results['warnings'].append("Redis not configured")
        return results
    
    try:
        import redis
        
        r = redis.from_url(redis_url)
        r.ping()
        logger.info("Redis connectivity: OK")
        
    except Exception as e:
        results['warnings'].append(f"Redis connectivity failed: {e}")
    
    return results


def validate_storage() -> Dict[str, Any]:
    """Validate storage configuration."""
    logger.info("Validating storage configuration...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    use_gcs = os.environ.get('USE_GCS', '0').lower() in ['1', 'true', 'yes']
    
    if use_gcs:
        # Validate Google Cloud Storage configuration
        gcs_bucket = os.environ.get('GCS_BUCKET_NAME')
        if not gcs_bucket:
            results['errors'].append("GCS_BUCKET_NAME required when USE_GCS=1")
        
        # Check for Google Cloud credentials
        if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            results['warnings'].append("GOOGLE_APPLICATION_CREDENTIALS not set")
    else:
        # Local storage - check if uploads directory exists
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            try:
                os.makedirs(uploads_dir, exist_ok=True)
                logger.info(f"Created uploads directory: {uploads_dir}")
            except Exception as e:
                results['warnings'].append(f"Could not create uploads directory: {e}")
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def validate_application_factory() -> Dict[str, Any]:
    """Validate that the Flask application can be created."""
    logger.info("Validating application factory...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        from app import create_app
        
        # Create the application
        app = create_app()
        
        # Test basic functionality
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/health/simple')
            if response.status_code != 200:
                results['errors'].append(f"Health endpoint returned {response.status_code}")
            
            # Test root endpoint
            response = client.get('/')
            if response.status_code not in [200, 302]:  # 302 for redirects
                results['warnings'].append(f"Root endpoint returned {response.status_code}")
        
        logger.info("Application factory validation: OK")
        
    except Exception as e:
        results['errors'].append(f"Application factory validation failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def validate_wsgi_entry_point() -> Dict[str, Any]:
    """Validate the WSGI entry point."""
    logger.info("Validating WSGI entry point...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Test importing the WSGI app
        from wsgi import app
        
        # Check if it's a Flask app
        from flask import Flask
        if not isinstance(app, Flask):
            results['errors'].append("WSGI app is not a Flask application")
        
        # Test basic functionality
        with app.test_client() as client:
            response = client.get('/health/simple')
            if response.status_code != 200:
                results['errors'].append(f"WSGI health endpoint returned {response.status_code}")
        
        logger.info("WSGI entry point validation: OK")
        
    except Exception as e:
        results['errors'].append(f"WSGI entry point validation failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def run_all_validations() -> Dict[str, Any]:
    """Run all validation checks."""
    logger.info("=== STARTUP VALIDATION STARTED ===")
    logger.info(f"Timestamp: {datetime.now()}")
    
    validations = [
        ('Environment', validate_environment),
        ('Database', validate_database),
        ('Redis', validate_redis),
        ('Storage', validate_storage),
        ('Application Factory', validate_application_factory),
        ('WSGI Entry Point', validate_wsgi_entry_point)
    ]
    
    all_results = {}
    has_errors = False
    has_warnings = False
    
    for name, validation_func in validations:
        logger.info(f"Running {name} validation...")
        try:
            result = validation_func()
            all_results[name] = result
            
            if result['status'] == 'error':
                has_errors = True
                logger.error(f"❌ {name} validation failed")
                for error in result['errors']:
                    logger.error(f"  - {error}")
            
            if result['warnings']:
                has_warnings = True
                logger.warning(f"⚠️  {name} validation warnings")
                for warning in result['warnings']:
                    logger.warning(f"  - {warning}")
            
            if result['status'] == 'ok' and not result['warnings']:
                logger.info(f"✅ {name} validation passed")
                
        except Exception as e:
            logger.error(f"❌ {name} validation crashed: {e}")
            all_results[name] = {
                'status': 'error',
                'errors': [f"Validation crashed: {e}"],
                'warnings': []
            }
            has_errors = True
    
    # Summary
    logger.info("=== VALIDATION SUMMARY ===")
    
    if has_errors:
        logger.error("❌ Validation failed - application may not start correctly")
        return {
            'status': 'error',
            'results': all_results,
            'message': 'Startup validation failed'
        }
    elif has_warnings:
        logger.warning("⚠️  Validation completed with warnings")
        return {
            'status': 'warning',
            'results': all_results,
            'message': 'Startup validation completed with warnings'
        }
    else:
        logger.info("✅ All validations passed")
        return {
            'status': 'ok',
            'results': all_results,
            'message': 'Startup validation completed successfully'
        }


def main():
    """Main validation function."""
    try:
        result = run_all_validations()
        
        if result['status'] == 'error':
            logger.error("=== STARTUP VALIDATION FAILED ===")
            return 1
        elif result['status'] == 'warning':
            logger.warning("=== STARTUP VALIDATION COMPLETED WITH WARNINGS ===")
            return 0
        else:
            logger.info("=== STARTUP VALIDATION COMPLETED SUCCESSFULLY ===")
            return 0
            
    except Exception as e:
        logger.error(f"Validation script crashed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
