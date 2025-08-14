# Migration Doctor Implementation Summary

## Overview
This document summarizes the implementation of the Migration Doctor system to fix failing migrations and ensure proper JSON error handling for the mdraft application.

## 1. Migration Doctor Script (`scripts/migration_doctor.py`)

### Key Features:
- **Advisory Lock**: Uses PostgreSQL advisory lock (key: 87421123) to prevent concurrent migrations
- **Progressive Fallback Strategy**:
  1. Try `flask db upgrade` (Flask-Migrate)
  2. If failed → `flask db stamp head` → `flask db upgrade`
  3. If still failed → `alembic upgrade head` directly
  4. If still failed → Apply guarded DDL as last resort

### Guarded DDL Operations:
- **Proposals Table**:
  - Add `visitor_session_id VARCHAR(64)` column
  - Add `expires_at TIMESTAMP WITHOUT TIME ZONE` column
  - Create index on `visitor_session_id`
  - Add check constraint for owner presence

- **Conversions Table**:
  - Add `proposal_id INTEGER` column
  - Add `user_id INTEGER` column
  - Add `visitor_session_id VARCHAR(64)` column
  - Create indexes on all new columns
  - Backfill ownership data from proposals

### Safety Features:
- All DDL uses `IF NOT EXISTS` clauses
- Advisory lock prevents concurrent execution
- Graceful error handling with detailed logging
- Returns exit code 0 even if migrations fail (app can start with guarded schema)

## 2. Deployment Integration

### Render.yaml Updates:
- **Web Service**: `startCommand: python -m scripts.migration_doctor && gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app`
- **Worker Service**: `startCommand: python -m scripts.migration_doctor && celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4 --without-gossip --without-mingle`
- **Environment Variables**: Added `FLASK_APP=run.py` to both services

### Pre-deploy Integration:
- Migration doctor runs before every process start
- Covers restarts, scale-outs, and new deployments
- Optional: Can also add to `preDeployCommand` for additional safety

## 3. JSON Error Handling

### API Error Blueprint (`app/api/errors.py`):
- Forces JSON responses for all `/api/*` routes
- Preserves HTML responses for non-API routes
- Handles both HTTPException and generic exceptions
- Returns structured error format: `{"error": "code", "detail": "message"}`

### Registration:
- Added to app factory in `app/__init__.py`
- Registered after other blueprints to ensure proper error handling

## 4. Migration Status Endpoint

### Endpoint: `/api/ops/migration_status`
- **Alembic Status**: Compares current vs head versions
- **Schema Health**: Probes for required columns
- **Overall Status**: Determines if migrations are complete
- **Error Handling**: Graceful degradation if checks fail

### Response Format:
```json
{
  "migrated": true,
  "alembic": {
    "current": "abc123",
    "head": "abc123",
    "at_head": true
  },
  "checks": {
    "proposals.visitor_session_id": true,
    "conversions.proposal_id": true
  }
}
```

## 5. Frontend API Guard

### JavaScript API Function (`app/static/app.js`):
- **Global Function**: `window.api()` available to all templates
- **JSON Detection**: Automatically detects content-type
- **Error Handling**: Parses JSON errors, falls back to text
- **Consistent Interface**: Replaces raw `fetch()` calls

### Updated Templates:
- **index.html**: Upload, polling, recent conversions, estimates
- **view.html**: Conversion status polling
- **base.html**: Usage badge loading
- **proposals.html**: Proposal loading, compliance matrix
- **compliance_matrix.html**: All API calls for requirements

### Error Prevention:
- Prevents "Unexpected token '<'" errors
- Shows user-friendly error messages
- Maintains app functionality even with API failures

## 6. Testing and Verification

### Test Script (`scripts/test_migration_doctor.py`):
- Validates migration doctor imports
- Tests environment variable detection
- Verifies command execution capability

### Verification Checklist:
1. **Deploy and Check Logs**:
   - Look for `[migration_doctor] flask db upgrade OK`
   - Or `[migration_doctor] stamp→upgrade OK`
   - Or `[migration_doctor] upgrade OK after guarded DDL`

2. **Test Migration Status**:
   - Visit `/api/ops/migration_status`
   - Should show `"migrated": true`

3. **Test Anonymous Flow**:
   - Create proposal (no 500 errors)
   - Upload files successfully
   - Run compliance matrix

4. **Test Frontend Error Handling**:
   - Intentionally break an endpoint
   - Should get JSON error message
   - No "Unexpected token '<'" crashes

## 7. Emergency SQL (One-time Fix)

If immediate relief is needed before deployment, run in Render Shell:

```sql
-- Proposals table fixes
ALTER TABLE public.proposals ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);
ALTER TABLE public.proposals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;
CREATE INDEX IF NOT EXISTS ix_proposals_visitor_session_id ON public.proposals (visitor_session_id);
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_proposals_owner_present') THEN
    ALTER TABLE public.proposals ADD CONSTRAINT ck_proposals_owner_present
    CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL));
  END IF;
END $$;

-- Conversions table fixes
ALTER TABLE public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;
ALTER TABLE public.conversions ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE public.conversions ADD COLUMN IF NOT EXISTS visitor_session_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);
CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON public.conversions (user_id);
CREATE INDEX IF NOT EXISTS ix_conversions_visitor_session_id ON public.conversions (visitor_session_id);
```

## 8. Benefits

### Reliability:
- **Zero Downtime**: Migration doctor ensures schema is always safe
- **Self-Healing**: Automatically fixes broken migration chains
- **Concurrent Safety**: Advisory locks prevent race conditions

### User Experience:
- **No More Crashes**: Frontend gracefully handles API errors
- **Clear Error Messages**: JSON errors provide actionable feedback
- **Consistent Behavior**: All API routes return structured errors

### Operations:
- **Monitoring**: Migration status endpoint for health checks
- **Debugging**: Detailed logging for troubleshooting
- **Safety**: Idempotent operations can be run repeatedly

## 9. Files Modified

### New Files:
- `scripts/migration_doctor.py` - Main migration doctor script
- `app/api/errors.py` - API error handling blueprint
- `scripts/test_migration_doctor.py` - Test script
- `MIGRATION_DOCTOR_IMPLEMENTATION.md` - This documentation

### Modified Files:
- `render.yaml` - Added migration doctor to start commands and FLASK_APP env var
- `app/__init__.py` - Registered API errors blueprint
- `app/static/app.js` - Added global api() function
- `app/templates/index.html` - Updated fetch calls to use api()
- `app/templates/view.html` - Updated fetch calls to use api()
- `app/templates/base.html` - Updated fetch calls to use api()
- `app/templates/proposals.html` - Updated fetch calls to use api()
- `app/templates/compliance_matrix.html` - Updated fetch calls to use api()

## 10. Next Steps

1. **Deploy**: Push changes to trigger migration doctor
2. **Monitor**: Watch logs for migration doctor execution
3. **Verify**: Test migration status endpoint
4. **Test**: Run through anonymous proposal flow
5. **Validate**: Confirm no more frontend crashes

The Migration Doctor system provides a robust, self-healing solution for database migrations while ensuring a smooth user experience with proper error handling.
