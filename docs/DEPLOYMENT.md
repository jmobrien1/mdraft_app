# Deployment Guide

This document provides comprehensive guidance for deploying the mdraft application on Render.

## Pre-Deployment Requirements

### Environment Variables

The following environment variables must be configured in Render:

#### Security & Authentication
- `SECRET_KEY`: Auto-generated stable secret key (configured in render.yaml)
- `MDRAFT_PUBLIC_MODE`: Set to "0" to require authentication
- `LOGIN_DISABLED`: Set to "false" to enable login requirement
- `ALLOWLIST`: Comma-separated list of allowed email addresses

#### Session Cookie Security (HTTPS)
- `SESSION_COOKIE_SECURE`: Set to "true" for HTTPS-only cookies
- `SESSION_COOKIE_SAMESITE`: Set to "Lax" for CSRF protection
- `REMEMBER_COOKIE_SECURE`: Set to "true" for HTTPS-only remember cookies
- `REMEMBER_COOKIE_SAMESITE`: Set to "Lax" for CSRF protection

#### Database & Migration
- `DATABASE_URL`: PostgreSQL connection string
- Pre-deploy script automatically runs `flask db upgrade`

#### Rate Limiting
- `GLOBAL_RATE_LIMIT`: Set to "120 per minute" for abuse protection
- `FLASK_LIMITER_STORAGE_URI`: Redis URL for rate limiting (optional)

#### Queue Configuration
- `QUEUE_MODE`: Set to "sync" for synchronous processing
- `CELERY_BROKER_URL`: Redis URL for Celery broker (if using async mode)
- `CELERY_RESULT_BACKEND`: Redis URL for Celery results (if using async mode)

#### Google Cloud Services
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account key
- `GCS_BUCKET_NAME`: Google Cloud Storage bucket for uploads
- `USE_GCS`: Set to "0" to disable GCS (use local storage)

#### Monitoring & Logging
- `SENTRY_DSN`: Sentry DSN for error tracking
- `SENTRY_ENVIRONMENT`: Set to "production"
- `LOG_LEVEL`: Logging level (default: INFO)

#### Webhook Security
- `WEBHOOK_SECRET`: Secret for webhook signature verification

## Deployment Configuration

### render.yaml

The application is configured with three services:

1. **Web Service** (`mdraft-web`)
   - Runs the main Flask application
   - Pre-deploy: Runs `flask db upgrade`
   - Health check: `/health` endpoint
   - Start command: Gunicorn with 2 workers, 8 threads

2. **Worker Service** (`mdraft_app-worker`)
   - Runs Celery workers for background processing
   - Pre-deploy: Runs `flask db upgrade`
   - Start command: Celery worker with 4 concurrent tasks

3. **Cleanup Service** (`mdraft-cleanup`)
   - Daily cron job for cleanup tasks
   - Runs at 06:00 UTC daily

### Pre-Deploy Migration

The `scripts/migration_sentry.sh` script ensures:

1. **Database Connectivity**: Verifies connection to PostgreSQL
2. **Migration Execution**: Runs `flask db upgrade`
3. **Schema Validation**: Checks required columns exist
4. **Auto-Repair**: Handles migration chain breaks gracefully

## Health Checks

### `/health` Endpoint
- **Purpose**: Lightweight health check for load balancers
- **Response**: `{"status": "ok"}`
- **Database**: Executes `SELECT 1` query
- **Use**: Render health checks, basic monitoring

### `/readyz` Endpoint
- **Purpose**: Comprehensive readiness check
- **Checks**: Database, Redis (if configured), Storage
- **Response**: Detailed status with component health
- **Use**: Kubernetes readiness probes

### `/healthz` Endpoint
- **Purpose**: Fast health check without external dependencies
- **Response**: Basic service information
- **Use**: Quick health verification

## Smoke Testing

### Python Smoke Test (Comprehensive)

```bash
# Set environment variables
export SMOKE_TEST_URL="https://your-app.onrender.com"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="your-password"

# Run full end-to-end test
python scripts/smoke_test.py
```

