# Perfect Render Pre-Deployment Command

## The Issue
The pre-deployment script was failing with two critical errors:
1. `ValueError: Unrecognized value for SESSION_TYPE: null` - Flask-Session couldn't determine session backend
2. `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379` - Redis client defaulting to localhost

## Root Cause
The pre-deployment script (`bash scripts/migration_sentry.sh`) was running in an environment where session-related environment variables were not properly set, causing Flask-Session to fail during database migrations.

## Solution

### Option 1: Use the Improved Pre-Deployment Script (Recommended)
```bash
bash scripts/predeploy.sh
```

This script:
- Loads secrets from `/etc/secrets/mdraft-web`
- Sets proper session configuration for pre-deployment
- Ensures all required environment variables are available
- Runs the migration sentry script with proper configuration

### Option 2: Manual Command (Alternative)
```bash
export $(cat /etc/secrets/mdraft-web | xargs) && export SESSION_BACKEND=filesystem && export SESSION_TYPE=filesystem && bash scripts/migration_sentry.sh
```

## Why This Works

### Session Configuration During Pre-Deployment
During pre-deployment (database migrations), we use `filesystem` session backend instead of `redis` because:
1. **No Redis dependency**: Database migrations don't need Redis sessions
2. **Faster execution**: Filesystem sessions are faster for migration operations
3. **Reliability**: Eliminates Redis connection issues during deployment

### Production Runtime Configuration
After deployment, the application will use the proper session configuration:
- `SESSION_BACKEND=redis` (from environment variables)
- `SESSION_TYPE=redis` (set by application logic)
- Redis client properly configured for `redis://red-d2gudc7diees73duftog:6379`

## Environment Variables Required

### For Pre-Deployment (filesystem sessions)
```bash
SESSION_BACKEND=filesystem
SESSION_TYPE=filesystem
```

### For Production Runtime (Redis sessions)
```bash
SESSION_BACKEND=redis
REDIS_URL=rediss://red-d2gudc7diees73duftog:6379
```

## Implementation

### 1. Updated Migration Script
The `scripts/migration_sentry.sh` now includes:
```bash
# Set session configuration for pre-deployment script
export SESSION_BACKEND="${SESSION_BACKEND:-filesystem}"
export SESSION_TYPE="${SESSION_TYPE:-filesystem}"
```

### 2. Improved Pre-Deployment Script
The new `scripts/predeploy.sh` provides:
- Proper secret loading
- Session configuration setup
- Environment validation
- Clear logging for debugging

## Testing

To test the pre-deployment script locally:
```bash
# Test with filesystem sessions (pre-deployment mode)
SESSION_BACKEND=filesystem SESSION_TYPE=filesystem bash scripts/migration_sentry.sh

# Test with Redis sessions (production mode)
SESSION_BACKEND=redis REDIS_URL=redis://red-d2gudc7diees73duftog:6379 bash scripts/migration_sentry.sh
```

## Deployment Checklist

- [ ] Use `bash scripts/predeploy.sh` as the pre-deployment command
- [ ] Ensure `SESSION_BACKEND=redis` is set in production environment
- [ ] Ensure `REDIS_URL=redis://red-d2gudc7diees73duftog:6379` is set in production environment
- [ ] Verify that secrets are properly loaded from `/etc/secrets/mdraft-web`

## Expected Behavior

### Pre-Deployment
- Uses filesystem sessions for database migrations
- No Redis connection attempts
- Fast, reliable migration execution

### Production Runtime
- Uses Redis sessions for user sessions
- Proper connection to `rediss://red-d2gudc7diees73duftog:6379`
- Full session functionality with Redis backend
