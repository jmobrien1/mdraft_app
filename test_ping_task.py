#!/usr/bin/env python3
"""
Simple test script for the ping task.
This script tests the ping task functionality without requiring a full Celery setup.
"""

import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ping_task_function():
    """Test the ping task function directly."""
    try:
        from app.celery_tasks import ping_task
        
        print("Testing ping_task function directly...")
        result = ping_task("test message")
        
        print(f"✅ Function test passed!")
        print(f"Result: {result}")
        
        # Verify expected fields
        expected_fields = ['status', 'message', 'task_id', 'timestamp', 'worker_id']
        for field in expected_fields:
            if field not in result:
                print(f"❌ Missing field: {field}")
                return False
        
        print(f"✅ All expected fields present")
        return True
        
    except Exception as e:
        print(f"❌ Function test failed: {e}")
        return False

def test_celery_worker_config():
    """Test Celery worker configuration."""
    try:
        from celery_worker import celery, test_broker_connection
        
        print("\nTesting Celery worker configuration...")
        
        # Test broker connection
        connection_ok = test_broker_connection()
        
        if connection_ok:
            print("✅ Broker connection test passed")
        else:
            print("⚠️  Broker connection test failed (expected in development)")
        
        # Check task registration
        registered_tasks = celery.tasks.keys()
        ping_task_registered = 'ping_task' in registered_tasks
        
        if ping_task_registered:
            print("✅ Ping task is registered")
        else:
            print("❌ Ping task is not registered")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Ping Task Test Suite")
    print("=" * 50)
    
    # Test 1: Function test
    test1_passed = test_ping_task_function()
    
    # Test 2: Configuration test
    test2_passed = test_celery_worker_config()
    
    print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        print("✅ All tests PASSED")
        print("\nTo test with actual Celery worker:")
        print("1. Start Redis: brew services start redis")
        print("2. Start worker: celery -A celery_worker worker --loglevel=info")
        print("3. Run ping: python scripts/ping_celery.py")
        sys.exit(0)
    else:
        print("❌ Some tests FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
