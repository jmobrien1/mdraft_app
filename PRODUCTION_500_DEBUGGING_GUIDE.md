# Production 500 Error Debugging Guide

## CRITICAL PRODUCTION BUG: 500 Internal Server Error

### Situation Summary
- ✅ Local testing shows app creates successfully and view function executes
- ❌ Production deployment on Render returns 500 Internal Server Error
- ❌ No visible error logs in production
- ✅ Health check endpoints work fine
- ❌ Homepage (/) fails with 500 error

## Root Cause Analysis

### Most Likely Causes (in order of probability)

1. **Gunicorn Worker Process Crashes**
   - Preload issues with complex app initialization
   - Memory issues during app creation
   - Import path problems with PYTHONPATH=/opt/render/project/src

2. **Environment Variable Issues**
   - Trailing whitespace in Redis URLs
   - Missing or malformed DATABASE_URL
   - Incorrect SECRET_KEY format

3. **Flask-Limiter Redis Connection Failing**
   - Silent Redis connection failures in production
   - Upstash Redis URL scheme issues (redis:// vs rediss://)
   - Network connectivity problems

4. **Database Connection Issues**
   - PostgreSQL connection pool exhaustion
   - Invalid DATABASE_URL format
   - Network connectivity to Google Cloud SQL

5. **Template Loading Issues**
   - Template path resolution problems in production
   - Missing template files
   - File permission issues

## Immediate Debugging Steps

### Step 1: Run Production Debug Script
```bash
# On Render, run this script to get detailed diagnostics
bash scripts/production_debug.sh
```

### Step 2: Check Render Logs
```bash
# In Render dashboard, check:
# 1. Build logs for import errors
# 2. Runtime logs for application errors
# 3. Health check logs for startup issues
```

### Step 3: Test Minimal Routes
Visit these URLs to isolate the issue:
- `https://mdraft.onrender.com/test` - Minimal test route
- `https://mdraft.onrender.com/debug` - App state information
- `https://mdraft.onrender.com/health/simple` - Health check

### Step 4: Environment Variable Validation
Check these critical environment variables in Render dashboard:
- `DATABASE_URL` - Must be valid PostgreSQL URL
- `SECRET_KEY` - Must be set and non-empty
- `REDIS_URL` - Check for trailing whitespace
- `SESSION_REDIS_URL` - Check for trailing whitespace
- `FLASK_LIMITER_STORAGE_URI` - Check for trailing whitespace

## Specific Fixes Applied

### 1. Enhanced Gunicorn Configuration
- Created `gunicorn.conf.py` with proper error handling
- Added comprehensive logging and worker management
- Fixed preload app issues

### 2. Improved Error Logging
- Added detailed 500 error handler in `app/__init__.py`
- Enhanced exception logging with full tracebacks
- Added request context logging

### 3. Minimal Test Routes
- Added `/test` route for basic functionality testing
- Added `/debug` route for app state inspection
- Simplified homepage route to isolate template issues

### 4. Production Debugging Tools
- Created `debug_production_500.py` for local debugging
- Created `scripts/production_debug.sh` for Render debugging
- Enhanced startup validation

## Deployment Configuration Changes

### Updated render.yaml
```yaml
startCommand: gunicorn --config gunicorn.conf.py wsgi:app
```

### Environment Variables to Check
```bash
FLASK_ENV=production
FLASK_DEBUG=0
PYTHONPATH=/opt/render/project/src
GUNICORN_CMD_ARGS="--preload --access-logfile -"
```

## Step-by-Step Resolution Process

### Phase 1: Immediate Diagnostics
1. Deploy the updated code with enhanced logging
2. Run `bash scripts/production_debug.sh` on Render
3. Check Render logs for detailed error messages
4. Test minimal routes (`/test`, `/debug`)

### Phase 2: Environment Fixes
1. Validate all environment variables in Render dashboard
2. Remove any trailing whitespace from Redis URLs
3. Ensure DATABASE_URL is properly formatted
4. Verify SECRET_KEY is set and valid

### Phase 3: Configuration Optimization
1. If Redis issues persist, temporarily disable Redis sessions
2. If database issues persist, check connection pool settings
3. If template issues persist, verify template file paths

### Phase 4: Gradual Feature Re-enablement
1. Start with minimal homepage route
2. Gradually re-enable template rendering
3. Re-enable Redis sessions
4. Re-enable complex features

## Common Production Issues and Solutions

### Issue: Redis Connection Failures
**Symptoms:** Silent failures, no error logs
**Solution:** 
```python
# In app/__init__.py, add Redis connection testing
try:
    redis_client.ping()
    app.logger.info("Redis connection successful")
except Exception as e:
    app.logger.error(f"Redis connection failed: {e}")
    # Fall back to filesystem sessions
```

### Issue: Database Connection Pool Exhaustion
**Symptoms:** Connection timeouts, worker crashes
**Solution:**
```python
# Optimize SQLAlchemy pool settings
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 5,
    "pool_recycle": 1800,
    "pool_timeout": 30,
}
```

### Issue: Template Loading Problems
**Symptoms:** 500 errors on template rendering
**Solution:**
```python
# Add template path debugging
app.logger.info(f"Template folder: {app.template_folder}")
app.logger.info(f"Template files: {os.listdir(app.template_folder)}")
```

### Issue: Import Path Problems
**Symptoms:** ModuleNotFoundError in production
**Solution:**
```python
# Ensure proper PYTHONPATH
import sys
sys.path.insert(0, '/opt/render/project/src')
```

## Monitoring and Prevention

### Health Check Endpoints
- `/health/simple` - Basic health check
- `/test` - Minimal functionality test
- `/debug` - App state inspection

### Logging Strategy
- Structured logging with request IDs
- Error tracking with full tracebacks
- Performance monitoring with timing data

### Deployment Validation
- Pre-deployment validation scripts
- Post-deployment health checks
- Automated rollback on failures

## Emergency Rollback Plan

If the issue persists after all fixes:

1. **Temporary Fix:** Disable complex features
   ```python
   # In app/ui.py, use minimal response
   @bp.route("/")
   def index():
       return "<h1>Maintenance Mode</h1>"
   ```

2. **Database Fallback:** Use SQLite for testing
   ```python
   # Temporarily use SQLite
   DATABASE_URL = "sqlite:///temp.db"
   ```

3. **Session Fallback:** Use filesystem sessions
   ```python
   # Disable Redis sessions
   SESSION_BACKEND = "filesystem"
   ```

## Success Criteria

The issue is resolved when:
- ✅ Homepage (/) returns 200 OK
- ✅ No 500 errors in production logs
- ✅ All health checks pass
- ✅ Application functions normally

## Next Steps

1. Deploy the updated code with enhanced debugging
2. Run the production debug script
3. Check Render logs for specific error messages
4. Apply targeted fixes based on diagnostic results
5. Gradually re-enable features once basic functionality works

## Contact Information

For additional support:
- Check Render documentation for deployment issues
- Review Flask-Gunicorn integration best practices
- Consult Google Cloud SQL connection troubleshooting
