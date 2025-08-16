# Structured JSON Logging with Correlation IDs

## Overview

This document describes the comprehensive structured JSON logging system implemented for the mdraft application. The system provides observability through correlation IDs, request tracking, and Celery task integration for production debugging and monitoring.

## Key Features

- **Structured JSON Logs**: All logs are formatted as JSON for easy parsing and analysis
- **Correlation IDs**: Request ID, User ID, Task ID, Job ID, and Conversion ID tracking
- **Request Timing**: Automatic duration tracking for all HTTP requests
- **Celery Integration**: Task ID and retry information for background jobs
- **Cloud Tasks Support**: Integration with Google Cloud Tasks headers
- **Context Variables**: Thread-safe correlation ID management using Python's `contextvars`

## Architecture

### Core Components

1. **StructuredJSONFormatter**: JSON log formatter with correlation ID support
2. **RequestLogger**: Flask middleware for request tracking
3. **CeleryTaskLogger**: Celery task logging utilities
4. **Context Variables**: Thread-safe correlation ID storage

### Correlation IDs

The system tracks the following correlation IDs:

- `request_id`: Unique identifier for each HTTP request
- `user_id`: Database user ID (when authenticated)
- `task_id`: Celery task identifier
- `job_id`: Document conversion job ID
- `conversion_id`: Document conversion ID

## Implementation

### 1. Logging Setup

The structured logging is initialized in `app/__init__.py`:

```python
from .utils.logging import setup_logging

# Initialize structured logging
setup_logging(app, log_level=level)
```

### 2. Request Logging

Every HTTP request automatically generates structured logs:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "mdraft",
  "message": "",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123",
  "event": "request_started",
  "method": "POST",
  "path": "/api/convert",
  "remote_addr": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

### 3. Celery Task Logging

Celery tasks include task-specific correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "mdraft",
  "message": "",
  "task_id": "conv-task-456",
  "conversion_id": "conv-789",
  "user_id": "123",
  "celery_task_id": "celery-task-abc",
  "celery_task_name": "convert_document",
  "celery_retries": 0,
  "event": "conversion_task_started",
  "gcs_uri": "gs://bucket/document.pdf"
}
```

### 4. Cloud Tasks Integration

Cloud Tasks requests include additional headers:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "mdraft",
  "message": "",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "projects/myproject/locations/us-central1/queues/mdraft-queue/tasks/task-123",
  "cloud_task_name": "task-123",
  "cloud_queue_name": "mdraft-conversion-queue",
  "cloud_execution_count": "1",
  "event": "cloud_tasks_request_received",
  "queue_name": "mdraft-conversion-queue"
}
```

## Usage Examples

### 1. Basic Logging

```python
from app.utils.logging import log_with_context

# Log with correlation IDs
log_with_context(
    level="INFO",
    event="user_action",
    action="document_upload",
    filename="report.pdf"
)
```

### 2. Setting Correlation IDs

```python
from app.utils.logging import set_correlation_id, get_correlation_ids

# Set correlation IDs
set_correlation_id("user_id", "123")
set_correlation_id("job_id", "456")

# Get all correlation IDs
ids = get_correlation_ids()
print(ids)  # {'request_id': '...', 'user_id': '123', 'job_id': '456', ...}
```

### 3. Celery Task Logging

```python
from app.utils.logging import CeleryTaskLogger
import time

def my_celery_task():
    start_time = time.time()
    task_id = str(uuid.uuid4())
    
    # Set up task logging
    CeleryTaskLogger.setup_task_logging(task_id, task_type="custom")
    
    try:
        # Task processing...
        result = process_data()
        
        duration_ms = int((time.time() - start_time) * 1000)
        CeleryTaskLogger.log_task_completion(task_id, True, duration_ms)
        
        return result
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        CeleryTaskLogger.log_task_completion(task_id, False, duration_ms, error=str(e))
        raise
```

### 4. Database Operation Logging

```python
from app.utils.logging import log_database_operation
import time

def query_database():
    start_time = time.time()
    
    # Execute query
    result = db.session.execute("SELECT * FROM users")
    
    duration_ms = int((time.time() - start_time) * 1000)
    log_database_operation(
        operation="SELECT",
        table="users",
        duration_ms=duration_ms,
        rows_returned=len(result)
    )
```

### 5. Conversion Event Logging

