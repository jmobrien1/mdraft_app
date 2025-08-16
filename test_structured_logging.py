#!/usr/bin/env python3
"""
Test script for structured JSON logging with correlation IDs.

This script demonstrates the structured logging system by simulating
various application scenarios including HTTP requests, Celery tasks,
and database operations.
"""
import json
import logging
import time
import uuid
from datetime import datetime
from unittest.mock import Mock, patch

# Mock Flask context
class MockRequest:
    def __init__(self, method="GET", path="/api/test", headers=None):
        self.method = method
        self.path = path
        self.remote_addr = "127.0.0.1"
        self.headers = headers or {}
        self.environ = {}

class MockResponse:
    def __init__(self, status_code=200, content_length=100):
        self.status_code = status_code
        self.content_length = content_length

# Mock Celery context
class MockCeleryTask:
    def __init__(self, task_id="test-task-123", name="test_task", retries=0):
        self.request = Mock()
        self.request.id = task_id
        self.request.retries = retries
        self.name = name

def test_request_logging():
    """Test HTTP request logging with correlation IDs."""
    print("=== Testing HTTP Request Logging ===")
    
    # Import after setting up mocks
    from app.utils.logging import log_with_context, set_correlation_id, get_correlation_ids
    
    # Simulate request context
    request_id = str(uuid.uuid4())
    user_id = "123"
    
    set_correlation_id("request_id", request_id)
    set_correlation_id("user_id", user_id)
    
    # Log request start
    log_with_context(
        level="INFO",
        event="request_started",
        method="POST",
        path="/api/convert",
        remote_addr="192.168.1.100"
    )
    
    # Simulate processing time
    time.sleep(0.1)
    
    # Log request completion
    log_with_context(
        level="INFO",
        event="request_completed",
        method="POST",
        path="/api/convert",
        status_code=200,
        duration_ms=150,
        content_length=2048
    )
    
    print(f"Request correlation IDs: {get_correlation_ids()}")

def test_celery_task_logging():
    """Test Celery task logging with correlation IDs."""
    print("\n=== Testing Celery Task Logging ===")
    
    from app.utils.logging import CeleryTaskLogger, log_with_context
    
    # Simulate Celery task
    task_id = str(uuid.uuid4())
    conversion_id = "conv-456"
    user_id = "789"
    
    # Set up task logging context
    CeleryTaskLogger.setup_task_logging(
        task_id,
        conversion_id=conversion_id,
        user_id=user_id,
        gcs_uri="gs://bucket/document.pdf"
    )
    
    # Simulate task processing
    time.sleep(0.2)
    
    # Log task completion
    CeleryTaskLogger.log_task_completion(
        task_id,
        success=True,
        duration_ms=250,
        conversion_id=conversion_id,
        markdown_length=1500
    )

def test_database_operations():
    """Test database operation logging."""
    print("\n=== Testing Database Operation Logging ===")
    
    from app.utils.logging import log_database_operation, set_correlation_id
    
    # Set correlation IDs
    request_id = str(uuid.uuid4())
    set_correlation_id("request_id", request_id)
    
    # Simulate database operations
    log_database_operation(
        operation="SELECT",
        table="conversions",
        duration_ms=45,
        rows_returned=1
    )
    
    log_database_operation(
        operation="UPDATE",
        table="conversions",
        duration_ms=23,
        rows_affected=1
    )

def test_conversion_events():
    """Test conversion event logging."""
    print("\n=== Testing Conversion Event Logging ===")
    
    from app.utils.logging import log_conversion_event, set_correlation_id
    
    conversion_id = "conv-789"
    set_correlation_id("conversion_id", conversion_id)
    
    # Log conversion events
    log_conversion_event(conversion_id, "started", user_id="123", gcs_uri="gs://bucket/doc.pdf")
    time.sleep(0.1)
    log_conversion_event(conversion_id, "processing", progress=50)
    time.sleep(0.1)
    log_conversion_event(conversion_id, "completed", markdown_length=2000, duration_ms=300)

def test_job_events():
    """Test job event logging."""
    print("\n=== Testing Job Event Logging ===")
    
    from app.utils.logging import log_job_event, set_correlation_id
    
    job_id = "job-101"
    set_correlation_id("job_id", job_id)
    
    # Log job events
    log_job_event(job_id, "created", user_id="123", filename="document.pdf")
    time.sleep(0.1)
    log_job_event(job_id, "queued", queue_name="mdraft_default")
    time.sleep(0.1)
    log_job_event(job_id, "processing", worker_id="worker-1")
    time.sleep(0.1)
    log_job_event(job_id, "completed", duration_ms=500, output_size=2048)

def test_error_logging():
    """Test error logging with correlation IDs."""
    print("\n=== Testing Error Logging ===")
    
    from app.utils.logging import log_with_context, set_correlation_id
    
    request_id = str(uuid.uuid4())
    set_correlation_id("request_id", request_id)
    
    try:
        # Simulate an error
        raise ValueError("Test error for logging")
    except Exception as e:
        log_with_context(
            level="ERROR",
            event="processing_error",
            error=str(e),
            exception_type=type(e).__name__,
            stack_trace="traceback info here"
        )

def test_cloud_tasks_logging():
    """Test Cloud Tasks specific logging."""
    print("\n=== Testing Cloud Tasks Logging ===")
    
    from app.utils.logging import log_with_context, set_correlation_id
    
    # Simulate Cloud Tasks headers
    task_id = "projects/myproject/locations/us-central1/queues/mdraft-queue/tasks/task-123"
    set_correlation_id("task_id", task_id)
    
    log_with_context(
        level="INFO",
        event="cloud_tasks_request_received",
        queue_name="mdraft-conversion-queue",
        task_name=task_id,
        execution_count=1,
        job_id="456",
        user_id="789"
    )

def main():
    """Run all logging tests."""
    print("Structured JSON Logging Test Suite")
    print("=" * 50)
    
    # Configure logging to output to console
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'  # Raw JSON output
    )
    
    # Run tests
    test_request_logging()
    test_celery_task_logging()
    test_database_operations()
    test_conversion_events()
    test_job_events()
    test_error_logging()
    test_cloud_tasks_logging()
    
    print("\n" + "=" * 50)
    print("All tests completed. Check the JSON log output above.")
    print("Each log line should contain correlation IDs and structured data.")

if __name__ == "__main__":
    main()
