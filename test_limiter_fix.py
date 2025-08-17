#!/usr/bin/env python3
"""
Test script to verify Flask-Limiter initialization fix.
This script tests the bulletproof approach to ensure no UnboundLocalError occurs.
"""

import os
import sys
from unittest.mock import patch, MagicMock

def test_limiter_initialization():
    """Test that limiter initialization doesn't cause UnboundLocalError."""
    
    # Mock environment variables
    env_vars = {
        'FLASK_LIMITER_STORAGE_URI': 'memory://',
        'GLOBAL_RATE_LIMIT': '120 per minute',
        'FLASK_ENV': 'development'
    }
    
    with patch.dict(os.environ, env_vars):
        try:
            # Import the app module
            from app import create_app, limiter, _limiter_initialized
            
            print("✅ Successfully imported app module")
            print(f"✅ Global limiter exists: {limiter is not None}")
            print(f"✅ Initial limiter state: {_limiter_initialized}")
            
            # Test app creation
            app = create_app()
            print("✅ Successfully created Flask app")
            
            # Check limiter state after initialization
            print(f"✅ Final limiter state: {_limiter_initialized}")
            print(f"✅ Limiter default_limits: {limiter.default_limits}")
            
            return True
            
        except UnboundLocalError as e:
            print(f"❌ UnboundLocalError occurred: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

def test_limiter_with_redis_failure():
    """Test limiter behavior when Redis connection fails."""
    
    # Mock environment variables with invalid Redis URL
    env_vars = {
        'FLASK_LIMITER_STORAGE_URI': 'redis://invalid:6379/0',
        'GLOBAL_RATE_LIMIT': '120 per minute',
        'FLASK_ENV': 'development'
    }
    
    with patch.dict(os.environ, env_vars):
        try:
            # Import the app module
            from app import create_app, limiter, _limiter_initialized
            
            print("✅ Successfully imported app module with invalid Redis")
            
            # Test app creation (should handle Redis failure gracefully)
            app = create_app()
            print("✅ Successfully created Flask app despite Redis failure")
            
            # Check limiter state after initialization
            print(f"✅ Final limiter state: {_limiter_initialized}")
            print(f"✅ Limiter default_limits: {limiter.default_limits}")
            
            return True
            
        except UnboundLocalError as e:
            print(f"❌ UnboundLocalError occurred: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

if __name__ == "__main__":
    print("🧪 Testing Flask-Limiter initialization fix...")
    print("=" * 50)
    
    # Test 1: Normal initialization
    print("\n📋 Test 1: Normal initialization with memory storage")
    success1 = test_limiter_initialization()
    
    # Test 2: Redis failure
    print("\n📋 Test 2: Redis connection failure")
    success2 = test_limiter_with_redis_failure()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED! No UnboundLocalError detected.")
        sys.exit(0)
    else:
        print("💥 TESTS FAILED! UnboundLocalError or other issues detected.")
        sys.exit(1)