**Tests performed:**
1. Health check
2. Login
3. Create proposal (`/api/agents/compliance-matrix/proposals`)
4. Upload file (`/api/convert`)
5. Attach file to proposal (`/api/agents/compliance-matrix/proposals/{id}/documents`)
6. Fetch requirements (`/api/agents/compliance-matrix/proposals/{id}/requirements`)
7. Worker ping
8. Delete proposal (`/api/agents/compliance-matrix/proposals/{id}`)

### Shell Smoke Test (Basic)

```bash
# Set environment variables
export SMOKE_TEST_URL="https://your-app.onrender.com"

# Run basic connectivity test
./scripts/smoke_test.sh
```

**Tests performed:**
1. Health check
2. Ready check
3. API health check
4. Migration status (auth required)
5. Proposals list (auth required) (`/api/agents/compliance-matrix/proposals`)
6. Convert endpoint (auth required) (`/api/convert`)
7. Worker ping (auth required)

## Deployment Validation

### Acceptance Checklist

Run the deployment validation script to verify all requirements:

```bash
# Set environment variables
export VALIDATION_URL="https://your-app.onrender.com"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="your-password"

# Run validation
python scripts/deployment_validation.py
```

**Validation checks:**
- ✅ Proposals page loads → GET list fires and resolves (no infinite loader)
- ✅ Create proposal works; Add documents runs: upload/convert → attach → requirements refresh
- ✅ Requirements table populates (or shows 'none yet')
- ✅ Delete/edit (attach/detach) work and update the UI
- ✅ All API responses are JSON; 401/403/500 are readable
- ✅ Worker (if used) passes ping and finishes conversions
- ✅ Render pre-deploy migration succeeds; health check green

## Troubleshooting

### Common Issues

#### Migration Failures
- Check database connectivity
- Verify `DATABASE_URL` is correct
- Review migration logs in Render dashboard
- Run `flask db current` to check migration status

#### Health Check Failures
- Verify `/health` endpoint returns `{"status": "ok"}`
- Check database connectivity
- Review application logs for errors

#### Authentication Issues
- Verify `SECRET_KEY` is set and stable
- Check session cookie configuration
- Ensure `MDRAFT_PUBLIC_MODE=0` and `LOGIN_DISABLED=false`

#### Rate Limiting Issues
- Check `GLOBAL_RATE_LIMIT` configuration
- Verify Redis connectivity (if using Redis for rate limiting)
- Review rate limiting logs

#### Worker Issues
- Check Celery broker connectivity
- Verify worker service is running
- Test worker ping endpoint

### Debugging Commands

```bash
# Check migration status
flask db current

# Check database connectivity
flask db upgrade --dry-run

# Test health endpoint
curl https://your-app.onrender.com/health

# Test worker ping (requires auth)
curl -X POST https://your-app.onrender.com/api/ops/ping \
  -H "Content-Type: application/json" \
  -d '{"message":"test"}'

# Run smoke test
python scripts/smoke_test.py
```

## Monitoring

### Logs
- Application logs: Available in Render dashboard
- Request logs: Include method, path, status, duration, request_id
- Error logs: Include request_id for correlation

### Metrics
- Health check status
- Response times
- Error rates
- Database connectivity

### Alerts
- Health check failures
- Migration failures
- High error rates
- Worker connectivity issues

## Security Considerations

### HTTPS Configuration
- All cookies configured for HTTPS-only
- HSTS headers enabled
- Secure session management

### Authentication
- Login required (`MDRAFT_PUBLIC_MODE=0`)
- Session cookies with CSRF protection
- Rate limiting enabled

### Database Security
- Connection strings use SSL
- Database credentials stored securely
- Migration scripts run with proper permissions

## Performance Optimization

### Gunicorn Configuration
- 2 workers with 8 threads each
- 120-second timeout
- Optimized for Render's environment

### Database Optimization
- Connection pooling
- Indexed queries
- Efficient migrations

### Caching
- Redis for rate limiting (optional)
- Celery result backend (optional)
- Static file caching

## Rollback Strategy

### Database Rollback
```bash
# Rollback to previous migration
flask db downgrade

# Check migration status
flask db current
```

### Application Rollback
- Use Render's rollback feature
- Verify health checks pass
- Run smoke tests after rollback

### Data Backup
- Regular database backups
- File storage backups
- Configuration backups
