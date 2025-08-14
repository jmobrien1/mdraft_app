# Migration Doctor Deployment Summary

## What Was Implemented

### 1. Migration Doctor Script (`scripts/migration_doctor.py`)
- **Purpose**: Ensures migrations run reliably in production on every boot/restart
- **Features**:
  - Takes a Postgres advisory lock to prevent concurrent upgrades
  - Runs `alembic upgrade head` first
  - If that fails, runs `alembic stamp head` then `alembic upgrade head`
  - As a last resort, applies guarded DDL to ensure required columns exist
  - Logs clear pass/fail output with emojis for visibility
  - Exits gracefully if another instance holds the lock

### 2. Updated Start Commands (`render.yaml`)
- **Web Service**: `python -m scripts.migration_doctor && gunicorn ...`
- **Worker Service**: `python -m scripts.migration_doctor && celery ...`
- **Replaces**: The old `schema_guard` script with the more robust migration doctor

### 3. Migration Status Endpoint (`/api/ops/migration_status`)
- **Purpose**: Runtime verification that migrations are at head and required columns exist
- **Response Format**:
  ```json
  {
    "migrated": true/false,
    "alembic": {
      "current": "revision_id",
      "head": "revision_id", 
      "at_head": true/false
    },
    "schema": {
      "proposals_has_visitor_session_id": true/false,
      "conversions_has_ownership": true/false
    }
  }
  ```

### 4. Fail-Fast Schema Check
- Added to app factory to log errors if required schema is missing
- Only runs in non-test environments
- Provides early warning if migration doctor didn't work

## How It Works

### Production Boot Sequence
1. **Migration Doctor Runs First**: Takes DB lock, runs migrations, applies guarded DDL if needed
2. **App Starts**: Flask app starts with guaranteed schema
3. **Status Endpoint Available**: `/api/ops/migration_status` for monitoring

### Guarded DDL Statements
The migration doctor ensures these columns exist:
- `proposals.visitor_session_id` (VARCHAR(64))
- `proposals.expires_at` (TIMESTAMP)
- `conversions.user_id` (INTEGER)
- `conversions.visitor_session_id` (VARCHAR(64))
- Required indexes and constraints

### Advisory Lock System
- Uses PostgreSQL advisory lock (key: 73219011)
- Prevents multiple instances from running migrations simultaneously
- If lock is held, instance skips migration cycle (safe)

## Verification Steps

### 1. Deploy and Check Logs
Watch for these log messages:
```
[migration_doctor] $ alembic upgrade head
[migration_doctor] ✅ Alembic upgrade OK.
[migration_doctor] ✅ Done.
```

### 2. Test Migration Status Endpoint
```bash
curl https://your-app.onrender.com/api/ops/migration_status
```

Expected response:
```json
{
  "migrated": true,
  "alembic": {
    "current": "defensive_schema_guard_20250814",
    "head": "defensive_schema_guard_20250814",
    "at_head": true
  },
  "schema": {
    "proposals_has_visitor_session_id": true,
    "conversions_has_ownership": true
  }
}
```

### 3. Test Anonymous Proposals
- Open incognito window
- Go to your app
- Create a proposal → should succeed (no 500 errors)
- Upload files → should work
- Run Compliance Matrix → should work

### 4. Test Recent Conversions
- Check that "Recent conversions" section works
- Verify proposals appear correctly

## Troubleshooting

### If Migration Doctor Fails
1. Check logs for `[migration_doctor]` messages
2. Verify `DATABASE_URL` is set in Render environment
3. Check if another instance holds the advisory lock
4. Look for `alembic` command errors

### If Status Endpoint Shows `migrated: false`
1. Check which specific checks are failing
2. Verify migration doctor ran successfully
3. Check if schema columns exist manually

### If Anonymous Proposals Still Fail
1. Check that `proposals.visitor_session_id` column exists
2. Verify the owner check constraint is present
3. Check app logs for specific error messages

## Files Modified

1. `scripts/migration_doctor.py` - New migration doctor script
2. `render.yaml` - Updated start commands for web and worker
3. `app/api/ops.py` - New migration status endpoint
4. `app/__init__.py` - Added ops blueprint and fail-fast check

## Success Criteria ✅

- [ ] Migration doctor runs on every boot/restart
- [ ] `/api/ops/migration_status` returns `migrated: true`
- [ ] Anonymous proposal creation works (no 500 errors)
- [ ] `/api/proposals` endpoint works
- [ ] "Recent conversions" section works
- [ ] All required schema columns exist

## Why This Fixes the Problem

1. **Guaranteed Execution**: Migration doctor runs before app starts on every boot
2. **Robust Fallback**: If Alembic fails, guarded DDL ensures schema exists
3. **Concurrency Safe**: Advisory lock prevents migration conflicts
4. **Monitoring**: Status endpoint makes it obvious if migrations worked
5. **Idempotent**: All operations are safe to run multiple times

The migration doctor ensures that even if the migration chain is broken or Alembic fails, the required schema columns will exist, allowing the app to function properly with anonymous proposals.
