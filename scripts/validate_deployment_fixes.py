#!/usr/bin/env python3
"""
Deployment Validation Script for mdraft application.

This script validates that all the deployment fixes are working correctly:
1. WSGI entry point functionality
2. Database migration handling
3. Application startup validation
4. Error visibility and logging
5. Health endpoint functionality
"""

import os
import sys
import logging
import subprocess
import time
from typing import Dict, Any, List
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_wsgi_entry_point() -> Dict[str, Any]:
    """Test the WSGI entry point functionality."""
    logger.info("Testing WSGI entry point...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Add current directory to Python path
        import sys
        import os
        sys.path.insert(0, os.getcwd())
        
        # Test importing the WSGI app
        from wsgi import app
        
        # Check if it's a Flask app
        from flask import Flask
        if not isinstance(app, Flask):
            results['errors'].append("WSGI app is not a Flask application")
        
        # Test basic functionality
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/health/simple')
            if response.status_code == 200:
                logger.info("WSGI health endpoint: OK")
            else:
                results['errors'].append(f"WSGI health endpoint returned {response.status_code}")
            
            # Test root endpoint
            response = client.get('/')
            if response.status_code in [200, 302]:
                logger.info("WSGI root endpoint: OK")
            else:
                results['warnings'].append(f"WSGI root endpoint returned {response.status_code}")
        
        logger.info("WSGI entry point validation: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"WSGI entry point test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def test_migration_doctor() -> Dict[str, Any]:
    """Test the migration doctor functionality."""
    logger.info("Testing migration doctor...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Check if migration doctor script exists
        if not os.path.exists('scripts/migration_doctor.py'):
            results['warnings'].append("migration_doctor.py not found")
            return results
        
        # Run migration doctor in diagnostic mode (no --fix)
        result = subprocess.run(
            [sys.executable, 'scripts/migration_doctor.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("Migration doctor diagnostic: SUCCESS")
        else:
            results['warnings'].append(f"Migration doctor diagnostic failed: {result.stderr}")
        
        # Check if the script has the expected functionality
        with open('scripts/migration_doctor.py', 'r') as f:
            content = f.read()
            
        expected_functions = [
            'check_database_connectivity',
            'check_migration_state',
            'check_schema_consistency',
            'run_migrations',
            'create_missing_tables'
        ]
        
        for func in expected_functions:
            if func not in content:
                results['warnings'].append(f"Migration doctor missing function: {func}")
        
        logger.info("Migration doctor validation: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"Migration doctor test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def test_startup_validation() -> Dict[str, Any]:
    """Test the startup validation functionality."""
    logger.info("Testing startup validation...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Check if startup validation script exists
        if not os.path.exists('scripts/startup_validation.py'):
            results['warnings'].append("startup_validation.py not found")
            return results
        
        # Run startup validation
        result = subprocess.run(
            [sys.executable, 'scripts/startup_validation.py'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            logger.info("Startup validation: SUCCESS")
        elif result.returncode == 1:
            results['warnings'].append("Startup validation completed with warnings")
        else:
            results['errors'].append(f"Startup validation failed: {result.stderr}")
        
        # Check if the script has the expected functionality
        with open('scripts/startup_validation.py', 'r') as f:
            content = f.read()
            
        expected_functions = [
            'validate_environment',
            'validate_database',
            'validate_redis',
            'validate_storage',
            'validate_application_factory',
            'validate_wsgi_entry_point'
        ]
        
        for func in expected_functions:
            if func not in content:
                results['warnings'].append(f"Startup validation missing function: {func}")
        
        logger.info("Startup validation test: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"Startup validation test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def test_predeploy_script() -> Dict[str, Any]:
    """Test the predeploy script functionality."""
    logger.info("Testing predeploy script...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Check if predeploy script exists
        if not os.path.exists('scripts/predeploy.sh'):
            results['warnings'].append("predeploy.sh not found")
            return results
        
        # Check if the script is executable
        if not os.access('scripts/predeploy.sh', os.X_OK):
            results['warnings'].append("predeploy.sh is not executable")
        
        # Check if the script has the expected functionality
        with open('scripts/predeploy.sh', 'r') as f:
            content = f.read()
            
        expected_features = [
            'migration_doctor.py',
            'startup_validation.py',
            'wsgi.py',
            'app/__init__.py',
            'requirements.txt'
        ]
        
        for feature in expected_features:
            if feature not in content:
                results['warnings'].append(f"Predeploy script missing feature: {feature}")
        
        # Check for error handling
        if 'set -e' not in content:
            results['warnings'].append("Predeploy script missing error handling (set -e)")
        
        if 'set -o pipefail' not in content:
            results['warnings'].append("Predeploy script missing pipe failure handling")
        
        logger.info("Predeploy script validation: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"Predeploy script test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def test_error_visibility() -> Dict[str, Any]:
    """Test error visibility and logging functionality."""
    logger.info("Testing error visibility...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Add current directory to Python path
        import sys
        import os
        sys.path.insert(0, os.getcwd())
        
        # Test that the WSGI app has error handling
        from wsgi import app
        
        # Check if the app has error handlers
        if not hasattr(app, 'error_handler_spec') or not app.error_handler_spec:
            results['warnings'].append("No error handlers registered")
        
        # Test error handling by making a request to a non-existent endpoint
        with app.test_client() as client:
            response = client.get('/non-existent-endpoint')
            if response.status_code == 404:
                logger.info("404 error handling: OK")
            else:
                results['warnings'].append(f"Unexpected response for non-existent endpoint: {response.status_code}")
        
        # Check if logging is configured
        if not app.logger.handlers:
            results['warnings'].append("No logging handlers configured")
        
        logger.info("Error visibility validation: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"Error visibility test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def test_health_endpoints() -> Dict[str, Any]:
    """Test health endpoint functionality."""
    logger.info("Testing health endpoints...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Add current directory to Python path
        import sys
        import os
        sys.path.insert(0, os.getcwd())
        
        from wsgi import app
        
        with app.test_client() as client:
            # Test /health/simple endpoint
            response = client.get('/health/simple')
            if response.status_code == 200:
                logger.info("Health simple endpoint: OK")
                try:
                    data = response.get_json()
                    if data and 'status' in data:
                        logger.info(f"Health response: {data['status']}")
                    else:
                        results['warnings'].append("Health endpoint response missing status field")
                except Exception:
                    results['warnings'].append("Health endpoint response is not JSON")
            else:
                results['errors'].append(f"Health simple endpoint returned {response.status_code}")
            
            # Test /health endpoint (if it exists)
            response = client.get('/health')
            if response.status_code in [200, 404]:
                if response.status_code == 200:
                    logger.info("Health endpoint: OK")
                else:
                    logger.info("Health endpoint not found (expected)")
            else:
                results['warnings'].append(f"Health endpoint returned unexpected status: {response.status_code}")
        
        logger.info("Health endpoints validation: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"Health endpoints test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def test_render_configuration() -> Dict[str, Any]:
    """Test Render configuration compatibility."""
    logger.info("Testing Render configuration...")
    
    results = {
        'status': 'ok',
        'errors': [],
        'warnings': []
    }
    
    try:
        # Check if render.yaml exists
        if not os.path.exists('render.yaml'):
            results['warnings'].append("render.yaml not found")
            return results
        
        with open('render.yaml', 'r') as f:
            content = f.read()
        
        # Check for required configuration
        required_config = [
            'wsgi:app',
            'healthCheckPath: /health/simple',
            'preDeployCommand: bash scripts/predeploy.sh'
        ]
        
        for config in required_config:
            if config not in content:
                results['errors'].append(f"Missing required Render configuration: {config}")
        
        # Check for proper start command
        if 'gunicorn' not in content:
            results['warnings'].append("Gunicorn not configured in start command")
        
        logger.info("Render configuration validation: SUCCESS")
        
    except Exception as e:
        results['errors'].append(f"Render configuration test failed: {e}")
        results['status'] = 'error'
    
    if results['errors']:
        results['status'] = 'error'
    
    return results


def run_all_tests() -> Dict[str, Any]:
    """Run all deployment validation tests."""
    logger.info("=== DEPLOYMENT VALIDATION STARTED ===")
    logger.info(f"Timestamp: {datetime.now()}")
    
    tests = [
        ('WSGI Entry Point', test_wsgi_entry_point),
        ('Migration Doctor', test_migration_doctor),
        ('Startup Validation', test_startup_validation),
        ('Predeploy Script', test_predeploy_script),
        ('Error Visibility', test_error_visibility),
        ('Health Endpoints', test_health_endpoints),
        ('Render Configuration', test_render_configuration)
    ]
    
    all_results = {}
    has_errors = False
    has_warnings = False
    
    for name, test_func in tests:
        logger.info(f"Running {name} test...")
        try:
            result = test_func()
            all_results[name] = result
            
            if result['status'] == 'error':
                has_errors = True
                logger.error(f"❌ {name} test failed")
                for error in result['errors']:
                    logger.error(f"  - {error}")
            
            if result['warnings']:
                has_warnings = True
                logger.warning(f"⚠️  {name} test warnings")
                for warning in result['warnings']:
                    logger.warning(f"  - {warning}")
            
            if result['status'] == 'ok' and not result['warnings']:
                logger.info(f"✅ {name} test passed")
                
        except Exception as e:
            logger.error(f"❌ {name} test crashed: {e}")
            all_results[name] = {
                'status': 'error',
                'errors': [f"Test crashed: {e}"],
                'warnings': []
            }
            has_errors = True
    
    # Summary
    logger.info("=== VALIDATION SUMMARY ===")
    
    if has_errors:
        logger.error("❌ Deployment validation failed")
        return {
            'status': 'error',
            'results': all_results,
            'message': 'Deployment validation failed'
        }
    elif has_warnings:
        logger.warning("⚠️  Deployment validation completed with warnings")
        return {
            'status': 'warning',
            'results': all_results,
            'message': 'Deployment validation completed with warnings'
        }
    else:
        logger.info("✅ All deployment validations passed")
        return {
            'status': 'ok',
            'results': all_results,
            'message': 'Deployment validation completed successfully'
        }


def main():
    """Main validation function."""
    try:
        result = run_all_tests()
        
        if result['status'] == 'error':
            logger.error("=== DEPLOYMENT VALIDATION FAILED ===")
            return 1
        elif result['status'] == 'warning':
            logger.warning("=== DEPLOYMENT VALIDATION COMPLETED WITH WARNINGS ===")
            return 0
        else:
            logger.info("=== DEPLOYMENT VALIDATION COMPLETED SUCCESSFULLY ===")
            return 0
            
    except Exception as e:
        logger.error(f"Validation script crashed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
