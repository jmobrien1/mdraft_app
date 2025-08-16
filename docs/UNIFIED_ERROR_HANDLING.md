# Unified Error Handling System

## Overview

The mdraft application implements a comprehensive, unified error handling system that provides:

- **Safe JSON responses** - No tracebacks or sensitive information exposed
- **Request correlation** - Every error includes a request ID for debugging
- **Structured logging** - JSON-formatted logs with context
- **Sentry integration** - Automatic exception capture when configured
- **Consistent error codes** - Standardized error naming convention

## Architecture

### Error Handler Blueprint

The error handling is implemented in `app/api/errors.py` as a Flask blueprint that registers application-wide error handlers. This approach provides:

- **Centralized error handling** - All error logic in one place
- **Blueprint isolation** - Error handlers don't interfere with other blueprints
- **Easy testing** - Error handlers can be tested independently

### Request ID Middleware

Request IDs are automatically generated and attached to every request via middleware in `app/__init__.py`:

```python
@app.before_request
def _set_request_id():
    """Set request ID for logging and tracing."""
    import uuid
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    request.environ['X-Request-ID'] = request_id
    request.environ['HTTP_X_REQUEST_ID'] = request_id
```

## Error Response Format

All API error responses follow this consistent JSON structure:

```json
{
  "error": "error_code",
  "detail": "Human-readable error description",
  "request_id": "unique-request-identifier"
}
```

### Error Codes

The system maps HTTP exception names to standardized error codes:

| HTTP Exception | Error Code | Status |
|----------------|------------|--------|
| BadRequest | `bad_request` | 400 |
| Unauthorized | `unauthorized` | 401 |
| Forbidden | `forbidden` | 403 |
| NotFound | `not_found` | 404 |
| MethodNotAllowed | `method_not_allowed` | 405 |
| RequestEntityTooLarge | `payload_too_large` | 413 |
| TooManyRequests | `rate_limited` | 429 |
| InternalServerError | `internal_error` | 500 |

## Structured Logging

Every error is logged with structured JSON data:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "ERROR",
  "message": "Error occurred",
  "path": "/api/convert",
  "status": 400,
  "request_id": "abc123-def456",
  "user_id": "123",
  "error": "bad_request",
  "detail": "Invalid file format",
  "exception_type": "BadRequest",
  "logger": "app.api.errors"
}
```

### Log Context

The logging system captures:

- **Request path** - The endpoint that caused the error
- **HTTP status** - The response status code
- **Request ID** - For correlation across logs
- **User ID** - If user is authenticated
- **Error details** - Specific error information
- **Exception type** - The Python exception class

## Sentry Integration

When `SENTRY_DSN` environment variable is set, exceptions are automatically captured in Sentry with:

- **Request context** - URL, method, headers
- **User context** - User ID if authenticated
- **Request ID** - For correlation with logs
- **Full exception details** - Stack traces and context

### Sentry Configuration

Sentry is configured in `app/__init__.py`:

```python
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        environment=sentry_env,
        release=sentry_release,
        traces_sample_rate=0.10,
    )
```

## Usage Examples

### API Routes

API routes automatically get JSON error responses:

```python
@app.route('/api/convert')
def convert_document():
    if not request.files:
        raise BadRequest("No file provided")
    
    # ... processing logic
```

**Response for missing file:**
```json
{
  "error": "bad_request",
  "detail": "No file provided",
  "request_id": "abc123-def456"
}
```

### UI Routes

UI routes continue to use Flask's default HTML error handling:

```python
@app.route('/dashboard')
def dashboard():
    if not current_user.is_authenticated:
        raise Unauthorized("Login required")
    
    # ... dashboard logic
```

**Response:** HTML error page (not JSON)

## Testing

### Unit Tests

The error handling system includes comprehensive unit tests in `tests/test_errors.py`:

```bash
python3 -m pytest tests/test_errors.py -v
```

Tests cover:
- Error response format validation
- Request ID preservation
- Sentry integration
- Structured logging
- Helper function behavior

### Smoke Tests

Run the smoke test to verify error handling in the running application:

```bash
python3 test_error_handling_smoke.py [base_url]
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SENTRY_DSN` | Sentry DSN for exception tracking | None |
| `SENTRY_ENVIRONMENT` | Environment name for Sentry | "production" |
| `SENTRY_RELEASE` | Release version for Sentry | None |

### Logging Configuration

Error logging uses the application's structured logging configuration:

- **Development**: Human-readable logs
- **Production**: JSON-formatted logs with correlation IDs

## Security Considerations

### Information Disclosure

The error handling system is designed to prevent information disclosure:

- **No tracebacks** - Stack traces are never returned to clients
- **Safe error messages** - Generic messages for internal errors
- **Request ID correlation** - Debugging without exposing internals

### Rate Limiting

Rate limit errors (429) are handled consistently:

```json
{
  "error": "rate_limited",
  "detail": "Rate limit exceeded",
  "request_id": "abc123-def456"
}
```

## Monitoring and Debugging

### Request Correlation

Use the `request_id` to correlate errors across:

- Application logs
- Sentry events
- Client requests
- Database queries

### Error Tracking

Monitor error patterns using:

- **Sentry dashboards** - Exception frequency and trends
- **Log aggregation** - Error rates and patterns
- **Request ID tracing** - End-to-end request debugging

## Migration from Old System

The new error handling system replaces the global error handlers in `app/__init__.py`:

### Before (Old System)
```python
@app.errorhandler(Exception)
def _json_errors(e):
    # Global error handler with basic logging
```

### After (New System)
```python
# Blueprint-based error handling with:
# - Structured logging
# - Sentry integration
# - Request correlation
# - Safe error responses
```

## Best Practices

### For Developers

1. **Raise appropriate exceptions** - Use Werkzeug HTTPExceptions
2. **Provide meaningful error messages** - Help users understand the issue
3. **Test error scenarios** - Ensure error handling works correctly
4. **Monitor error rates** - Track application health

### For Operations

1. **Configure Sentry** - Set up proper DSN and environment
2. **Monitor logs** - Watch for error patterns
3. **Set up alerts** - Notify on high error rates
4. **Use request IDs** - Correlate issues across systems

## Troubleshooting

### Common Issues

1. **Missing request IDs** - Check middleware registration
2. **Sentry not capturing** - Verify DSN configuration
3. **Inconsistent error format** - Ensure blueprint is registered
4. **Log correlation issues** - Check structured logging setup

### Debug Commands

```bash
# Test error handling
python3 -m pytest tests/test_errors.py -v

# Smoke test running application
python3 test_error_handling_smoke.py

# Check logs for request correlation
grep "request_id" logs/app.log
```
