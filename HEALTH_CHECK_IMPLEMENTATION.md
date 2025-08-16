# Health Check Implementation

This document describes the comprehensive health check implementation for the mdraft application, providing liveness and readiness probes with detailed dependency monitoring.

## Overview

The health check system provides three endpoints:

- **`/healthz`** - Liveness probe (fast, minimal checks)
- **`/readyz`** - Readiness probe (comprehensive dependency checks)
- **`/health`** - Legacy health endpoint (lightweight database check)

## Endpoints

### `/healthz` - Liveness Probe

**Purpose**: Fast health check for Kubernetes liveness probes
**Response Time**: < 1ms
**Status Codes**: 200 (always healthy)

```json
{
  "status": "healthy",
  "service": "mdraft",
  "version": "1.0.0",
  "timestamp": 1703123456.789
}
```

**Usage**:
- Kubernetes liveness probes
- Load balancer health checks
- Quick application status verification

### `/readyz` - Readiness Probe

**Purpose**: Comprehensive dependency health check for Kubernetes readiness probes
**Response Time**: 1-8 seconds (depending on dependency response times)
**Status Codes**: 200 (ready), 503 (not ready)

**Dependencies Checked**:
1. **Database** - `SELECT 1` query (2s timeout)
2. **Redis** - Ping command (1s timeout, optional)
3. **Celery** - Worker inspect ping (3s timeout)
4. **Storage** - GCS bucket or local filesystem access (2s timeout)

**Success Response**:
```json
{
  "status": "ready",
  "service": "mdraft",
  "version": "1.0.0",
  "timestamp": 1703123456.789,
  "duration_ms": 125.5,
  "checks": {
    "database": {
      "status": "healthy",
      "duration_ms": 15.5,
      "error": null
    },
    "redis": {
      "status": "healthy",
      "duration_ms": 8.2,
      "error": null
    },
    "celery": {
      "status": "healthy",
      "duration_ms": 45.1,
      "error": null,
      "active_workers": 2
    },
    "storage": {
      "status": "healthy",
      "duration_ms": 12.3,
      "error": null,
      "storage_type": "gcs"
    }
  }
}
```

**Failure Response**:
```json
{
  "status": "not_ready",
  "service": "mdraft",
  "version": "1.0.0",
  "timestamp": 1703123456.789,
  "duration_ms": 2000.0,
  "message": "Health checks failed: database, celery",
  "failed_checks": ["database", "celery"],
  "checks": {
    "database": {
      "status": "unhealthy",
      "duration_ms": 2000.0,
      "error": "Database query timed out"
    },
    "redis": {
      "status": "healthy",
      "duration_ms": 8.2,
      "error": null
    },
    "celery": {
      "status": "unhealthy",
      "duration_ms": 3000.0,
      "error": "No active Celery workers found"
    },
    "storage": {
      "status": "healthy",
      "duration_ms": 12.3,
      "error": null,
      "storage_type": "gcs"
    }
  }
}
```

**Usage**:
- Kubernetes readiness probes
- Load balancer traffic routing decisions
- Application dependency monitoring
- Incident response and debugging

### `/health` - Legacy Health Endpoint

**Purpose**: Lightweight database health check for existing monitoring systems
**Response Time**: < 2 seconds
**Status Codes**: 200 (ok), 503 (database_error)

**Success Response**:
```json
{
  "status": "ok"
}
```

**Failure Response**:
```json
{
  "status": "database_error",
  "error": "Database connection failed"
}
```

## Dependency Checks

### Database Check

- **Query**: `SELECT 1`
- **Timeout**: 2 seconds
- **Thread**: Executed in separate thread with timeout
- **Status**: Required for application functionality

### Redis Check

- **Command**: `PING`
- **Timeout**: 1 second
- **Thread**: Executed in separate thread with timeout
- **Status**: Optional (healthy if not configured)
- **Note**: Returns `"note": "Redis not configured"` when Redis is not set up

### Celery Check

- **Command**: `celery.control.inspect().ping()`
- **Timeout**: 3 seconds
- **Thread**: Executed in separate thread with timeout
- **Status**: Required for background task processing
- **Metadata**: Returns `active_workers` count

