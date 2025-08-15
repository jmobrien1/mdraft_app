# Observability & Guardrails

This document describes the observability and guardrails implemented in the mdraft application.

## Request Logging

### Overview
The application includes concise request logging middleware that logs:
- **Method**: HTTP method (GET, POST, etc.)
- **Path**: Request path
- **Status**: HTTP status code
- **Duration**: Response time in milliseconds
- **Request ID**: Unique identifier for request tracing

### Implementation
- **File**: `app/middleware/logging.py`
- **Lines**: Under 40 lines as requested
- **Registration**: Automatically registered in `app/__init__.py`

### Log Format
```
rid=<request_id> <method> <path> <status> <duration>ms
```

Example:
```
rid=a1b2c3d4 GET /api/convert 200 45ms
```

### Request ID Handling
- Uses existing `X-Request-ID` header if provided
- Generates new UUID if not provided
- Available in `request.environ['X-Request-ID']`

## Health Checks

### `/health` Endpoint
- **Purpose**: Lightweight health check for monitoring systems
- **Response**: `{"status": "ok"}`
- **Database**: Executes lightweight `SELECT 1` query
- **Use Case**: Load balancer health checks, basic monitoring

### `/readyz` Endpoint
- **Purpose**: Comprehensive readiness check
- **Checks**: Database, Redis (if configured), Storage
- **Response**: Detailed status with individual component health
- **Use Case**: Kubernetes readiness probes, deployment verification

### `/healthz` Endpoint
- **Purpose**: Fast health check without external dependencies
- **Response**: Basic service information
- **Use Case**: Quick health verification

## Migration Status

### `/api/ops/migration_status` Endpoint
- **Purpose**: Report database migration status
- **Authentication**: Required (login_required)
- **Response**:
  ```json
  {
    "alembic_head": "revision_id",
    "tables_exist": {
      "proposals": true,
      "conversions": true,
      "users": true,
      "api_keys": true
    },
    "status": "ok",
    "timestamp": "2024-01-01T00:00:00Z"
  }
  ```

### Features
- Reports current Alembic migration head
- Checks existence of expected database tables
- Provides timestamp for monitoring
- Handles errors gracefully

## Error Response Enhancement

### Request ID in API Errors
All API error responses now include a `request_id` field for tracing:

```json
{
  "error": "not_found",
  "detail": "Resource not found",
  "request_id": "a1b2c3d4"
}
```

### Supported Error Types
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 413 Payload Too Large
- 429 Rate Limited
- 500 Internal Server Error
- All other exceptions

### Implementation
- **Middleware**: Automatically adds request_id to error responses
- **Error Handlers**: Include request_id in all API error responses
- **Consistency**: All error responses follow the same format

## Testing

### Test Script
Run the observability test script to verify all features:

```bash
python test_observability.py
```

### Manual Testing
1. **Health Check**: `curl http://localhost:5000/health`
2. **Migration Status**: `curl -H "X-Request-ID: test123" http://localhost:5000/api/ops/migration_status`
3. **Error with Request ID**: `curl http://localhost:5000/api/nonexistent`

## Monitoring Integration

### Log Aggregation
- Structured JSON logging in production
- Request ID correlation across logs
- Duration tracking for performance monitoring

### Health Check Integration
- Load balancer health checks: `/health`
- Kubernetes readiness: `/readyz`
- Database migration monitoring: `/api/ops/migration_status`

### Error Tracking
- Request ID correlation with error logs
- Consistent error response format
- Structured error data for monitoring systems

## Configuration

### Environment Variables
- `LOG_LEVEL`: Logging level (default: INFO)
- `SENTRY_DSN`: Sentry integration for error tracking
- `SENTRY_ENVIRONMENT`: Environment name for Sentry

### Logging Configuration
- **Development**: Human-readable logs
- **Production**: Structured JSON logs with correlation IDs
- **Request Logging**: Always enabled for all requests

## Best Practices

### Request ID Usage
1. Always include `X-Request-ID` header in client requests
2. Use request ID for log correlation
3. Include request ID in error reports

### Health Check Usage
1. Use `/health` for basic health checks
2. Use `/readyz` for comprehensive readiness checks
3. Monitor `/api/ops/migration_status` for database health

### Error Handling
1. Always check for `request_id` in error responses
2. Use request ID for debugging and support
3. Log request ID with all error conditions
