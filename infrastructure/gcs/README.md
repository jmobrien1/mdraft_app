# Google Cloud Storage Lifecycle Management

This directory contains configuration files and commands for managing GCS bucket lifecycle policies.

## Lifecycle Policy

The `lifecycle.json` file defines a lifecycle policy that automatically deletes objects older than 30 days. This helps manage storage costs and maintain data hygiene.

## Commands

### Apply Lifecycle Policy

To apply the lifecycle policy to your GCS buckets:

```bash
# Apply to uploads bucket
gcloud storage buckets update gs://$GCS_BUCKET_NAME --lifecycle-file=infrastructure/gcs/lifecycle.json

# Apply to processed bucket  
gcloud storage buckets update gs://$GCS_PROCESSED_BUCKET_NAME --lifecycle-file=infrastructure/gcs/lifecycle.json
```

### Rollback Lifecycle Policy

To remove the lifecycle policy (clear all lifecycle rules):

```bash
# Clear lifecycle policy from uploads bucket
gcloud storage buckets update gs://$GCS_BUCKET_NAME --clear-lifecycle

# Clear lifecycle policy from processed bucket
gcloud storage buckets update gs://$GCS_PROCESSED_BUCKET_NAME --clear-lifecycle
```

### Check Current Lifecycle Policy

To view the current lifecycle policy on a bucket:

```bash
gcloud storage buckets describe gs://$BUCKET_NAME --format="value(lifecycle.rule)"
```

## Environment Variables

Make sure these environment variables are set:

```bash
export GCS_BUCKET_NAME="mdraft-uploads"
export GCS_PROCESSED_BUCKET_NAME="mdraft-processed"
```

## Notes

- The lifecycle policy deletes objects after 30 days
- This affects both upload and processed buckets
- Use the rollback command to disable automatic deletion
- Consider your data retention requirements before applying