### Storage Check

- **GCS**: Lists objects with prefix `health/` (2s timeout)
- **Local**: Minimal storage object creation check
- **Timeout**: 2 seconds
- **Thread**: Executed in separate thread with timeout
- **Status**: Required for file operations
- **Metadata**: Returns `storage_type` ("gcs" or "local")

## Implementation Details

### Timeout Handling

All dependency checks use `ThreadPoolExecutor` with bounded timeouts to prevent hanging:

```python
with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(check_function)
    future.result(timeout=timeout_seconds)
```

### Error Handling

- **Timeouts**: Return `"error": "Component timed out"`
- **Exceptions**: Return `"error": str(exception)`
- **Graceful Degradation**: Individual check failures don't crash the endpoint

### Performance

- **Liveness**: < 1ms response time
- **Readiness**: 1-8 seconds (parallel dependency checks)
- **Legacy**: < 2 seconds (database only)

## Configuration

### Environment Variables

- `USE_GCS`: Enable GCS storage checks (default: False)
- `CELERY_BROKER_URL`: Celery broker URL for worker checks
- `REDIS_URL`: Redis URL for session storage and health checks

### Timeout Configuration

Timeouts are hardcoded for reliability:

- Database: 2 seconds
- Redis: 1 second  
- Celery: 3 seconds
- Storage: 2 seconds

## Kubernetes Integration

### Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 5000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /readyz
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 10
  failureThreshold: 3
```

## Monitoring and Alerting

### Metrics to Monitor

1. **Response Times**:
   - `/healthz` duration (should be < 10ms)
   - `/readyz` duration (should be < 10s)
   - Individual dependency check durations

2. **Failure Rates**:
   - 503 responses from `/readyz`
   - Individual dependency failure rates

3. **Dependency Health**:
   - Database connectivity
   - Redis availability
   - Celery worker count
   - Storage access

### Alerting Rules

```yaml
# High readiness probe failure rate
- alert: HighReadinessProbeFailureRate
  expr: rate(http_requests_total{status="503", path="/readyz"}[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High readiness probe failure rate"

# Database health check failures
- alert: DatabaseHealthCheckFailure
  expr: rate(health_check_duration_seconds{component="database", status="unhealthy"}[5m]) > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Database health check failing"
```

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
python3 -m pytest tests/test_health.py -v
```

### Smoke Tests

Test endpoints in a running environment:

```bash
python3 test_health_smoke.py
python3 test_health_smoke.py http://your-app-url
```

### Manual Testing

```bash
# Test liveness
curl -s http://localhost:5000/healthz | jq

# Test readiness
curl -s http://localhost:5000/readyz | jq

# Test legacy health
curl -s http://localhost:5000/health | jq
```

## Troubleshooting

### Common Issues

1. **Database Timeouts**:
   - Check database connectivity
   - Verify connection pool settings
   - Monitor database performance

2. **Redis Failures**:
   - Verify Redis is running
   - Check Redis URL configuration
   - Monitor Redis memory usage

3. **Celery Worker Issues**:
   - Ensure Celery workers are running
   - Check broker connectivity
   - Verify task routing configuration

4. **Storage Access Problems**:
   - Verify GCS credentials (if using GCS)
   - Check bucket permissions
   - Monitor storage quota usage

### Debug Information

The `/readyz` endpoint provides detailed error information:

- Component-specific error messages
- Duration measurements
- Failed check identification
- Overall system status

### Logs

Health check activities are logged with appropriate levels:

- **DEBUG**: Individual check results
- **INFO**: Endpoint access
- **ERROR**: Check failures and timeouts

## Security Considerations

- Health endpoints are public (no authentication required)
- No sensitive information is exposed
- Error messages are sanitized
- Timeouts prevent resource exhaustion attacks

## Future Enhancements

1. **Metrics Export**: Prometheus metrics for dependency health
2. **Circuit Breaker**: Automatic dependency failure detection
3. **Health History**: Historical health check results
4. **Custom Checks**: Pluggable health check system
5. **Health Dashboard**: Web UI for health monitoring
