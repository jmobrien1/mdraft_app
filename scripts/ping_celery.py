#!/usr/bin/env python3
"""
Celery worker health check script.

This script sends a ping task to the Celery worker and monitors its status.
Useful for debugging worker connectivity issues.
"""
import os
import time
from celery import Celery


def ping_celery_worker():
    """Send a ping task and monitor its status."""
    # Get Celery configuration from environment
    broker_url = os.environ.get('CELERY_BROKER_URL')
    backend_url = os.environ.get('CELERY_RESULT_BACKEND')
    
    if not broker_url:
        print("ERROR: CELERY_BROKER_URL environment variable not set")
        return False
    
    print(f"Broker URL: {broker_url}")
    if backend_url:
        print(f"Result Backend: {backend_url}")
    else:
        print("Result Backend: Using broker as backend")
    
    # Create Celery app
    app = Celery(
        broker=broker_url, 
        backend=backend_url or broker_url
    )
    
    # Send ping task
    print("\nSending ping task...")
    try:
        result = app.send_task('ping_task')
        print(f"Task ID: {result.id}")
    except Exception as e:
        print(f"ERROR: Failed to send task: {e}")
        return False
    
    # Monitor task status
    print("\nMonitoring task status...")
    for i in range(20):
        try:
            status = result.status
            print(f"Status ({i+1}/20): {status}")
            
            if status in ("SUCCESS", "FAILURE"):
                print(f"Final result: {result.result}")
                return status == "SUCCESS"
            
            time.sleep(1)
        except Exception as e:
            print(f"ERROR: Failed to check status: {e}")
            return False
    
    print("WARNING: Task still pending after 20 seconds")
    return False


if __name__ == "__main__":
    success = ping_celery_worker()
    if success:
        print("\n✅ Worker is healthy!")
    else:
        print("\n❌ Worker health check failed")
        print("\nPossible issues:")
        print("- Worker not connected to broker")
        print("- Check CELERY_BROKER_URL configuration")
        print("- Check Render worker logs")
        print("- Verify Redis/Redis Cloud connectivity")
