# Tools

This directory contains utility scripts for the mdraft application.

## Bootstrap Tasks

The `bootstrap_tasks.py` script ensures that the required Cloud Tasks queue exists with proper configuration.

### Prerequisites

1. **Google Cloud Project**: You need a Google Cloud project with Cloud Tasks API enabled
2. **Service Account**: A service account with the following roles:
   - Cloud Tasks Admin
   - Cloud Tasks Queue Admin
3. **Authentication**: Set up authentication using one of:
   - Service account key file: `export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`
   - Application Default Credentials: `gcloud auth application-default login`

### Environment Variables

```bash
# Required
GOOGLE_CLOUD_PROJECT=your-project-id

# Optional (with defaults)
CLOUD_TASKS_LOCATION=us-central1
CLOUD_TASKS_QUEUE_NAME=mdraft-conversion-queue
```

### Usage

```bash
# Basic usage
python tools/bootstrap_tasks.py

# With custom project
GOOGLE_CLOUD_PROJECT=my-project python tools/bootstrap_tasks.py

# With all custom settings
GOOGLE_CLOUD_PROJECT=my-project \
CLOUD_TASKS_LOCATION=us-central1 \
CLOUD_TASKS_QUEUE_NAME=my-queue \
python tools/bootstrap_tasks.py
```

### Expected Output

**Success (queue exists):**
```
🚀 Bootstrapping Cloud Tasks queue for mdraft...
2025-08-10 19:45:34,767 - INFO - Ensuring queue 'mdraft-conversion-queue' exists in project 'my-project' at location 'us-central1'
2025-08-10 19:45:35,123 - INFO - Queue 'mdraft-conversion-queue' already exists
2025-08-10 19:45:35,124 - INFO - Queue retry config: max_attempts=5, min_backoff=20s, max_backoff=600s
✅ Queue bootstrap completed successfully
```

**Success (queue created):**
```
🚀 Bootstrapping Cloud Tasks queue for mdraft...
2025-08-10 19:45:34,767 - INFO - Ensuring queue 'mdraft-conversion-queue' exists in project 'my-project' at location 'us-central1'
2025-08-10 19:45:35,123 - INFO - Queue 'mdraft-conversion-queue' not found, creating...
2025-08-10 19:45:35,456 - INFO - Successfully created queue 'mdraft-conversion-queue'
2025-08-10 19:45:35,457 - INFO - Queue retry config: max_attempts=5, min_backoff=20s, max_backoff=600s
✅ Queue bootstrap completed successfully
```

**Error (missing project):**
```
🚀 Bootstrapping Cloud Tasks queue for mdraft...
❌ Missing required environment variables: GOOGLE_CLOUD_PROJECT

Required environment variables:
  GOOGLE_CLOUD_PROJECT - Your Google Cloud project ID
  CLOUD_TASKS_LOCATION - Cloud Tasks location (default: us-central1)
  CLOUD_TASKS_QUEUE_NAME - Queue name (default: mdraft-conversion-queue)

Example usage:
  GOOGLE_CLOUD_PROJECT=my-project python tools/bootstrap_tasks.py
```

**Error (permission denied):**
```
🚀 Bootstrapping Cloud Tasks queue for mdraft...
2025-08-10 19:45:34,767 - INFO - Ensuring queue 'mdraft-conversion-queue' exists in project 'my-project' at location 'us-central1'
2025-08-10 19:45:35,968 - ERROR - Permission denied. Ensure the service account has 'Cloud Tasks Admin' role
❌ Queue bootstrap failed
```

### Queue Configuration

The script creates a queue with the following configuration:

- **Rate Limits**:
  - Max concurrent dispatches: 100
  - Max dispatches per second: 500
- **Retry Configuration**:
  - Max attempts: 5
  - Min backoff: 20 seconds
  - Max backoff: 600 seconds (10 minutes)
  - Max doublings: 3

### Troubleshooting

1. **Permission Denied**: Ensure your service account has the `Cloud Tasks Admin` role
2. **Project Not Found**: Verify the project ID is correct and you have access to it
3. **API Not Enabled**: Enable the Cloud Tasks API in your Google Cloud project
4. **Authentication Issues**: Set up proper authentication using `gcloud auth application-default login` or service account key

### Integration

The bootstrap script is automatically called during application startup, but you can also run it manually to ensure the queue exists before deploying your application.
