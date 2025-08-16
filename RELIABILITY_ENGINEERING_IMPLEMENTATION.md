# Reliability Engineering Implementation

## Overview

This document describes the comprehensive reliability engineering implementation for the mdraft application. The system provides standardized error handling, retries with jittered backoff, circuit breakers, and timeout management for all external service calls.

## Architecture

### Core Components

1. **Reliability Module** (`app/services/reliability.py`)
   - Standardized error types and mapping
   - Circuit breaker implementation
   - Retry decorators with jittered backoff
   - Timeout handling

2. **Configuration** (`app/config.py`)
   - Centralized reliability settings
   - Environment variable support
   - Validation and defaults

3. **Service Integration**
   - LLM Client (`app/services/llm_client.py`)
   - Storage Service (`app/services/storage.py`)
   - Antivirus Service (`app/services/antivirus.py`)

## Configuration

### Environment Variables

```bash
# HTTP timeout and retry settings
HTTP_TIMEOUT_SEC=30          # Default timeout for HTTP calls (seconds)
HTTP_RETRIES=3               # Number of retries for transient failures
HTTP_BACKOFF_BASE_MS=1000    # Base backoff delay (milliseconds)

# Circuit breaker settings
CB_FAIL_THRESHOLD=5          # Failure threshold before opening circuit
CB_RESET_SEC=60              # Circuit reset timeout (seconds)
```

### Configuration Class

```python
@dataclass
class ReliabilityConfig:
    """Reliability engineering configuration for external calls."""
    HTTP_TIMEOUT_SEC: int = 30
    HTTP_RETRIES: int = 3
    HTTP_BACKOFF_BASE_MS: int = 1000
    CB_FAIL_THRESHOLD: int = 5
    CB_RESET_SEC: int = 60
```

## Error Standardization

### Error Types

The system maps all external service errors to standardized types:

```python
class ExternalServiceError(Enum):
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    BAD_REQUEST = "bad_request"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"
```

### Error Mapping

Errors are automatically mapped based on error message content:

```python
def map_external_error(service_name: str, endpoint: str, error: Exception) -> ReliabilityError:
    """Map external service errors to standardized error types."""
    error_str = str(error).lower()
    
    if any(keyword in error_str for keyword in ['timeout', 'timed out', 'deadline']):
        return ReliabilityError(error_type=ExternalServiceError.TIMEOUT, ...)
    # ... additional mappings
```

## Circuit Breaker

### States

1. **CLOSED**: Normal operation, requests pass through
2. **OPEN**: Circuit is open, requests are rejected immediately
3. **HALF_OPEN**: Testing if service has recovered

### Implementation

```python
@dataclass
class CircuitBreaker:
    endpoint: str
    failure_threshold: int
    reset_timeout_sec: int
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)
```

### Behavior

- **Failure Tracking**: Counts consecutive failures
- **Threshold**: Opens circuit after `CB_FAIL_THRESHOLD` failures
- **Reset**: Transitions to half-open after `CB_RESET_SEC` timeout
- **Recovery**: Closes circuit after successful half-open request
- **Thread Safety**: Uses locks for concurrent access

## Retry Logic

### Jittered Exponential Backoff

```python
# Calculate delay with jitter
delay_ms = base_delay_ms * (2 ** (attempt - 1))
jitter_ms = random.randint(0, int(delay_ms * 0.1))  # 10% jitter
total_delay_ms = delay_ms + jitter_ms
```

### Retry Strategy

- **Exponential Backoff**: Base delay doubles with each retry
- **Jitter**: Random component prevents thundering herd
- **Smart Retries**: Don't retry on certain error types (auth, bad request, etc.)
- **Configurable**: Retry count and base delay configurable per service

## Timeout Handling

### Implementation

```python
def with_timeout(timeout_sec: Optional[int] = None) -> Callable:
    """Decorator to add timeout handling to functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout_sec} seconds")
            
            # Set up timeout handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_sec)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Restore original handler and cancel alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    
    return decorator
```

## Service Integration

### LLM Client

```python
def _create_chat_completion(client: OpenAI, params: Dict[str, Any], response_json_hint: bool = True) -> str:
    """Create chat completion with reliability features."""
    def _call_openai():
        # ... OpenAI API call logic
        return resp.choices[0].message.content or ""
    
    # Use resilient_call for automatic retries, timeouts, and circuit breaker
    return resilient_call(
        service_name="openai",
        endpoint="chat.completions",
        func=_call_openai
    )
```

### Storage Service

```python
def _write_bytes_gcs(self, path: str, data: bytes, request_id: str) -> None:
    """Write bytes to GCS with reliability features."""
    def _upload_to_gcs():
        blob = self._gcs_bucket.blob(path)
        # ... upload logic
        return True
    
    # Use resilient_call for automatic retries and circuit breaker
    resilient_call(
        service_name="gcs",
        endpoint="upload",
        func=_upload_to_gcs
    )
```

### Antivirus Service

```python
def _scan_with_clamd(self, file_path: str, config) -> ScanResponse:
    """Scan file using ClamAV daemon with reliability features."""
    def _clamd_scan():
        # ... ClamAV scan logic
        return ScanResponse(result=ScanResult.CLEAN)
    
    # Use resilient_call for automatic retries and circuit breaker
    return resilient_call(
        service_name="clamav",
        endpoint="scan",
        func=_clamd_scan,
        timeout_sec=config.AV_TIMEOUT_MS / 1000.0
    )
```

## Usage Examples

### Basic Usage

```python
from app.services.reliability import resilient_call

def call_external_api():
    return resilient_call(
        service_name="external_api",
        endpoint="data",
        func=make_api_call,
        timeout_sec=30,
        max_retries=3
    )
```

