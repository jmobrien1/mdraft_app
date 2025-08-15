# Worker Sanity Testing Guide

## Overview

This guide covers how to test Celery worker connectivity and functionality using the ping task system. The ping task is a simple, lightweight way to verify that your Celery workers are functioning correctly.

## Ping Task Features

### **What the Ping Task Tests**

1. **Worker Connectivity**: Verifies the worker can receive tasks from the broker
2. **Task Processing**: Confirms the worker can process and execute tasks
3. **Result Return**: Ensures the worker can return results back to the application
4. **Response Time**: Measures how quickly the worker responds

### **Ping Task Response**

```json
{
    "status": "success",
    "message": "pong",
    "task_id": "uuid-here",
    "timestamp": "2024-01-01T00:00:00Z",
    "worker_id": "worker-1@hostname"
}
```

## Testing Methods

### **1. Command Line Script**

Use the provided ping script for quick testing:

```bash
# Basic ping test
python scripts/ping_celery.py

# Custom message
python scripts/ping_celery.py "hello worker"

# Test with specific message
python scripts/ping_celery.py "test message from $(date)"
```

**Expected Output:**
```
Celery Ping Test
==================================================
Testing Celery ping with message: 'pong'
Broker URL: redis://localhost:6379/0
Timestamp: 2024-01-01T00:00:00Z
--------------------------------------------------
Sending ping task...
Task ID: abc123-def456-ghi789
Waiting for result...
✅ Task completed successfully!
Result: {'status': 'success', 'message': 'pong', 'task_id': '...', 'timestamp': '...', 'worker_id': 'worker-1@hostname'}
==================================================
✅ Ping test PASSED - Worker is functioning correctly
```

### **2. API Endpoint**

Use the REST API for programmatic testing:

```bash
# Test ping via API
curl -X POST http://localhost:5000/api/ops/ping \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"message": "test from API"}'
```

**Response:**
```json
{
    "status": "success",
    "task_id": "abc123-def456-ghi789",
    "result": {
        "status": "success",
        "message": "test from API",
        "task_id": "uuid-here",
        "timestamp": "2024-01-01T00:00:00Z",
        "worker_id": "worker-1@hostname"
    },
    "duration_ms": 45,
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### **3. Python Snippet**

Use this one-off Python snippet for custom testing:

```python
#!/usr/bin/env python3
"""
One-off Celery ping test snippet.
Save this as test_ping.py and run: python test_ping.py
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery_worker import celery

def test_ping():
    print("Testing Celery ping...")
    
    # Send ping task
    task = celery.send_task('ping_task', args=["test from snippet"])
    print(f"Task ID: {task.id}")
    
    # Wait for result
    timeout = 30
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if task.ready():
            break
        time.sleep(0.5)
        print(".", end="", flush=True)
    
    print()  # New line
    
    if task.ready():
        if task.successful():
            result = task.get()
            print(f"✅ Success: {result}")
            return True
        else:
            print(f"❌ Failed: {task.info}")
            return False
    else:
        print("❌ Timeout")
        return False

if __name__ == "__main__":
    success = test_ping()
    sys.exit(0 if success else 1)
```

## Troubleshooting

### **If Ping Task is PENDING Forever**

When the ping task stays in PENDING status, check these diagnostics:

#### **1. Check Broker URL**

```bash
# Check environment variable
echo $CELERY_BROKER_URL

# Should show something like:
# redis://localhost:6379/0
# or
# redis://username:password@host:port/db
```

#### **2. Check Worker Logs**

Look for these messages in worker startup logs:

```
INFO: Initializing Celery with broker: redis://localhost:6379/0
INFO: Result backend: redis://localhost:6379/0
INFO: Testing broker connection: redis://localhost:6379/0
INFO: Broker connection successful
```

**If you see connection errors:**
```
ERROR: Broker connection failed: Connection refused
ERROR: Worker will not function properly without broker connection
```

#### **3. Check Worker Status**

```bash
# Check if worker is running
ps aux | grep celery

# Check worker processes
celery -A celery_worker inspect active

# Check registered tasks
celery -A celery_worker inspect registered
```

#### **4. Test Broker Connection**

```bash
# Test Redis connection directly
redis-cli ping

# Should return: PONG

# Test with full URL
redis-cli -u redis://localhost:6379/0 ping
```

#### **5. Check Configuration**

Use the config endpoint to verify settings:

```bash
curl http://localhost:5000/api/ops/config \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
    "queue_mode": "celery",
    "broker_url": "redis://localhost:6379/0",
    "worker_service": false,
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### **Common Issues and Solutions**

#### **Issue: CELERY_BROKER_URL not set**
```
ERROR: CELERY_BROKER_URL not set
```
**Solution:** Set the environment variable:
```bash
export CELERY_BROKER_URL="redis://localhost:6379/0"
```

#### **Issue: Redis not running**
```
ERROR: Broker connection failed: Connection refused
```
**Solution:** Start Redis:
```bash
# macOS with Homebrew
brew services start redis

# Ubuntu/Debian
sudo systemctl start redis-server

# Docker
docker run -d -p 6379:6379 redis:alpine
```

#### **Issue: Worker not running**
```
❌ Task timed out!
```
**Solution:** Start the worker:
```bash
celery -A celery_worker worker --loglevel=info
```

#### **Issue: Wrong queue configuration**
```
❌ Task failed!
```
**Solution:** Check task routing in `celery_worker.py`:
```python
c.conf.task_routes = {
    'app.celery_tasks.ping_task': {
        'queue': 'mdraft_default',
        'routing_key': 'mdraft_default',
    }
}
```

## Production Monitoring

### **Health Check Integration**

Add ping task to your health check system:

```python
def health_check():
    """Comprehensive health check including Celery."""
    checks = {
        "database": check_database(),
        "celery": check_celery(),
        "storage": check_storage()
    }
    
    return {
        "status": "healthy" if all(checks.values()) else "unhealthy",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }

def check_celery():
    """Check Celery worker health."""
    try:
        from celery_worker import celery
        task = celery.send_task('ping_task', args=["health_check"])
        
        # Wait up to 10 seconds
        if task.get(timeout=10):
            return True
    except Exception:
        pass
    return False
```

### **Automated Testing**

Create a cron job or scheduled task:

```bash
# Add to crontab
*/5 * * * * cd /path/to/mdraft_app && python scripts/ping_celery.py >> /var/log/celery_ping.log 2>&1
```

### **Alerting**

Set up alerts for ping failures:

```python
def alert_celery_failure():
    """Send alert when Celery ping fails."""
    # Send email, Slack, etc.
    pass

# In your monitoring script
if not test_celery_ping():
    alert_celery_failure()
```

## Summary

The ping task system provides:

1. **Quick Testing**: Simple command-line and API testing
2. **Comprehensive Diagnostics**: Detailed error messages and troubleshooting
3. **Production Monitoring**: Integration with health checks and alerting
4. **Idempotent Operations**: Safe to run multiple times
5. **Readable Errors**: User-friendly error messages

Use these tools to ensure your Celery workers are functioning correctly and to quickly diagnose any issues that arise.