```python
from app.utils.logging import log_conversion_event

# Log conversion lifecycle
log_conversion_event("started", conversion_id="conv-123", user_id="456")
log_conversion_event("processing", conversion_id="conv-123", progress=50)
log_conversion_event("completed", conversion_id="conv-123", markdown_length=1500)
```

## Log Analysis

### 1. Request Tracing

To trace a request through the system:

```bash
# Find all logs for a specific request
grep '"request_id": "550e8400-e29b-41d4-a716-446655440000"' logs.json

# Find all logs for a specific user
grep '"user_id": "123"' logs.json

# Find all logs for a specific conversion
grep '"conversion_id": "conv-789"' logs.json
```

### 2. Performance Analysis

```bash
# Find slow requests (>1 second)
grep '"duration_ms": [0-9]\{4,\}' logs.json

# Find failed requests
grep '"status_code": [4-5][0-9][0-9]' logs.json

# Find Celery task failures
grep '"event": "celery_task_failed"' logs.json
```

### 3. Error Analysis

```bash
# Find all errors
grep '"level": "ERROR"' logs.json

# Find specific error types
grep '"exception_type": "ValueError"' logs.json

# Find database errors
grep '"event": "database_operation_error"' logs.json
```

## Configuration

### Environment Variables

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `SENTRY_DSN`: Sentry integration for error tracking
- `SENTRY_ENVIRONMENT`: Environment name for Sentry

### Log Format

All logs follow this JSON structure:

```json
{
  "timestamp": "ISO 8601 timestamp",
  "level": "log level",
  "logger": "logger name",
  "message": "log message",
  "request_id": "correlation ID",
  "user_id": "user ID",
  "task_id": "task ID",
  "job_id": "job ID",
  "conversion_id": "conversion ID",
  "event": "event type",
  "duration_ms": "timing in milliseconds",
  "extra_fields": "additional context"
}
```

## Testing

Run the test script to see structured logging in action:

```bash
python test_structured_logging.py
```

This will generate sample JSON logs demonstrating all features.

## Monitoring and Alerting

### 1. Log Aggregation

Configure your log aggregation system (e.g., Google Cloud Logging, ELK Stack) to parse the JSON logs.

### 2. Metrics Extraction

Extract metrics from structured logs:

- Request duration percentiles
- Error rates by endpoint
- Celery task success rates
- Database operation performance

### 3. Alerting Rules

Set up alerts for:

- High error rates (>5%)
- Slow requests (>5 seconds)
- Celery task failures
- Database connection issues

## Best Practices

### 1. Correlation ID Propagation

Always propagate correlation IDs across service boundaries:

```python
# In HTTP headers
headers = {
    'X-Request-ID': request_id,
    'X-Job-ID': job_id
}

# In Celery task parameters
task.delay(param1, param2, request_id=request_id)
```

### 2. Consistent Event Names

Use consistent event naming conventions:

- `request_started` / `request_completed`
- `task_started` / `task_completed` / `task_failed`
- `conversion_started` / `conversion_completed`
- `database_operation`

### 3. Sensitive Data

Never log sensitive information:

```python
# Good
log_with_context(event="user_login", user_id="123")

# Bad
log_with_context(event="user_login", password="secret123")
```

### 4. Performance Impact

The logging system is designed to be lightweight:

- Context variables are thread-safe and fast
- JSON serialization is optimized
- Log levels can be adjusted for performance

## Troubleshooting

### 1. Missing Correlation IDs

If correlation IDs are missing:

1. Check that `set_correlation_id()` is called
2. Verify context variables are set in the correct thread
3. Ensure Flask request context is available

### 2. Duplicate Logs

If you see duplicate logs:

1. Check logger configuration in `setup_logging()`
2. Verify `app.logger.propagate = False`
3. Remove duplicate handlers

### 3. Performance Issues

If logging impacts performance:

1. Increase log level to WARNING or ERROR
2. Use async logging for high-volume operations
3. Consider log sampling for high-traffic endpoints

## Future Enhancements

1. **Distributed Tracing**: Integration with OpenTelemetry
2. **Log Sampling**: Configurable sampling rates
3. **Custom Metrics**: Prometheus metrics extraction
4. **Log Compression**: Automatic log rotation and compression
5. **Real-time Monitoring**: WebSocket-based log streaming