### Custom Retry Decorator

```python
from app.services.reliability import create_retry_decorator

@create_retry_decorator("my_service", "my_endpoint", max_retries=5)
def my_function():
    # Function with automatic retry and circuit breaker
    pass
```

### Error Handling

```python
from app.services.reliability import ReliabilityError, ExternalServiceError

try:
    result = resilient_call("service", "endpoint", func)
except ReliabilityError as e:
    if e.error_type == ExternalServiceError.TIMEOUT:
        # Handle timeout
        pass
    elif e.error_type == ExternalServiceError.RATE_LIMIT:
        # Handle rate limit
        pass
    else:
        # Handle other errors
        pass
```

## Testing

### Unit Tests

Comprehensive test suite in `tests/test_resilience.py`:

- Error mapping tests
- Circuit breaker state transitions
- Retry logic with jitter
- Timeout handling
- Thread safety
- Integration tests

### Smoke Tests

Quick validation script `test_reliability_smoke.py`:

```bash
python test_reliability_smoke.py
```

### Running Tests

```bash
# Run all reliability tests
pytest tests/test_resilience.py -v

# Run specific test class
pytest tests/test_resilience.py::TestCircuitBreaker -v

# Run with coverage
pytest tests/test_resilience.py --cov=app.services.reliability
```

## Monitoring and Observability

### Logging

The system provides comprehensive logging:

```python
logger.warning(f"Retrying {service_name} ({endpoint}) attempt {attempt}/{max_retries}")
logger.error(f"All retries exhausted for {service_name} ({endpoint})")
logger.info(f"Circuit breaker {endpoint}: transitioning to HALF_OPEN")
```

### Metrics

Key metrics to monitor:

- Circuit breaker state transitions
- Retry counts and success rates
- Timeout frequencies
- Error type distributions
- Service response times

### Alerting

Recommended alerts:

- Circuit breaker opens frequently
- High retry rates
- Excessive timeouts
- Service degradation patterns

## Best Practices

### Configuration

1. **Start Conservative**: Use lower retry counts and shorter timeouts initially
2. **Monitor and Adjust**: Tune based on production metrics
3. **Service-Specific Settings**: Different services may need different configurations
4. **Environment-Specific**: Different settings for dev/staging/production

### Error Handling

1. **Don't Retry Everything**: Some errors (auth, bad request) should fail fast
2. **Log Appropriately**: Different log levels for different error types
3. **User-Friendly Messages**: Don't expose internal error details to users
4. **Graceful Degradation**: Provide fallback behavior when possible

### Circuit Breaker Tuning

1. **Failure Threshold**: Start with 5-10 failures
2. **Reset Timeout**: Start with 60 seconds, adjust based on service recovery time
3. **Monitor State Changes**: Track how often circuits open/close
4. **Service-Specific**: Different services may need different thresholds

## Dependencies

### Required Packages

```txt
tenacity==9.0.1  # Retry library with exponential backoff
```

### Optional Dependencies

The system gracefully handles missing tenacity:

```python
try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    # Fallback implementation
```

## Migration Guide

### From Manual Error Handling

**Before:**
```python
try:
    result = external_api_call()
except requests.exceptions.Timeout:
    # Handle timeout
except requests.exceptions.ConnectionError:
    # Handle connection error
except Exception as e:
    # Handle other errors
```

**After:**
```python
try:
    result = resilient_call("external_api", "endpoint", external_api_call)
except ReliabilityError as e:
    # Handle standardized error
```

### From Manual Retries

**Before:**
```python
for attempt in range(3):
    try:
        result = api_call()
        break
    except Exception as e:
        if attempt == 2:
            raise
        time.sleep(2 ** attempt)
```

**After:**
```python
result = resilient_call("api", "endpoint", api_call, max_retries=3)
```

## Troubleshooting

### Common Issues

1. **Circuit Breaker Stuck Open**
   - Check reset timeout configuration
   - Verify service is actually recovering
   - Monitor failure patterns

2. **Excessive Retries**
   - Review retry configuration
   - Check if errors are retryable
   - Monitor service health

3. **Timeout Issues**
   - Adjust timeout values
   - Check network connectivity
   - Monitor service response times

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('app.services.reliability').setLevel(logging.DEBUG)
```

### Circuit Breaker Status

Check circuit breaker status:

```python
from app.services.reliability import get_circuit_breaker_manager

manager = get_circuit_breaker_manager()
breaker = manager.get_breaker("endpoint")
print(f"State: {breaker.state}, Failures: {breaker.failure_count}")
```

## Future Enhancements

### Planned Features

1. **Distributed Circuit Breakers**: Redis-based circuit breakers for multi-instance deployments
2. **Advanced Retry Strategies**: Custom retry policies per service
3. **Metrics Integration**: Prometheus/StatsD metrics
4. **Health Checks**: Automatic service health monitoring
5. **Rate Limiting**: Built-in rate limiting per service

### Configuration Management

1. **Dynamic Configuration**: Runtime configuration updates
2. **Service Discovery**: Automatic endpoint discovery
3. **A/B Testing**: Different reliability settings for traffic splitting

## Conclusion

This reliability engineering implementation provides a robust foundation for handling external service dependencies. The standardized approach ensures consistent behavior across all services while providing the flexibility to tune settings per service and environment.

The system is designed to be:
- **Production Ready**: Comprehensive error handling and monitoring
- **Configurable**: Environment-specific settings
- **Testable**: Extensive test coverage
- **Maintainable**: Clear separation of concerns
- **Extensible**: Easy to add new services and features

By implementing these reliability patterns, the application becomes more resilient to external service failures and provides a better user experience during partial outages.
