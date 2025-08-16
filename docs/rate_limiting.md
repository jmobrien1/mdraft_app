# Rate Limiting Implementation

This document describes the fine-grained rate limiting system implemented in the mdraft application.

## Overview

The rate limiting system provides protection against abuse by limiting the number of requests that can be made to specific endpoints within a given time period. The system supports multiple authentication methods and provides different limits for different types of users.

## Rate Limit Configuration

### Endpoint Limits

The following rate limits are configured by default:

| Endpoint | Limit | Key Type | Description |
|----------|-------|----------|-------------|
| `/` (index) | 50 per minute | IP address | Public endpoint, IP-based limiting |
| `/auth/login` | 10 per minute | Username + IP | Login attempts, prevents brute force |
| `/upload` | 20 per minute | User/API key/IP | File uploads, different limits for auth vs anonymous |
| `/api/upload` | 20 per minute | User/API key/IP | API uploads, same as web upload |

### Authentication Priority

The rate limiting system uses the following priority order for determining the rate limit key:

1. **Authenticated User ID** - If a user is logged in, their user ID is used
2. **API Key** - If an API key is provided in headers, args, or cookies
3. **IP Address** - Fallback for anonymous users

### Configuration

Rate limits can be configured via environment variables:

```bash
# Index endpoint rate limit
INDEX_RATE_LIMIT="50 per minute"

# Login endpoint rate limit
LOGIN_RATE_LIMIT="10 per minute"

# Upload endpoint rate limits
UPLOAD_RATE_LIMIT="20 per minute"
UPLOAD_ANON_RATE_LIMIT="10 per minute"

# Global rate limit (fallback)
GLOBAL_RATE_LIMIT="120 per minute"
```

## Implementation Details

### Rate Limit Key Functions

The system provides several specialized key functions for different endpoints:

#### `get_rate_limit_key()`
Primary rate limit key function that follows the authentication priority order.

#### `get_login_rate_limit_key()`
Combines username and IP address for login attempts to prevent both targeted attacks and IP-based brute force.

#### `get_upload_rate_limit_key()`
Provides different keys for authenticated users, API key users, and anonymous users.

#### `get_index_rate_limit_key()`
Uses IP address only for the public index endpoint.

### API Key Support

API keys can be provided in multiple ways:

1. **Headers**: `X-API-Key: your-api-key`
2. **Query Parameters**: `?api_key=your-api-key`
3. **Cookies**: `api_key=your-api-key`

Headers take priority over query parameters, which take priority over cookies.

### IP Address Detection

The system supports proxy environments by checking multiple headers:

1. `X-Forwarded-For` - Takes the first IP in the chain
2. `X-Real-IP` - Direct client IP
3. `REMOTE_ADDR` - Fallback to direct connection

## Response Format

When rate limits are exceeded, the system returns a 429 status code with a JSON response:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Please try again later."
}
```

### Rate Limit Headers

All responses include rate limit headers:

- `X-RateLimit-Limit` - Maximum requests allowed
- `X-RateLimit-Remaining` - Remaining requests in current window
- `X-RateLimit-Reset` - Timestamp when the limit resets
- `Retry-After` - Seconds to wait before retrying (on 429)

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
pytest tests/test_rate_limits.py -v
```

### Integration Tests

Run the simple integration test script:

```bash
python test_rate_limits_simple.py [base_url]
```

### Manual Testing

Test rate limiting manually:

```bash
# Test index endpoint (50 per minute)
for i in {1..51}; do curl http://localhost:5000/; done

# Test login endpoint (10 per minute)
for i in {1..11}; do curl -X POST http://localhost:5000/auth/login -d "email=test@example.com&password=wrong"; done

# Test upload endpoint (20 per minute)
for i in {1..21}; do curl -X POST http://localhost:5000/upload -F "file=@test.txt"; done
```

## Security Considerations

### Rate Limit Isolation

- Different users have isolated rate limits
- API keys have their own rate limit buckets
- IP addresses are used as fallback for anonymous users

### Brute Force Protection

- Login attempts are limited per username + IP combination
- This prevents both targeted attacks on specific accounts and IP-based brute force

### API Key Security

- API keys are hashed in logs to prevent exposure
- Rate limits can be customized per API key
- API keys support different limits than web users

### Proxy Support

- Proper IP detection behind proxies
- Support for load balancers and CDNs
- Configurable trusted proxy settings

## Monitoring and Logging

### Rate Limit Events

The system logs rate limit events for monitoring:

```python
# Example log entry
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "WARNING",
  "message": "Rate limit exceeded",
  "rate_limit_key": "user:123",
  "identifier_type": "user_id",
  "client_ip": "192.168.1.1",
  "endpoint": "/upload"
}
```

### Metrics

Key metrics to monitor:

- Rate limit violations per endpoint
- Rate limit violations per user type (authenticated, API key, anonymous)
- Distribution of rate limit keys
- Response times during rate limiting

## Troubleshooting

### Common Issues

1. **Rate limits too strict**: Adjust environment variables
2. **Proxy IP detection**: Configure trusted proxy settings
3. **API key not recognized**: Check header/parameter/cookie format
4. **429 responses in testing**: Reset rate limit storage

### Debugging

Enable debug logging for rate limiting:

```bash
export LOG_LEVEL=DEBUG
```

Check rate limit storage:

```bash
# If using Redis
redis-cli KEYS "*rate_limit*"

# If using memory storage
# Check application logs for rate limit information
```

## Future Enhancements

### Planned Features

1. **Dynamic rate limiting**: Adjust limits based on user behavior
2. **Geographic rate limiting**: Different limits by country/region
3. **Rate limit analytics**: Dashboard for rate limit usage
4. **Custom rate limit rules**: Per-endpoint custom limits
5. **Rate limit bypass**: Whitelist for trusted IPs/users

### Configuration Examples

```python
# Example: Custom rate limits for different user tiers
if user.plan == "premium":
    rate_limit = "100 per minute"
elif user.plan == "basic":
    rate_limit = "50 per minute"
else:
    rate_limit = "20 per minute"

# Example: Geographic rate limiting
if client_country == "US":
    rate_limit = "100 per minute"
else:
    rate_limit = "50 per minute"
```
