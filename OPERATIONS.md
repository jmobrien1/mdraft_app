# Operations Playbook

This document contains operational procedures for the mdraft application, including rollback procedures, database migrations, and resilience drills.

## Table of Contents

1. [Cloud Run Revision Rollback](#cloud-run-revision-rollback)
2. [Database Migration Rollback](#database-migration-rollback)
3. [Feature Flag Management](#feature-flag-management)
4. [Resilience Drills](#resilience-drills)
5. [Emergency Procedures](#emergency-procedures)

## Cloud Run Revision Rollback

### List Revisions

```bash
# List all revisions for the main application
gcloud run revisions list --service=mdraft --region=us-central1

# List all revisions for the worker service
gcloud run revisions list --service=mdraft-worker --region=us-central1
```

### Rollback to Previous Revision

```bash
# Rollback main application to a specific revision
gcloud run services update-traffic mdraft \
  --to-revisions=mdraft-00001-abc=100 \
  --region=us-central1

# Rollback worker service to a specific revision
gcloud run services update-traffic mdraft-worker \
  --to-revisions=mdraft-worker-00001-xyz=100 \
  --region=us-central1
```

### Rollback to Latest Stable Revision

```bash
# Rollback main application to latest stable revision
gcloud run services update-traffic mdraft \
  --to-revisions=mdraft-00002-def=100 \
  --region=us-central1

# Verify rollback
gcloud run services describe mdraft --region=us-central1 --format="value(status.traffic[0].revisionName)"
```

### Emergency Rollback (All Traffic to Previous Revision)

```bash
# Emergency rollback - send all traffic to previous revision
gcloud run services update-traffic mdraft \
  --to-revisions=mdraft-00001-abc=100 \
  --region=us-central1 \
  --quiet
```

## Database Migration Rollback

### List Migration History

```bash
# Show migration history
flask db history

# Show current migration
flask db current
```

### Rollback to Specific Migration

```bash
# Rollback to a specific migration
flask db downgrade afbc8388791d

# Rollback one step
flask db downgrade -1

# Rollback multiple steps
flask db downgrade -3
```

### Emergency Database Rollback

```bash
# In case of critical database issues, rollback to last known good state
flask db downgrade afbc8388791d

# Verify rollback
flask db current
```

### Production Database Rollback

```bash
# For production, use Cloud SQL Proxy
cloud_sql_proxy -instances=PROJECT_ID:REGION:INSTANCE_NAME=tcp:5432

# Then run rollback
DATABASE_URL=postgresql://user:pass@localhost:5432/db flask db downgrade afbc8388791d
```

## Feature Flag Management

### Disable Pro Conversion (Kill Switch)

```bash
# Disable Document AI processing (emergency kill switch)
gcloud run services update mdraft \
  --set-env-vars PRO_CONVERSION_ENABLED=false \
  --region=us-central1

# Disable for worker service
gcloud run services update mdraft-worker \
  --set-env-vars PRO_CONVERSION_ENABLED=false \
  --region=us-central1
```

### Re-enable Pro Conversion

```bash
# Re-enable Document AI processing
gcloud run services update mdraft \
  --set-env-vars PRO_CONVERSION_ENABLED=true \
  --region=us-central1

# Re-enable for worker service
gcloud run services update mdraft-worker \
  --set-env-vars PRO_CONVERSION_ENABLED=true \
  --region=us-central1
```

### Verify Feature Flag Status

```bash
# Check current environment variables
gcloud run services describe mdraft --region=us-central1 --format="value(spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].value)"
```

## Resilience Drills

### Drill 1: Intentional Error and Rollback

**Objective**: Practice identifying and rolling back from a deployment issue.

**Steps**:

1. **Deploy a "broken" version**:
   ```bash
   # Modify the health check endpoint to return an error
   # In app/routes.py, change the health check to:
   @bp.route("/health", methods=["GET"])
   def health_check() -> Any:
       return jsonify({"status": "error", "message": "Intentional drill error"}), 500
   ```

2. **Deploy the broken version**:
   ```bash
   gcloud run deploy mdraft --source . --region=us-central1
   ```

3. **Verify the error**:
   ```bash
   curl https://mdraft-xxxxx-uc.a.run.app/health
   # Should return error status
   ```

4. **Practice rollback**:
   ```bash
   # List revisions
   gcloud run revisions list --service=mdraft --region=us-central1
   
   # Rollback to previous revision
   gcloud run services update-traffic mdraft \
     --to-revisions=mdraft-00001-abc=100 \
     --region=us-central1
   ```

5. **Verify rollback success**:
   ```bash
   curl https://mdraft-xxxxx-uc.a.run.app/health
   # Should return "ok" status
   ```

6. **Clean up**:
   ```bash
   # Revert the code change
   git checkout app/routes.py
   ```

### Drill 2: Database Migration Rollback

**Objective**: Practice rolling back database schema changes.

**Steps**:

1. **Create a test migration**:
   ```bash
   flask db migrate -m "Test migration for drill"
   ```

2. **Apply the migration**:
   ```bash
   flask db upgrade
   ```

3. **Verify the change**:
   ```bash
   flask db current
   ```

4. **Practice rollback**:
   ```bash
   flask db downgrade -1
   ```

5. **Verify rollback**:
   ```bash
   flask db current
   ```

6. **Clean up**:
   ```bash
   # Remove the test migration file
   rm migrations/versions/xxxxx_test_migration_for_drill.py
   ```

### Drill 3: Feature Flag Kill Switch

**Objective**: Practice using the kill switch to disable expensive operations.

**Steps**:

1. **Verify current state**:
   ```bash
   curl https://mdraft-xxxxx-uc.a.run.app/health
   ```

2. **Activate kill switch**:
   ```bash
   gcloud run services update mdraft \
     --set-env-vars PRO_CONVERSION_ENABLED=false \
     --region=us-central1
   ```

3. **Verify kill switch effect**:
   ```bash
   # Upload a PDF file
   curl -X POST https://mdraft-xxxxx-uc.a.run.app/upload \
     -F "file=@test.pdf"
   
   # Check that it uses markitdown instead of Document AI
   ```

4. **Deactivate kill switch**:
   ```bash
   gcloud run services update mdraft \
     --set-env-vars PRO_CONVERSION_ENABLED=true \
     --region=us-central1
   ```

5. **Verify restoration**:
   ```bash
   # Upload another PDF and verify Document AI is used
   ```

## Emergency Procedures

### Service Down Emergency

1. **Check service status**:
   ```bash
   gcloud run services describe mdraft --region=us-central1
   ```

2. **Check logs**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=mdraft" --limit=50
   ```

3. **Emergency rollback**:
   ```bash
   gcloud run services update-traffic mdraft \
     --to-revisions=mdraft-00001-abc=100 \
     --region=us-central1
   ```

### Database Emergency

1. **Check database connectivity**:
   ```bash
   gcloud sql instances describe INSTANCE_NAME
   ```

2. **Emergency rollback**:
   ```bash
   flask db downgrade afbc8388791d
   ```

3. **Verify data integrity**:
   ```bash
   flask db current
   ```

### Cost Emergency

1. **Activate kill switch**:
   ```bash
   gcloud run services update mdraft \
     --set-env-vars PRO_CONVERSION_ENABLED=false \
     --region=us-central1
   
   gcloud run services update mdraft-worker \
     --set-env-vars PRO_CONVERSION_ENABLED=false \
     --region=us-central1
   ```

2. **Scale down services**:
   ```bash
   gcloud run services update mdraft \
     --max-instances=1 \
     --region=us-central1
   
   gcloud run services update mdraft-worker \
     --max-instances=1 \
     --region=us-central1
   ```

## Monitoring and Alerting

### Health Check Monitoring

```bash
# Set up monitoring for health check endpoint
gcloud monitoring uptime-checks create http mdraft-health \
  --uri=https://mdraft-xxxxx-uc.a.run.app/health \
  --display-name="mdraft Health Check"
```

### Cost Monitoring

```bash
# Set up billing alerts
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="mdraft Budget Alert" \
  --budget-amount=100USD \
  --threshold-rule=percent=0.5
```

### Log Monitoring

```bash
# Create log-based metrics for errors
gcloud logging metrics create mdraft-errors \
  --description="mdraft application errors" \
  --log-filter="resource.type=cloud_run_revision AND severity>=ERROR"
```

## Recovery Procedures

### Full Service Recovery

1. **Stop all traffic**:
   ```bash
   gcloud run services update-traffic mdraft \
     --to-revisions=mdraft-00000-initial=0 \
     --region=us-central1
   ```

2. **Deploy known good version**:
   ```bash
   gcloud run deploy mdraft \
     --image gcr.io/PROJECT_ID/mdraft:KNOWN_GOOD_TAG \
     --region=us-central1
   ```

3. **Gradually restore traffic**:
   ```bash
   gcloud run services update-traffic mdraft \
     --to-revisions=mdraft-00001-good=10 \
     --region=us-central1
   ```

4. **Monitor and increase traffic**:
   ```bash
   gcloud run services update-traffic mdraft \
     --to-revisions=mdraft-00001-good=100 \
     --region=us-central1
   ```

### Data Recovery

1. **Restore from backup** (if available):
   ```bash
   gcloud sql instances restore-backup INSTANCE_NAME BACKUP_ID
   ```

2. **Rollback to last known good migration**:
   ```bash
   flask db downgrade KNOWN_GOOD_REVISION
   ```

3. **Verify data integrity**:
   ```bash
   flask db current
   # Run data validation queries
   ```

## Contact Information

- **On-call Engineer**: [Contact Information]
- **Escalation Manager**: [Contact Information]
- **Emergency Contact**: [Contact Information]

## Post-Incident Review

After any incident or drill:

1. **Document the incident** in the incident log
2. **Review the response** with the team
3. **Update procedures** based on lessons learned
4. **Schedule follow-up drills** to practice improvements
