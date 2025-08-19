# Immediate Deployment Guide - mdraft Application

## 🚨 CRITICAL: Production Deployment Required

This guide provides the exact steps to fix the three blockers preventing the mdraft application from functioning in production.

## Quick Fix Summary

1. **Install PDF dependency** → Fix 503 errors on `/api/convert`
2. **Apply database schema fix** → Fix 500 errors on `/api/agents/compliance-matrix/proposals`
3. **Validate deployment** → Ensure everything works

## Step-by-Step Deployment

### Step 1: Install PDF Dependency

```bash
# Install the critical PDF processing library
pip install pdfminer.six==20231228

# Verify installation
python3 -c "
from pdfminer.high_level import extract_text
print('✅ pdfminer.six available')
"
```

### Step 2: Apply Database Schema Fix

```bash
# Run the comprehensive database fix script
psql $DATABASE_URL -f scripts/fix_ingestion_columns.sql
```

**Alternative**: If you prefer to use the deployment script:
```bash
./scripts/deploy_with_migrations.sh
```

### Step 3: Validate the Fixes

```bash
# Run comprehensive validation
python scripts/validate_deployment_fixes.py
```

## Expected Results

### Before Fixes
- ❌ `/api/convert` → 503 "No PDF backend available"
- ❌ `/api/agents/compliance-matrix/proposals` → 500 UndefinedColumn
- ❌ PDF processing completely broken

### After Fixes
- ✅ `/api/convert` → 200 (or appropriate status, not 503)
- ✅ `/api/agents/compliance-matrix/proposals` → 200 with data
- ✅ PDF text extraction working correctly

## Verification Commands

### Test PDF Backend
```bash
python3 -c "
from app.services.pdf_backend import validate_pdf_backend
backend = validate_pdf_backend()
print(f'PDF Backend: {backend[\"backend\"]}')
print(f'Available: {backend[\"available\"]}')
"
```

### Test Database Schema
```bash
python3 -c "
from sqlalchemy import create_engine, text
engine = create_engine('$DATABASE_URL')
with engine.connect() as conn:
    result = conn.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name = \\'proposal_documents\\' AND column_name = \\'ingestion_status\\''))
    if result.fetchone():
        print('✅ ingestion_status column exists')
    else:
        print('❌ ingestion_status column missing')
"
```

### Test API Endpoints
```bash
# Test health endpoint
curl -s http://localhost:5000/health | jq .

# Test convert endpoint (should not return 503)
curl -s http://localhost:5000/api/convert | jq .

# Test proposals endpoint (should not return 500)
curl -s http://localhost:5000/api/agents/compliance-matrix/proposals | jq .
```

## Troubleshooting

### If PDF Backend Still Not Available
```bash
# Check what's installed
pip list | grep pdfminer

# Reinstall with force
pip install --force-reinstall pdfminer.six==20231228
```

### If Database Fix Fails
```bash
# Check database connection
psql $DATABASE_URL -c "SELECT version();"

# Check if table exists
psql $DATABASE_URL -c "SELECT table_name FROM information_schema.tables WHERE table_name = 'proposal_documents';"

# Manual column addition if needed
psql $DATABASE_URL -c "ALTER TABLE proposal_documents ADD COLUMN IF NOT EXISTS ingestion_status TEXT NOT NULL DEFAULT 'none';"
```

### If Validation Script Fails
```bash
# Run individual tests
python3 -c "from app.services.pdf_backend import validate_pdf_backend; print(validate_pdf_backend())"
python3 -c "from sqlalchemy import create_engine; print('DB connection OK')"
```

## Rollback Plan

If something goes wrong:

1. **Revert PDF dependency**:
   ```bash
   pip uninstall pdfminer.six
   ```

2. **Revert database changes** (if needed):
   ```bash
   psql $DATABASE_URL -c "ALTER TABLE proposal_documents DROP COLUMN IF EXISTS ingestion_status;"
   psql $DATABASE_URL -c "ALTER TABLE proposal_documents DROP COLUMN IF EXISTS available_sections;"
   psql $DATABASE_URL -c "ALTER TABLE proposal_documents DROP COLUMN IF EXISTS ingestion_error;"
   ```

## Success Criteria

The deployment is successful when:

1. ✅ Application starts without errors
2. ✅ `/health` endpoint returns 200
3. ✅ `/api/convert` does NOT return 503
4. ✅ `/api/agents/compliance-matrix/proposals` does NOT return 500
5. ✅ PDF text extraction works (test with a sample PDF)
6. ✅ All validation tests pass

## Next Steps After Deployment

1. **Monitor logs** for any remaining issues
2. **Test full workflow** with actual document uploads
3. **Update requirements.txt** for future deployments
4. **Document any issues** encountered during deployment

## Support

If you encounter issues:

1. Check the logs: `tail -f /var/log/application.log`
2. Run validation: `python scripts/validate_deployment_fixes.py`
3. Check system resources: `df -h && free -h`
4. Verify environment variables: `env | grep -E "(DATABASE|PDF)"`

---

**Note**: This deployment addresses the critical blockers. The application should be fully functional after these steps.
