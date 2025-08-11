# Deploying mdraft Worker Service

This document provides step-by-step instructions for deploying the mdraft worker service to Google Cloud Run.

## Prerequisites

- Google Cloud CLI (`gcloud`) installed and authenticated
- Project with billing enabled
- Required APIs enabled (Cloud Run, Cloud Tasks, Cloud Storage, Document AI)

## 1. Set Environment Variables

```bash
export PROJECT="your-project-id"
export REGION="us-central1"
export WORKER_SERVICE="mdraft-worker"
export WEB_SERVICE="mdraft-web"
```

## 2. Create Service Accounts

### Create Worker Service Account (Runtime)

```bash
# Create service account for worker runtime
gcloud iam service-accounts create mdraft-worker \
  --display-name="mdraft Worker Service Account" \
  --description="Service account for mdraft worker service runtime"

# Grant necessary roles for worker
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-worker@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/cloudtasks.taskRunner"

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-worker@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-worker@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-worker@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"
```

### Create Web Service Account (Enqueuer)

```bash
# Create service account for web service
gcloud iam service-accounts create mdraft-web \
  --display-name="mdraft Web Service Account" \
  --description="Service account for mdraft web service"

# Grant necessary roles for web service
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-web@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-web@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:mdraft-web@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

## 3. Deploy Worker Service

```bash
# Deploy worker service to Cloud Run
gcloud run deploy ${WORKER_SERVICE} \
  --source . \
  --entry-point create_worker_app \
  --region ${REGION} \
  --no-allow-unauthenticated \
  --service-account mdraft-worker@${PROJECT}.iam.gserviceaccount.com \
  --set-env-vars="WORKER_SERVICE=true" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT}" \
  --set-env-vars="CLOUD_TASKS_LOCATION=${REGION}" \
  --set-env-vars="GCS_PROCESSED_BUCKET_NAME=mdraft-processed-${PROJECT}" \
  --set-env-vars="PRO_CONVERSION_ENABLED=false" \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10 \
  --timeout 900
```

## 4. Grant Invoker Permission

```bash
# Grant web service account permission to invoke worker
gcloud run services add-iam-policy-binding ${WORKER_SERVICE} \
  --region ${REGION} \
  --member="serviceAccount:mdraft-web@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

## 5. Bootstrap Cloud Tasks Queue

```bash
# Create queue (idempotent - safe to run multiple times)
gcloud tasks queues create mdraft-conversion-queue \
  --location=${REGION} \
  --max-concurrent-dispatches=5 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s \
  --max-doublings=5

# Set retry policy
gcloud tasks queues update mdraft-conversion-queue \
  --location=${REGION} \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s \
  --max-doublings=5
```

## 6. Create GCS Buckets

```bash
# Create upload bucket
gsutil mb -l ${REGION} gs://mdraft-uploads-${PROJECT}

# Create processed bucket
gsutil mb -l ${REGION} gs://mdraft-processed-${PROJECT}

# Set bucket permissions
gsutil iam ch serviceAccount:mdraft-web@${PROJECT}.iam.gserviceaccount.com:objectCreator gs://mdraft-uploads-${PROJECT}
gsutil iam ch serviceAccount:mdraft-worker@${PROJECT}.iam.gserviceaccount.com:objectViewer gs://mdraft-uploads-${PROJECT}
gsutil iam ch serviceAccount:mdraft-worker@${PROJECT}.iam.gserviceaccount.com:objectCreator gs://mdraft-processed-${PROJECT}
```

## 7. Configure Environment Variables

Update your `.env` file with the worker service URL:

```bash
# Get the worker service URL
WORKER_URL=$(gcloud run services describe ${WORKER_SERVICE} --region ${REGION} --format="value(status.url)")

echo "WORKER_SERVICE_URL=${WORKER_URL}"
echo "WORKER_INVOKER_SA_EMAIL=mdraft-web@${PROJECT}.iam.gserviceaccount.com"
```

## 8. Verify Deployment

```bash
# Test worker health endpoint
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  ${WORKER_URL}/health

# Expected response: {"status": "ok", "service": "worker"}
```

## 9. Deploy Web Service

```bash
# Deploy web service (assuming you have the web service code)
gcloud run deploy ${WEB_SERVICE} \
  --source . \
  --region ${REGION} \
  --allow-unauthenticated \
  --service-account mdraft-web@${PROJECT}.iam.gserviceaccount.com \
  --set-env-vars="WORKER_SERVICE_URL=${WORKER_URL}" \
  --set-env-vars="WORKER_INVOKER_SA_EMAIL=mdraft-web@${PROJECT}.iam.gserviceaccount.com" \
  --set-env-vars="GCS_BUCKET=mdraft-uploads-${PROJECT}" \
  --set-env-vars="CLOUD_TASKS_QUEUE_ID=mdraft-conversion-queue" \
  --set-env-vars="CLOUD_TASKS_LOCATION=${REGION}"
```

## 10. Test End-to-End

```bash
# Run the validation script
python tools/validate_e2e.py \
  --web-url $(gcloud run services describe ${WEB_SERVICE} --region ${REGION} --format="value(status.url)") \
  --worker-url ${WORKER_URL} \
  --timeout 300
```

## Troubleshooting

### Check Service Logs

```bash
# View worker logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=${WORKER_SERVICE}" --limit=50

# View web service logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=${WEB_SERVICE}" --limit=50
```

### Check IAM Permissions

```bash
# Verify service account permissions
gcloud projects get-iam-policy ${PROJECT} \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:mdraft-worker@${PROJECT}.iam.gserviceaccount.com"
```

### Common Issues

1. **403 Forbidden**: Check service account permissions and IAM bindings
2. **Queue not found**: Ensure Cloud Tasks API is enabled and queue exists
3. **Storage access denied**: Verify bucket permissions and service account roles
4. **Worker not responding**: Check Cloud Run service logs and resource limits

## Security Notes

- Worker service is not publicly accessible (`--no-allow-unauthenticated`)
- Web service can only invoke worker through IAM permissions
- Service accounts have minimal required permissions
- All communication is authenticated and encrypted
