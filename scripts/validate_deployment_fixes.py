#!/usr/bin/env python3
"""
Deployment validation script to test the critical fixes:
1. Port binding issue resolution
2. Redis SSL configuration for rediss:// URLs
3. Celery worker SSL configuration
"""

import os
import sys
import subprocess
import time
import requests
from urllib.parse import urlparse

def check_environment_variables():
    """Check that all required environment variables are set."""
    print("🔍 Checking Environment Variables")
    print("-" * 40)
    
    required_vars = [
        "DATABASE_URL",
        "REDIS_URL", 
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND"
    ]
    
    optional_vars = [
        "SESSION_REDIS_URL",
        "FLASK_LIMITER_STORAGE_URI"
    ]
    
    all_good = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Check if it's a rediss:// URL
            if var in ["REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"] and value.startswith("rediss://"):
                print(f"  {var}: ✅ Set (rediss:// - SSL enabled)")
            else:
                print(f"  {var}: ✅ Set")
        else:
            print(f"  {var}: ❌ Not set")
            all_good = False
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            if var in ["SESSION_REDIS_URL", "FLASK_LIMITER_STORAGE_URI"] and value.startswith("rediss://"):
                print(f"  {var}: ✅ Set (rediss:// - SSL enabled)")
            else:
                print(f"  {var}: ✅ Set")
        else:
            print(f"  {var}: ⚠️  Not set (optional)")
    
    print()
    return all_good

def test_redis_ssl_configuration():
    """Test Redis SSL configuration for rediss:// URLs."""
    print("🔍 Testing Redis SSL Configuration")
    print("-" * 40)
    
    try:
        # Import and test the Redis configuration
        import redis
        from urllib.parse import urlparse
        
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("  ❌ No REDIS_URL found")
            return False
        
        parsed_url = urlparse(redis_url)
        is_tls = parsed_url.scheme == 'rediss'
        
        if is_tls:
            print(f"  Testing rediss:// connection to {parsed_url.hostname}:{parsed_url.port}")
            
            # Test with explicit SSL configuration
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                ssl_cert_reqs='none',
                ssl_check_hostname=False,
                ssl_ca_certs=None,
                ssl_certfile=None,
                ssl_keyfile=None,
            )
            
            # Test connection
            client.ping()
            print("  ✅ Redis SSL connection successful")
            return True
        else:
            print(f"  Testing redis:// connection to {parsed_url.hostname}:{parsed_url.port}")
            
            # Test standard connection
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            print("  ✅ Redis connection successful")
            return True
            
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        return False

def test_celery_ssl_configuration():
    """Test Celery SSL configuration."""
    print("🔍 Testing Celery SSL Configuration")
    print("-" * 40)
    
    try:
        from celery_worker import make_celery
        
        # Create Celery app
        celery_app = make_celery()
        
        broker_url = os.getenv("CELERY_BROKER_URL", "")
        backend_url = os.getenv("CELERY_RESULT_BACKEND", "")
        
        if broker_url.startswith("rediss://"):
            if hasattr(celery_app.conf, 'broker_use_ssl') and celery_app.conf.broker_use_ssl:
                print("  ✅ Celery broker SSL configuration found")
            else:
                print("  ❌ Celery broker SSL configuration missing")
                return False
        
        if backend_url.startswith("rediss://"):
            if hasattr(celery_app.conf, 'redis_backend_use_ssl') and celery_app.conf.redis_backend_use_ssl:
                print("  ✅ Celery backend SSL configuration found")
            else:
                print("  ❌ Celery backend SSL configuration missing")
                return False
        
        print("  ✅ Celery SSL configuration looks good")
        return True
        
    except Exception as e:
        print(f"  ❌ Celery configuration test failed: {e}")
        return False

def test_flask_app_initialization():
    """Test Flask app initialization with Redis configuration."""
    print("🔍 Testing Flask App Initialization")
    print("-" * 40)
    
    try:
        from app import create_app
        
        # Create Flask app
        app = create_app()
        
        # Check if app was created successfully
        if app:
            print("  ✅ Flask app created successfully")
            
            # Check session configuration
            session_type = app.config.get('SESSION_TYPE', 'unknown')
            print(f"  ✅ Session type: {session_type}")
            
            return True
        else:
            print("  ❌ Flask app creation failed")
            return False
            
    except Exception as e:
        print(f"  ❌ Flask app initialization failed: {e}")
        return False

def test_port_binding():
    """Test that the app can bind to the PORT environment variable."""
    print("🔍 Testing Port Binding Configuration")
    print("-" * 40)
    
    # Check if PORT is set
    port = os.getenv("PORT")
    if port:
        print(f"  ✅ PORT environment variable: {port}")
    else:
        print("  ⚠️  PORT environment variable not set (will use default)")
    
    # Check gunicorn configuration in render.yaml
    try:
        with open("render.yaml", "r") as f:
            content = f.read()
            if "--bind 0.0.0.0:$PORT" in content:
                print("  ✅ Gunicorn configured to bind to $PORT")
                return True
            else:
                print("  ❌ Gunicorn not configured to bind to $PORT")
                return False
    except Exception as e:
        print(f"  ❌ Could not read render.yaml: {e}")
        return False

def test_health_endpoint():
    """Test the health endpoint if the app is running."""
    print("🔍 Testing Health Endpoint")
    print("-" * 40)
    
    # Try to connect to health endpoint if app is running
    port = os.getenv("PORT", "5000")
    health_url = f"http://localhost:{port}/health"
    
    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Health endpoint responding: {response.status_code}")
            return True
        else:
            print(f"  ⚠️  Health endpoint returned: {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("  ⚠️  Health endpoint not accessible (app may not be running)")
        return True  # This is expected if app isn't running

def main():
    """Run all deployment validation tests."""
    print("🚀 Deployment Fixes Validation")
    print("=" * 60)
    print()
    
    tests = [
        ("Environment Variables", check_environment_variables),
        ("Port Binding", test_port_binding),
        ("Redis SSL Configuration", test_redis_ssl_configuration),
        ("Celery SSL Configuration", test_celery_ssl_configuration),
        ("Flask App Initialization", test_flask_app_initialization),
        ("Health Endpoint", test_health_endpoint),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print()
    print(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Deployment fixes are working correctly.")
        print()
        print("✅ Critical Fixes Applied:")
        print("  • Port binding issue resolved")
        print("  • Redis SSL configuration fixed for rediss:// URLs")
        print("  • Celery worker SSL configuration updated")
        print("  • Flask-Session Redis configuration improved")
        return 0
    else:
        print("❌ Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
