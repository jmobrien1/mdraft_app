# Environment Configuration

This document describes all environment variables required for the mdraft application.

## Required Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/mdraft

# Google Cloud Storage Configuration
GCS_BUCKET=mdraft-uploads-your-project-id
GCS_PROCESSED_BUCKET_NAME=mdraft-processed-your-project-id

# Google Cloud Tasks Configuration
CLOUD_TASKS_QUEUE_ID=mdraft-conversion-queue
CLOUD_TASKS_LOCATION=us-central1

# Worker Service Configuration
WORKER_SERVICE_URL=https://mdraft-worker-your-project-id-uc.a.run.app
WORKER_INVOKER_SA_EMAIL=mdraft-web@your-project-id.iam.gserviceaccount.com

# Document AI Configuration
DOCAI_PROCESSOR_ID=your-docai-processor-id
DOCAI_LOCATION=us

# Conversion Engine Configuration
PRO_CONVERSION_ENABLED=false

# Application Configuration
SECRET_KEY=your-secret-key-here
WORKER_SERVICE=false

# Google Cloud Project
GOOGLE_CLOUD_PROJECT=your-project-id

# Sentry Configuration (Optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

## Variable Descriptions

### Database
- `DATABASE_URL`: PostgreSQL connection string for the application database

### Google Cloud Storage
- `GCS_BUCKET`: Bucket name for storing uploaded files
- `GCS_PROCESSED_BUCKET_NAME`: Bucket name for storing processed/converted files

### Google Cloud Tasks
- `CLOUD_TASKS_QUEUE_ID`: Queue ID for document conversion tasks
- `CLOUD_TASKS_LOCATION`: GCP region for Cloud Tasks (e.g., us-central1)

### Worker Service
- `WORKER_SERVICE_URL`: Full URL of the deployed worker service
- `WORKER_INVOKER_SA_EMAIL`: Service account email that can invoke the worker

### Document AI
- `DOCAI_PROCESSOR_ID`: Document AI processor ID for PDF processing
- `DOCAI_LOCATION`: GCP region for Document AI (e.g., us)

### Conversion Engine
- `PRO_CONVERSION_ENABLED`: Enable/disable Document AI processing (true/false)

### Application
- `SECRET_KEY`: Flask secret key for session management
- `WORKER_SERVICE`: Set to true when running as worker service

### Google Cloud
- `GOOGLE_CLOUD_PROJECT`: GCP project ID

### Monitoring
- `SENTRY_DSN`: Sentry DSN for error tracking (optional)

## Environment-Specific Configurations

### Development
```bash
WORKER_SERVICE=false
PRO_CONVERSION_ENABLED=false
DATABASE_URL=sqlite:///mdraft_local.db
```

### Production (Web Service)
```bash
WORKER_SERVICE=false
PRO_CONVERSION_ENABLED=true
WORKER_SERVICE_URL=https://mdraft-worker-your-project-id-uc.a.run.app
WORKER_INVOKER_SA_EMAIL=mdraft-web@your-project-id.iam.gserviceaccount.com
```

### Production (Worker Service)
```bash
WORKER_SERVICE=true
PRO_CONVERSION_ENABLED=true
GCS_PROCESSED_BUCKET_NAME=mdraft-processed-your-project-id
```

## Getting Values

### Worker Service URL
```bash
gcloud run services describe mdraft-worker --region us-central1 --format="value(status.url)"
```

### Service Account Email
```bash
echo "mdraft-web@$(gcloud config get-value project).iam.gserviceaccount.com"
```

### Project ID
```bash
gcloud config get-value project
```
