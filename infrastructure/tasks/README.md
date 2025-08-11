# Cloud Tasks Infrastructure

This directory contains configuration and documentation for Google Cloud Tasks queue management for the mdraft application.

## Queue Configuration

The mdraft application uses a Cloud Tasks queue named `mdraft-conversion-queue` to handle document conversion tasks asynchronously.

### Queue Settings

- **Name**: `mdraft-conversion-queue`
- **Location**: `us-central1`
- **Max Attempts**: 5
- **Min Backoff**: 20 seconds
- **Max Backoff**: 600 seconds (10 minutes)
- **Max Concurrent Dispatches**: 100
- **Max Dispatches Per Second**: 500

## Queue Management Commands

### Update Queue Retry Policy

```bash
gcloud tasks queues update mdraft-conversion-queue \
  --location=us-central1 \
  --max-attempts=5 \
  --min-backoff=20s \
  --max-backoff=600s \
  --max-doublings=3
```

### Describe Queue Configuration

```bash
gcloud tasks queues describe mdraft-conversion-queue \
  --location=us-central1
```

### List All Queues

```bash
gcloud tasks queues list \
  --location=us-central1
```

### Delete Queue (if needed)

```bash
gcloud tasks queues delete mdraft-conversion-queue \
  --location=us-central1
```

## Task Structure

Tasks sent to the queue have the following structure:

```json
{
  "http_request": {
    "http_method": "POST",
    "url": "https://mdraft-worker-xxxxx-uc.a.run.app/tasks/process-document",
    "headers": {
      "Content-Type": "application/json"
    },
    "oidc_token": {
      "service_account_email": "mdraft-invoker@PROJECT_ID.iam.gserviceaccount.com",
      "audience": "https://mdraft-worker-xxxxx-uc.a.run.app"
    },
    "body": "{\"job_id\": 123, \"user_id\": 456, \"gcs_uri\": \"gs://bucket/path/file.pdf\"}"
  },
  "dispatch_deadline": {
    "seconds": 3600
  }
}
```

## Service Account Requirements

The following service accounts are required:

1. **mdraft-invoker@PROJECT_ID.iam.gserviceaccount.com**
   - Used by Cloud Tasks to invoke the worker service
   - Requires `roles/run.invoker` on the worker service

2. **mdraft-worker@PROJECT_ID.iam.gserviceaccount.com**
   - Used by the worker service
   - Requires access to Cloud Storage, Document AI, and Cloud SQL

## Environment Variables

The following environment variables must be set for Cloud Tasks integration:

```bash
# Cloud Tasks Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
CLOUD_TASKS_QUEUE_NAME=mdraft-conversion-queue
CLOUD_TASKS_LOCATION=us-central1

# Worker Service Configuration
WORKER_SERVICE_URL=https://mdraft-worker-xxxxx-uc.a.run.app
WORKER_INVOKER_SA_EMAIL=mdraft-invoker@your-project-id.iam.gserviceaccount.com
```

## Monitoring and Debugging

### View Queue Metrics

```bash
gcloud tasks queues describe mdraft-conversion-queue \
  --location=us-central1 \
  --format="value(name,rateLimits,retryConfig)"
```

### View Task Logs

Tasks are logged in Cloud Logging with the following filter:

```
resource.type="cloud_tasks_queue"
resource.labels.queue_id="mdraft-conversion-queue"
```

### Common Issues

1. **Task Dispatch Failures**: Check worker service health and authentication
2. **High Retry Rates**: Monitor worker service performance and resource usage
3. **Queue Backlog**: Scale worker service or increase queue capacity

## Security Considerations

- Worker service is deployed with `--no-allow-unauthenticated`
- Tasks use OIDC tokens for authentication
- Service accounts have minimal required permissions
- Queue access is restricted to authorized services only
