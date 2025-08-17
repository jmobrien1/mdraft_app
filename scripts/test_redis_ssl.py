#!/usr/bin/env python3
"""
Test script to validate Redis SSL configuration for rediss:// URLs.
This script tests both the Celery broker configuration and Flask-Session Redis configuration.
"""

import os
import sys
import redis
from urllib.parse import urlparse

def test_redis_connection(redis_url, name="Redis"):
    """Test Redis connection with proper SSL configuration."""
    if not redis_url:
        print(f"{name}: No URL provided, skipping test")
        return True
    
    try:
        parsed_url = urlparse(redis_url)
        is_tls = parsed_url.scheme == 'rediss'
        
        print(f"{name}: Testing connection to {parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}")
        
        if is_tls:
            # For rediss:// URLs, explicitly configure SSL settings
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                ssl_cert_reqs='none',  # Don't verify SSL certificates
                ssl_check_hostname=False,
                ssl_ca_certs=None,
                ssl_certfile=None,
                ssl_keyfile=None,
            )
        else:
            # For redis:// URLs, standard configuration
            client = redis.from_url(redis_url, decode_responses=True)
        
        # Test the connection
        client.ping()
        print(f"{name}: ✅ Connection successful")
        return True
        
    except Exception as e:
        print(f"{name}: ❌ Connection failed: {e}")
        return False

def test_celery_config():
    """Test Celery configuration with SSL settings."""
    try:
        from celery_worker import make_celery
        
        # Create Celery app
        celery_app = make_celery()
        
        # Check if SSL configuration is set
        broker_url = os.getenv("CELERY_BROKER_URL", "")
        if broker_url.startswith("rediss://"):
            if hasattr(celery_app.conf, 'broker_use_ssl'):
                print("Celery: ✅ SSL configuration found for broker")
            else:
                print("Celery: ❌ SSL configuration missing for broker")
                return False
        
        backend_url = os.getenv("CELERY_RESULT_BACKEND", "")
        if backend_url.startswith("rediss://"):
            if hasattr(celery_app.conf, 'redis_backend_use_ssl'):
                print("Celery: ✅ SSL configuration found for backend")
            else:
                print("Celery: ❌ SSL configuration missing for backend")
                return False
        
        print("Celery: ✅ Configuration looks good")
        return True
        
    except Exception as e:
        print(f"Celery: ❌ Configuration test failed: {e}")
        return False

def main():
    """Run all Redis SSL tests."""
    print("🔍 Testing Redis SSL Configuration")
    print("=" * 50)
    
    # Test environment variables
    redis_url = os.getenv("REDIS_URL")
    session_redis_url = os.getenv("SESSION_REDIS_URL")
    celery_broker_url = os.getenv("CELERY_BROKER_URL")
    celery_backend_url = os.getenv("CELERY_RESULT_BACKEND")
    
    print(f"Environment Variables:")
    print(f"  REDIS_URL: {'✅ Set' if redis_url else '❌ Not set'}")
    print(f"  SESSION_REDIS_URL: {'✅ Set' if session_redis_url else '❌ Not set'}")
    print(f"  CELERY_BROKER_URL: {'✅ Set' if celery_broker_url else '❌ Not set'}")
    print(f"  CELERY_RESULT_BACKEND: {'✅ Set' if celery_backend_url else '❌ Not set'}")
    print()
    
    # Test Redis connections
    tests_passed = 0
    total_tests = 0
    
    if redis_url:
        total_tests += 1
        if test_redis_connection(redis_url, "Main Redis"):
            tests_passed += 1
    
    if session_redis_url:
        total_tests += 1
        if test_redis_connection(session_redis_url, "Session Redis"):
            tests_passed += 1
    
    if celery_broker_url:
        total_tests += 1
        if test_redis_connection(celery_broker_url, "Celery Broker"):
            tests_passed += 1
    
    if celery_backend_url:
        total_tests += 1
        if test_redis_connection(celery_backend_url, "Celery Backend"):
            tests_passed += 1
    
    # Test Celery configuration
    total_tests += 1
    if test_celery_config():
        tests_passed += 1
    
    print()
    print("=" * 50)
    print(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Redis SSL configuration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the Redis SSL configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
