#!/usr/bin/env python3
"""
Celery Ping Test Script

This script tests the Celery worker connectivity by sending a ping task.
Use this to verify that:
1. The worker can receive tasks
2. The worker can process tasks  
3. The worker can return results

Usage:
    python scripts/ping_celery.py [message]

Example:
    python scripts/ping_celery.py "hello worker"
"""

import os
import sys
import time
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_celery_ping(message: str = "pong") -> bool:
    """Test Celery ping task and return success status."""
    
    try:
        # Import Celery app
        from celery_worker import celery
        
        print(f"Testing Celery ping with message: '{message}'")
        print(f"Broker URL: {os.getenv('CELERY_BROKER_URL', 'NOT SET')}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print("-" * 50)
        
        # Send ping task
        print("Sending ping task...")
        task = celery.send_task('ping_task', args=[message])
        
        print(f"Task ID: {task.id}")
        print("Waiting for result...")
        
        # Wait for result with timeout
        timeout = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if task.ready():
                break
            time.sleep(0.5)
        
        if task.ready():
            if task.successful():
                result = task.get()
                print("✅ Task completed successfully!")
                print(f"Result: {result}")
                return True
            else:
                print("❌ Task failed!")
                print(f"Error: {task.info}")
                return False
        else:
            print("❌ Task timed out!")
            print(f"Task status: {task.status}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Celery ping: {e}")
        return False

def main():
    """Main function to run the ping test."""
    message = sys.argv[1] if len(sys.argv) > 1 else "pong"
    
    print("Celery Ping Test")
    print("=" * 50)
    
    success = test_celery_ping(message)
    
    print("=" * 50)
    if success:
        print("✅ Ping test PASSED - Worker is functioning correctly")
        sys.exit(0)
    else:
        print("❌ Ping test FAILED - Worker has issues")
        print("\nTroubleshooting tips:")
        print("1. Check if CELERY_BROKER_URL is set correctly")
        print("2. Verify the worker is running: celery -A celery_worker worker --loglevel=info")
        print("3. Check worker logs for connection errors")
        print("4. Ensure Redis/RabbitMQ is running and accessible")
        sys.exit(1)

if __name__ == "__main__":
    main()
