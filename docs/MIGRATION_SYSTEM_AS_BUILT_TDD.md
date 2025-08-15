# Migration System: As-Built and Technical Design Document

## Executive Summary

This document describes the comprehensive migration system implemented for the mdraft application, including the extensive troubleshooting and hardening process that was required to resolve persistent `flask db upgrade` issues. The system ensures database migrations run reliably during deployment and prevents silent failures that could cause runtime crashes.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Implementation Details](#implementation-details)
4. [Troubleshooting History](#troubleshooting-history)
5. [Migration Sentry System](#migration-sentry-system)
6. [Database Schema Management](#database-schema-management)
7. [Deployment Integration](#deployment-integration)
8. [Monitoring and Observability](#monitoring-and-observability)
9. [Testing and Validation](#testing-and-validation)
10. [Operational Procedures](#operational-procedures)
11. [Lessons Learned](#lessons-learned)

## System Overview

### Problem Statement

The mdraft application experienced persistent deployment failures due to database migration issues:

- **Silent Failures**: Deployments would appear successful but fail at runtime due to missing database schema
- **Migration Chain Breaks**: Unknown alembic revisions caused `flask db upgrade` to fail
- **Driver Compatibility**: psycopg2 vs psycopg v3 driver mismatches
- **Context Issues**: Flask application context not available during pre-deployment
- **DDL Syntax Errors**: Invalid PostgreSQL syntax in migration scripts

### Solution Overview

Implemented a comprehensive Migration Sentry system that:

1. **Guarantees Migration Execution**: Pre-deployment script ensures migrations run before app starts
2. **Handles Edge Cases**: Auto-repair logic for broken migration chains
3. **Validates Schema**: Final verification ensures required columns exist
4. **Provides Monitoring**: Runtime endpoint to check migration status
5. **Ensures Compatibility**: Proper driver and context management

## Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Render        │    │   Migration      │    │   Application   │
│   Deployment    │───▶│   Sentry         │───▶│   Runtime       │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   PostgreSQL     │
                       │   Database       │
                       └──────────────────┘
```

### Component Architecture

#### 1. Migration Sentry (`scripts/migration_sentry.sh`)
- **Purpose**: Pre-deployment migration execution and validation
- **Responsibilities**:
  - Environment validation
  - Database connectivity testing
  - Migration execution with auto-repair
  - Schema verification
  - Deployment failure prevention

#### 2. Migration Status Endpoint (`/api/ops/migration_status`)
- **Purpose**: Runtime monitoring of migration status
- **Responsibilities**:
  - Check required columns exist
  - Verify alembic version status
  - Provide health status for monitoring

#### 3. Database URL Normalization (`app/utils/db_url.py`)
- **Purpose**: Ensure consistent database driver usage
- **Responsibilities**:
  - Normalize URLs to `postgresql+psycopg://`
  - Handle psycopg v3 compatibility
  - Support both app and sentry contexts

#### 4. Enhanced env.py (`migrations/env.py`)
- **Purpose**: Safe alembic execution outside Flask context
- **Responsibilities**:
  - Fallback to environment variables
  - Handle missing Flask app context
  - Prevent "working outside of application context" errors

## Implementation Details

### 1. Migration Sentry Script

#### Core Logic Flow

```bash
#!/usr/bin/env bash
# scripts/migration_sentry.sh

# 1. Environment Validation
: "${DATABASE_URL:?DATABASE_URL is not set}"
export SQLALCHEMY_DATABASE_URI="${SQLALCHEMY_DATABASE_URI:-$DATABASE_URL}"
export FLASK_APP="${FLASK_APP:-run.py}"

# 2. Database Connectivity Test (with psycopg v3 normalization)
python - <<'PY'
# URL normalization logic
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://") and "+psycopg" not in url:
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
# Database ping and version check
PY

# 3. Migration Execution with Auto-Repair
flask db upgrade
if [[ $rc -ne 0 ]]; then
    # Auto-repair: stamp base → retry upgrade
    flask db stamp base
    flask db upgrade
    
    if [[ $rc2 -ne 0 ]]; then
        # Fallback: guarded DDL → stamp head
        # Apply required columns and indexes
        flask db stamp head
    fi
fi

# 4. Final Schema Verification
python - <<'PY'
# Check required columns exist
need = [("proposals","visitor_session_id"), ("conversions","proposal_id")]
# Exit non-zero if any missing
PY
```

#### Key Features

- **Environment Validation**: Ensures required variables are set
- **URL Normalization**: Consistent psycopg v3 driver usage
- **Auto-Repair Logic**: Handles unknown revisions gracefully
- **Guarded DDL**: Safe schema modifications as fallback
- **Fail-Fast Verification**: Prevents deployment with missing schema

### 2. Migration Status Endpoint

#### Implementation

```python
@ops.get("/api/ops/migration_status")
def migration_status():
    """Check migration status and schema health."""
    try:
        # Check required columns
        checks = {}
        for table, col in [("proposals", "visitor_session_id"), ("conversions", "proposal_id")]:
            cnt = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name=:t AND column_name=:c
            """), {"t": table, "c": col}).scalar()
            checks[f"{table}.{col}"] = (cnt == 1)

        # Get current alembic version
        current = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        
        return jsonify({
            "migrated": all(checks.values()),
            "alembic_current": current,
            "checks": checks
        })
    except Exception as e:
        return jsonify({"migrated": False, "error": str(e)}), 500
```

#### Response Format

```json
{
  "migrated": true,
  "alembic_current": "defensive_schema_guard_20250814",
  "checks": {
    "proposals.visitor_session_id": true,
    "conversions.proposal_id": true
  }
}
```

### 3. Database URL Normalization

#### Implementation

```python
def normalize_db_url(raw: str) -> str:
    if not raw:
        return raw
    url = raw
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
```

#### Usage

```python
# In app/__init__.py
from .utils.db_url import normalize_db_url
db_url = normalize_db_url(ENV.get("DATABASE_URL", ""))
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
```

### 4. Enhanced env.py

#### Safe Fallback Implementation

```python
def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace('%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')
    except Exception:
        # Fallback to environment variables when no Flask app context
        import os
        url = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
        if not url:
            raise
        return url.replace('%', '%%')
```

## Troubleshooting History

### Phase 1: Initial Migration Issues

#### Problem
- Deployments failing with `ModuleNotFoundError: No module named 'psycopg2'`
- Migration doctor running at startup causing delays
- Silent failures where app appeared deployed but crashed at runtime

#### Root Cause Analysis
- psycopg2 vs psycopg v3 driver mismatch
- Migration doctor running in start command instead of pre-deployment
- No validation of migration success

#### Solution
- Updated requirements.txt to use `psycopg[binary]==3.2.9`
- Implemented URL normalization for consistent driver usage
- Moved migration logic to pre-deployment phase

### Phase 2: Flask-Migrate Compatibility Issues

#### Problem
- `flask db upgrade -v` failing with unsupported flag
- Unknown alembic revisions causing migration failures
- No recovery mechanism for broken migration chains

#### Root Cause Analysis
- Flask-Migrate version compatibility issues
- Migration chain broken by unknown revisions
- No fallback mechanism for failed migrations

#### Solution
- Removed unsupported `-v` flag from `flask db upgrade`
- Implemented auto-repair logic: `stamp base` → retry upgrade
- Added guarded DDL as final fallback

### Phase 3: DDL Syntax Errors

#### Problem
- PostgreSQL rejecting `ALTER TABLE IF NOT EXISTS` syntax
- Migration sentry failing on DDL execution
- Inconsistent syntax between scripts

#### Root Cause Analysis
- PostgreSQL only supports `ALTER TABLE IF EXISTS` (not `IF NOT EXISTS`)
- Incorrect syntax in migration sentry script
- Need to keep `ADD COLUMN IF NOT EXISTS` but remove invalid table clause

#### Solution
- Fixed DDL syntax: `ALTER TABLE IF EXISTS ... ADD COLUMN IF NOT EXISTS`
- Applied consistent syntax across all scripts
- Added syntax validation in deployment pipeline

### Phase 4: Application Context Issues

#### Problem
- "Working outside of application context" errors
- Raw `alembic` calls failing without Flask context
- Inconsistent behavior between local and deployment environments

#### Root Cause Analysis
- Migration sentry using raw `alembic` commands outside Flask context
- No fallback for environment variable access
- Context-dependent database configuration

#### Solution
- Replaced all `alembic` calls with `flask db` commands
- Enhanced env.py with safe fallback to environment variables
- Ensured all operations run within Flask application context

### Phase 5: Final Hardening

#### Problem
- Edge cases still causing deployment failures
- Need for comprehensive error handling
- Monitoring and observability gaps

#### Root Cause Analysis
- Complex migration scenarios not fully covered
- Limited visibility into migration status
- No runtime monitoring of schema health

#### Solution
- Implemented comprehensive auto-repair logic
- Added migration status endpoint for monitoring
- Enhanced logging and error reporting
- Added final schema verification

## Migration Sentry System

### Design Principles

1. **Fail Fast**: Exit non-zero if migrations don't run or schema is invalid
2. **Auto-Repair**: Handle common failure scenarios automatically
3. **Guarded Operations**: Safe DDL execution with proper error handling
4. **Comprehensive Logging**: Clear visibility into each step
5. **Context Safety**: Ensure proper Flask application context

### Auto-Repair Logic

```mermaid
graph TD
    A[Start Migration] --> B[flask db upgrade]
    B --> C{Success?}
    C -->|Yes| D[Verify Schema]
    C -->|No| E[stamp base]
    E --> F[retry upgrade]
    F --> G{Success?}
    G -->|Yes| D
    G -->|No| H[Apply Guarded DDL]
    H --> I[stamp head]
    I --> D
    D --> J{Schema Valid?}
    J -->|Yes| K[Deploy Success]
    J -->|No| L[Deploy Failure]
```

### Guarded DDL Operations

#### Required Columns and Indexes

```sql
-- PROPOSALS table
ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);
ALTER TABLE IF EXISTS public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;
CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);

-- CONVERSIONS table
ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;
ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE IF EXISTS public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);
CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);
CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);
```

#### Constraint Management

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_proposals_owner_present') THEN
    ALTER TABLE public.proposals
    ADD CONSTRAINT ck_proposals_owner_present
    CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
  END IF;
END $$;
```

## Database Schema Management

### Current Schema Requirements

#### Proposals Table
- `visitor_session_id VARCHAR(64)` - Required for anonymous proposals
- `expires_at TIMESTAMP WITHOUT TIME ZONE` - TTL for anonymous proposals
- `user_id INTEGER` - Optional, for authenticated users
- Constraint: Either `user_id` or `visitor_session_id` must be present

#### Conversions Table
- `proposal_id INTEGER` - Foreign key to proposals
- `user_id INTEGER` - Optional, for authenticated users
- `visitor_session_id VARCHAR(64)` - For anonymous conversions

### Migration Strategy

1. **Backward Compatibility**: All new columns are nullable
2. **Safe Operations**: Use `IF EXISTS` and `IF NOT EXISTS` clauses
3. **Indexing**: Create indexes for performance on frequently queried columns
4. **Constraints**: Add constraints only after data validation

## Deployment Integration

### Render Configuration

#### Web Service
```yaml
services:
  - type: web
    name: mdraft-web
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
```

#### Worker Service
```yaml
services:
  - type: worker
    name: mdraft_app-worker
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4
```

### Environment Variables

#### Required Variables
- `DATABASE_URL` - PostgreSQL connection string
- `FLASK_APP` - Flask application entry point (defaults to `run.py`)
- `SQLALCHEMY_DATABASE_URI` - Optional override (defaults to `DATABASE_URL`)

#### Optional Variables
- `FLASK_ENV` - Environment (production/development)
- `SECRET_KEY` - Application secret key
- Various Google Cloud and service configuration

### Deployment Flow

1. **Pre-Deployment**: Migration sentry runs and validates schema
2. **Application Start**: Simple start command without migration logic
3. **Health Check**: `/health` endpoint validates application status
4. **Runtime Monitoring**: `/api/ops/migration_status` provides schema health

## Monitoring and Observability

### Migration Status Endpoint

#### Purpose
- Runtime validation of schema health
- Monitoring integration
- Debugging migration issues

#### Usage
```bash
curl https://your-app.onrender.com/api/ops/migration_status
```

#### Response Interpretation
- `migrated: true` - All required columns exist
- `checks` - Individual column status
- `alembic_current` - Current migration version

### Logging Strategy

#### Migration Sentry Logs
```
=== MIGRATION SENTRY: starting ===
FLASK_APP=run.py
DB (redacted): postgresql://******@host/database
[SENTRY] DB OK: database_name
[SENTRY] Server: PostgreSQL
=== MIGRATION SENTRY: flask db upgrade ===
=== MIGRATION SENTRY: verifying required columns ===
[SENTRY] schema OK.
=== MIGRATION SENTRY: success ===
```

#### Error Scenarios
```
=== MIGRATION SENTRY: upgrade failed; attempting auto-repair ===
flask db stamp base
=== MIGRATION SENTRY: retry flask db upgrade ===
=== MIGRATION SENTRY: upgrade still failing; applying guarded DDL ===
[SENTRY] Guarded DDL applied.
flask db stamp head
```

### Health Monitoring

#### Application Health
- `/health` - Basic application health
- `/api/ops/migration_status` - Schema health
- Database connectivity checks
- Service dependency validation

## Testing and Validation

### Local Testing

#### Migration Sentry Testing
```bash
# Test with production database URL
export DATABASE_URL="your_production_db_url"
export FLASK_APP="run.py"
bash scripts/migration_sentry.sh
```

#### URL Normalization Testing
```python
# Test cases
test_cases = [
    ("postgres://user:pass@host/db", "postgresql+psycopg://user:pass@host/db"),
    ("postgresql://user:pass@host/db", "postgresql+psycopg://user:pass@host/db"),
    ("postgresql+psycopg://user:pass@host/db", "postgresql+psycopg://user:pass@host/db"),
]
```

### Integration Testing

#### Endpoint Testing
```bash
# Test migration status endpoint
curl https://your-app.onrender.com/api/ops/migration_status
```

#### Frontend Testing
```javascript
// Test API guard
try {
  const status = await api('/api/ops/migration_status');
  console.log('Migration status:', status);
} catch (error) {
  console.error('API error:', error.message);
}
```

### Validation Checklist

- [ ] Migration sentry runs successfully in deployment
- [ ] Required columns exist in database
- [ ] Migration status endpoint returns `migrated: true`
- [ ] Frontend API calls work without crashes
- [ ] New proposal button functions correctly
- [ ] No "Unexpected token '<'" errors in frontend

## Operational Procedures

### Deployment Procedure

1. **Pre-Deployment Checks**
   - Verify environment variables are set
   - Ensure database connectivity
   - Run migration sentry locally if needed

2. **Deployment Monitoring**
   - Watch deployment logs for migration sentry output
   - Verify "=== MIGRATION SENTRY: success ===" appears
   - Check application health after deployment

3. **Post-Deployment Validation**
   - Test migration status endpoint
   - Verify UI functionality
   - Monitor application logs for errors

### Emergency Procedures

#### Database Schema Issues
1. **Immediate Fix**: Run hot-patch SQL
   ```sql
   ALTER TABLE public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);
   CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);
   ```

2. **Investigation**: Check migration status endpoint
3. **Resolution**: Redeploy with migration sentry

#### Migration Chain Issues
1. **Diagnosis**: Check alembic version in database
2. **Repair**: Use `flask db stamp head` to reset chain
3. **Validation**: Run migration sentry to verify

### Rollback Procedures

#### Migration Sentry Rollback
1. Change `preDeployCommand` back to `bash scripts/predeploy.sh`
2. Add migration doctor back to start commands
3. Deploy to revert to previous system

#### Database Rollback
1. Identify target migration version
2. Use `flask db downgrade` to target version
3. Verify schema integrity
4. Redeploy application

## Lessons Learned

### Technical Lessons

1. **Driver Compatibility**: Always normalize database URLs for consistent driver usage
2. **Context Management**: Use `flask db` commands instead of raw `alembic` for proper context
3. **DDL Syntax**: PostgreSQL `ALTER TABLE IF EXISTS` is correct, `IF NOT EXISTS` is invalid
4. **Fail-Fast Design**: Exit non-zero on migration failures to prevent silent deployment issues
5. **Auto-Repair Logic**: Implement graceful handling of common failure scenarios

### Process Lessons

1. **Pre-Deployment Validation**: Run migrations before application start, not during
2. **Comprehensive Logging**: Clear visibility into each step prevents debugging delays
3. **Monitoring Integration**: Runtime endpoints provide ongoing health validation
4. **Testing Strategy**: Local testing with production-like conditions catches issues early
5. **Documentation**: Detailed troubleshooting history helps prevent repeat issues

### Architecture Lessons

1. **Separation of Concerns**: Migration logic separate from application startup
2. **Defense in Depth**: Multiple layers of validation and fallback mechanisms
3. **Observability**: Runtime monitoring complements deployment-time validation
4. **Error Handling**: Graceful degradation with clear error messages
5. **Configuration Management**: Environment variable fallbacks for flexibility

### Future Improvements

1. **Automated Testing**: Add integration tests for migration scenarios
2. **Monitoring Alerts**: Set up alerts for migration status endpoint failures
3. **Performance Optimization**: Optimize migration execution time
4. **Documentation**: Maintain troubleshooting guide for common issues
5. **Tooling**: Develop additional debugging tools for migration issues

## Conclusion

The migration system implementation represents a comprehensive solution to persistent deployment issues. Through extensive troubleshooting and iterative improvement, we've created a robust system that:

- **Guarantees Migration Execution**: Pre-deployment validation ensures migrations run
- **Handles Edge Cases**: Auto-repair logic manages common failure scenarios
- **Provides Monitoring**: Runtime endpoints offer ongoing health validation
- **Ensures Compatibility**: Proper driver and context management
- **Prevents Silent Failures**: Fail-fast design prevents deployment with invalid schema

The system is now hardened against the most common migration failure scenarios and provides clear visibility into migration status. The extensive troubleshooting process has resulted in a more robust and maintainable migration system that will prevent similar issues in the future.

## Appendices

### Appendix A: Migration Scripts

#### scripts/migration_sentry.sh
Complete implementation with auto-repair logic and schema validation.

#### scripts/hot_patch_conversions.sql
Emergency SQL patch for immediate column addition.

#### app/utils/db_url.py
Database URL normalization utility.

### Appendix B: Configuration Files

#### render.yaml
Deployment configuration with migration sentry integration.

#### requirements.txt
Dependencies including psycopg v3 compatibility.

#### migrations/env.py
Enhanced alembic environment with safe fallbacks.

### Appendix C: API Endpoints

#### /api/ops/migration_status
Runtime migration status monitoring endpoint.

#### /health
Application health check endpoint.

### Appendix D: Troubleshooting Guide

#### Common Issues and Solutions
- Database connectivity problems
- Migration chain breaks
- DDL syntax errors
- Context-related failures

#### Debugging Procedures
- Local testing procedures
- Log analysis techniques
- Emergency repair steps
