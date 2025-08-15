#!/usr/bin/env python3
"""
Test script to verify ping task registration.
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    # Import the ping task
    from app.tasks.ping import ping_task
    print("✅ Ping task imported successfully")
    
    # Check if it's registered
    from celery_worker import celery
    print("✅ Celery app imported successfully")
    
    # List registered tasks
    tasks = celery.tasks.keys()
    ping_tasks = [t for t in tasks if 'ping' in t.lower()]
    print(f"✅ Found {len(ping_tasks)} ping-related tasks: {ping_tasks}")
    
    if 'ping_task' in tasks:
        print("✅ ping_task is registered with Celery")
    else:
        print("⚠️  ping_task not found in registered tasks")
        print(f"Available tasks: {list(tasks)[:10]}...")  # Show first 10 tasks
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
