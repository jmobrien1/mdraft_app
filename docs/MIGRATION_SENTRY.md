# Migration Sentry System

## Overview

The Migration Sentry system guarantees that database migrations run during deployment and fails the deploy if they don't. This eliminates "silent failures" where the app appears to deploy successfully but crashes at runtime due to missing database schema.

## Components

### 1. Migration Sentry Script (`scripts/migration_sentry.sh`)

A strict pre-deployment script that:

- **Validates Environment**: Ensures `DATABASE_URL` and `FLASK_APP` are set
- **Tests Connectivity**: Proves it can connect to the actual production database
- **Runs Migrations**: Executes `flask db upgrade` with full verbosity
- **Handles Chain Breaks**: Automatically runs `stamp head` if upgrade fails
- **Verifies Schema**: Confirms required columns exist before allowing deploy to succeed
- **Fails Fast**: Exits with non-zero code if any step fails

### 2. Migration Status Endpoint (`/api/ops/migration_status`)

A runtime endpoint that confirms in one call that required columns exist:

```json
{
  "migrated": true,
  "alembic_current": "abc123def456",
  "checks": {
    "proposals.visitor_session_id": true,
    "conversions.proposal_id": true
  }
}
```

### 3. Frontend API Guard (`app/static/app.js`)

Enhanced fetch wrapper that prevents "Unexpected token '<'" errors by:

- Setting `Accept: application/json` header
- Detecting HTML error pages vs JSON responses
- Providing readable error messages instead of JSON parse failures

## Deployment Integration

### Render.yaml Configuration

```yaml
services:
  - type: web
    name: mdraft-web
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
    
  - type: worker
    name: mdraft_app-worker
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4
```

### Required Environment Variables

- `DATABASE_URL`: Production database connection string
- `FLASK_APP`: Flask application entry point (defaults to `run.py`)
- `SQLALCHEMY_DATABASE_URI`: Optional override (defaults to `DATABASE_URL`)

## How It Works

### Pre-Deployment Phase

1. **Environment Check**: Validates required environment variables
2. **Database Ping**: Connects to production database and verifies connectivity
3. **Migration Execution**: Runs `flask db upgrade -v` with full logging
4. **Chain Repair**: If upgrade fails, runs `stamp head` then retries upgrade
5. **Schema Verification**: Checks that required columns exist in the database
6. **Success/Failure**: Exits with appropriate code to pass/fail deployment

### Runtime Monitoring

The `/api/ops/migration_status` endpoint provides:

- **Migration Status**: Whether all required migrations have been applied
- **Alembic Version**: Current database migration version
- **Schema Health**: Status of each required column
- **Error Details**: Specific information about any failures

## Common Failure Scenarios

### 1. Environment Issues

**Problem**: `DATABASE_URL` not set or `FLASK_APP` misconfigured
**Detection**: Script fails immediately with clear error message
**Solution**: Check Render Dashboard environment variables

### 2. Database Connectivity

**Problem**: Cannot connect to production database during pre-deploy
**Detection**: Database ping fails, script exits non-zero
**Solution**: Verify database URL, network access, and VPC settings

### 3. Migration Chain Broken

**Problem**: Alembic migration chain is inconsistent
**Detection**: `flask db upgrade` fails, script attempts `stamp head` recovery
**Solution**: Review migration files and database state

### 4. Missing Schema

**Problem**: Migrations run but required columns don't exist
**Detection**: Schema verification fails, deploy stops
**Solution**: Check migration files and ensure they create required columns

## Immediate Hot-Patch

If the app is currently bricked due to missing `conversions.proposal_id`:

1. Connect to your Render Postgres database
2. Run the hot-patch script:

```sql
-- From scripts/hot_patch_conversions.sql
ALTER TABLE public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);
```

This immediately unblocks the app while you redeploy with the migration sentry.

## Testing the System

### Local Testing

```bash
# Test the migration sentry locally
export DATABASE_URL="your_production_db_url"
export FLASK_APP="run.py"
bash scripts/migration_sentry.sh
```

### Endpoint Testing

```bash
# Test the migration status endpoint
curl https://your-app.onrender.com/api/ops/migration_status
```

### Frontend Testing

```javascript
// Test the API guard
try {
  const status = await api('/api/ops/migration_status');
  console.log('Migration status:', status);
} catch (error) {
  console.error('API error:', error.message);
}
```

## Benefits

1. **No Silent Failures**: Deployments fail fast if migrations don't run
2. **Clear Diagnostics**: Detailed logging shows exactly what went wrong
3. **Automatic Recovery**: Handles common migration chain issues
4. **Runtime Monitoring**: Easy to check migration status in production
5. **Frontend Resilience**: API calls handle errors gracefully

## Migration from Old System

The migration sentry replaces the previous `migration_doctor` approach:

- **Before**: `startCommand: python -m scripts.migration_doctor && gunicorn ...`
- **After**: `preDeployCommand: bash scripts/migration_sentry.sh` + simple start command

This separation ensures migrations run before the app starts and provides better error handling and logging.
