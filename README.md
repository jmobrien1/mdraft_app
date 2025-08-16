# mdraft - Document to Markdown Conversion SaaS

A Flask-based SaaS application that converts documents (PDF, DOCX) to Markdown format using Google Cloud services.

## Features

- **Document Upload**: Secure file upload with MIME-type validation
- **Multiple Conversion Engines**: 
  - Open-source markitdown for standard documents
  - Google Document AI for scanned documents and OCR
- **Background Processing**: Asynchronous job processing with status tracking
- **Google Cloud Integration**: 
  - Cloud Storage for file management with streaming uploads
  - Cloud Tasks for background job processing
  - Document AI for advanced text extraction
  - V4 signed URLs for secure downloads
- **RESTful API**: Clean JSON API for integration
- **Rate Limiting**: Built-in protection against abuse
- **Database Migrations**: Alembic-based schema management
- **Production Ready**: Structured logging, error handling, and security features

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │   Flask App     │    │  Background     │
│                 │    │                 │    │   Workers       │
│ Upload Document │───▶│ Create Job      │───▶│ Process Job     │
│ Check Status    │◀───│ Return Job ID   │    │ Convert File    │
│ Download Result │◀───│ Return Status   │    │ Update Status   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │  Google Cloud   │
                       │   Database      │    │   Services      │
                       │                 │    │                 │
                       │ Store Job Info  │    │ Document AI     │
                       │ Track Status    │    │ Cloud Storage   │
                       │ User Data       │    │ Cloud Tasks     │
                       └─────────────────┘    └─────────────────┘
```

## Tech Stack

- **Backend**: Python 3.8+, Flask 3.0
- **Database**: PostgreSQL (production), SQLite (development)
- **ORM**: SQLAlchemy with Alembic migrations
- **Cloud Services**: Google Cloud Platform
  - Cloud SQL (PostgreSQL)
  - Cloud Storage (with streaming uploads)
  - Cloud Tasks
  - Document AI
- **Security**: Flask-Bcrypt, rate limiting, V4 signed URLs
- **File Processing**: filetype, subprocess

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Google Cloud Platform account (for production features)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mdraft_app
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Install production dependencies
   pip install -r requirements.txt
   
   # Or install development dependencies (includes testing and security tools)
   pip install -r requirements-dev.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize the database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   python run.py
   ```

## Build Engineering & Security

### Dependency Management with pip-tools

This project uses `pip-tools` for reliable dependency management:

```bash
# Lock production dependencies (generates requirements.txt with exact versions)
make lock

# Lock development dependencies (generates requirements-dev.txt with exact versions)
make lock-dev

# Install development tools
make install-dev
```

### Security Scanning

Regular security scanning is integrated into the build process:

```bash
# Run comprehensive security scan
make security-scan

# Or run the security script directly
./scripts/security_scan.sh
```

The security scan includes:
- **pip-audit**: Vulnerability scanning using the Python Packaging Authority database
- **safety**: Additional security checks using the Safety database
- **Compatibility checks**: Celery/Redis version compatibility validation
- **Package pinning verification**: Ensures security-critical packages are pinned

### Build Validation

Validate that your build environment is properly configured:

```bash
# Run build validation
make build-validate
```

This checks:
- ✅ Celery/Redis compatibility
- ✅ Security-critical package pinning (itsdangerous, Werkzeug)
- ✅ Google Cloud package availability
- ✅ All required dependencies are accessible

### Security Reports

Security scans generate detailed reports:
- `pip-audit-report.json`: Detailed vulnerability findings
- `safety-report.json`: Additional security analysis

**Acceptance Criteria:**
- ✅ App builds clean without errors
- ✅ pip-audit shows no high/critical vulnerabilities
- ✅ Celery/Redis versions are compatible
- ✅ All Google Cloud packages are available

The application will be available at `http://localhost:5000`

## Deployment

### Render Deployment

The application is configured for deployment on Render with the following features:

#### Pre-Deploy Migration
- **Script**: `scripts/migration_sentry.sh`
- **Action**: Runs `flask db upgrade` before serving
- **Features**: 
  - Database connectivity check
  - Alembic migration execution
  - Schema validation
  - Auto-repair for migration issues

#### Health Checks
- **Endpoint**: `/health` - Lightweight health check
- **Response**: `{"status": "ok"}`
- **Use**: Load balancer health checks, basic monitoring

#### Smoke Testing
Two smoke test options are available:

**Python Smoke Test (Comprehensive):**
```bash
# Set environment variables
export SMOKE_TEST_URL="https://your-app.onrender.com"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="your-password"

# Run full end-to-end test
python scripts/smoke_test.py
```

**Shell Smoke Test (Basic):**
```bash
# Set environment variables
export SMOKE_TEST_URL="https://your-app.onrender.com"

# Run basic connectivity test
./scripts/smoke_test.sh
```

#### Deployment Checklist
- [ ] Database migrations run successfully
- [ ] Health check endpoint returns `{"status": "ok"}`
- [ ] Session cookies configured for HTTPS
- [ ] Rate limiting enabled
- [ ] Authentication required (`MDRAFT_PUBLIC_MODE=0`)
- [ ] Smoke test passes
- [ ] Worker service (if used) responds to ping

### Environment Configuration

Copy `.env.example` to `.env` and configure the following variables:

#### Required for Local Development
```bash
SECRET_KEY=your-super-secret-key
FLASK_DEBUG=1
DATABASE_URL=sqlite:///mdraft_local.db
```

#### Required for Production (Google Cloud)
```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# Google Cloud Storage
GCS_BUCKET_NAME=mdraft-uploads
GCS_PROCESSED_BUCKET_NAME=mdraft-processed

# Google Cloud Tasks
CLOUD_TASKS_QUEUE_NAME=mdraft-conversion-queue
CLOUD_TASKS_LOCATION=us-central1

# Worker Service Configuration
WORKER_SERVICE_URL=https://mdraft-worker-xxxxx-uc.a.run.app
WORKER_INVOKER_SA_EMAIL=mdraft-invoker@your-project-id.iam.gserviceaccount.com

# Google Document AI
DOCAI_PROCESSOR_ID=your-docai-processor-id
DOCAI_LOCATION=us

# Database (Google Cloud SQL)
DATABASE_URL=postgresql://username:password@/database_name?host=/cloudsql/project:region:instance
```

#### Render Deployment Environment Variables

The following environment variables are configured in `render.yaml` for production deployment:

**Security & Authentication:**
- `SECRET_KEY`: Auto-generated stable secret key for session encryption
- `MDRAFT_PUBLIC_MODE`: Set to "0" to require authentication
- `LOGIN_DISABLED`: Set to "false" to enable login requirement
- `ALLOWLIST`: Comma-separated list of allowed email addresses

**Session Cookie Security (HTTPS):**
- `SESSION_COOKIE_SECURE`: Set to "true" for HTTPS-only cookies
- `SESSION_COOKIE_SAMESITE`: Set to "Lax" for CSRF protection
- `REMEMBER_COOKIE_SECURE`: Set to "true" for HTTPS-only remember cookies
- `REMEMBER_COOKIE_SAMESITE`: Set to "Lax" for CSRF protection

**Rate Limiting:**
- `GLOBAL_RATE_LIMIT`: Set to "120 per minute" for abuse protection
- `FLASK_LIMITER_STORAGE_URI`: Redis URL for rate limiting (if configured)

**Queue Configuration:**
- `QUEUE_MODE`: Set to "sync" for synchronous processing (change to "async" for background workers)
- `CELERY_BROKER_URL`: Redis URL for Celery broker
- `CELERY_RESULT_BACKEND`: Redis URL for Celery results

**Google Cloud Services:**
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account key
- `GCS_BUCKET_NAME`: Google Cloud Storage bucket for uploads
- `USE_GCS`: Set to "0" to disable GCS (use local storage)

**Monitoring & Logging:**
- `SENTRY_DSN`: Sentry DSN for error tracking
- `SENTRY_ENVIRONMENT`: Set to "production"
- `LOG_LEVEL`: Logging level (default: INFO)

**Webhook Security:**
- `WEBHOOK_SECRET`: Secret for webhook signature verification

**Database Migration:**
- `DATABASE_URL`: PostgreSQL connection string
- Pre-deploy script runs `flask db upgrade` automatically

**Note:** Sensitive values (marked with `sync: false` in render.yaml) must be configured manually in the Render dashboard.

## API Reference

### Endpoints

#### `GET /`
Health check and welcome message.

**Response:**
```json
{
  "status": "ok",
  "message": "Welcome to mdraft!"
}
```

#### `GET /health`
Database connectivity check.

**Response:**
```json
{
  "status": "ok"
}
```

#### `POST /upload`
Upload a document for conversion.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` field containing the document

**Response:**
```json
{
  "job_id": 123,
  "status": "queued"
}
```

#### `GET /jobs/{job_id}`
Get the status of a conversion job.

**Response:**
```json
{
  "job_id": 123,
  "status": "completed",
  "download_url": "https://storage.googleapis.com/..."
}
```

#### `GET /download/{filename}`
Download a processed file (development only).

## Usage Examples

### Upload a Document

```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@document.pdf"
```

### Check Job Status

```bash
curl http://localhost:5000/jobs/123
```

### Download Result

```bash
curl -O "https://storage.googleapis.com/..."
```

## Google Cloud Setup

### 1. Enable Required APIs

```bash
gcloud services enable \
  documentai.googleapis.com \
  cloudtasks.googleapis.com \
  storage.googleapis.com \
  sqladmin.googleapis.com
```

### 2. Create Storage Buckets

```bash
gsutil mb gs://mdraft-uploads
gsutil mb gs://mdraft-processed
```

### 3. Create Document AI Processor

```bash
gcloud documentai processors create \
  --location=us \
  --type=DOCUMENT_OCR_PROCESSOR \
  --display-name="mdraft-ocr-processor"
```

### 4. Create Cloud Tasks Queue

```bash
gcloud tasks queues create mdraft-conversion-queue \
  --location=us-central1
```

### 5. Set up Service Account

```bash
# Create service account
gcloud iam service-accounts create mdraft-worker \
  --display-name="mdraft Worker"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:mdraft-worker@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:mdraft-worker@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Download key file
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=mdraft-worker@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

## Data Retention

### Lifecycle Management

The application includes automated data retention policies to manage storage costs and maintain data hygiene:

- **Upload Files**: Automatically deleted after 30 days
- **Processed Files**: Automatically deleted after 30 days
- **Job Records**: Retained in database for audit purposes

### Apply Lifecycle Policies

```bash
# Apply to uploads bucket
gcloud storage buckets update gs://$GCS_BUCKET_NAME --lifecycle-file=infrastructure/gcs/lifecycle.json

# Apply to processed bucket  
gcloud storage buckets update gs://$GCS_PROCESSED_BUCKET_NAME --lifecycle-file=infrastructure/gcs/lifecycle.json
```

### Rollback Lifecycle Policies

```bash
# Clear lifecycle policy from uploads bucket
gcloud storage buckets update gs://$GCS_BUCKET_NAME --clear-lifecycle

# Clear lifecycle policy from processed bucket
gcloud storage buckets update gs://$GCS_PROCESSED_BUCKET_NAME --clear-lifecycle
```

See `infrastructure/gcs/README.md` for detailed lifecycle management commands.

## Database Migrations

### Create a new migration
```bash
flask db migrate -m "Description of changes"
```

### Apply migrations
```bash
flask db upgrade
```

### Rollback migration
```bash
flask db downgrade
```

## Development

### Project Structure
```
mdraft_app/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # SQLAlchemy models
│   ├── routes.py            # API endpoints
│   ├── tasks.py             # Background task management
│   ├── conversion.py        # Document conversion logic
│   ├── storage.py           # Google Cloud Storage integration
│   └── utils.py             # Utility functions
├── infrastructure/
│   └── gcs/
│       ├── lifecycle.json   # GCS lifecycle policy
│       └── README.md        # Lifecycle management docs
├── migrations/              # Database migrations
├── uploads/                 # Local file uploads (gitignored)
├── processed/               # Local processed files (gitignored)
├── requirements.txt         # Python dependencies
├── run.py                   # Application entry point
├── alembic.ini             # Alembic configuration
└── .env.example            # Environment variables template
```

### Adding New Features

1. **New API Endpoints**: Add routes to `app/routes.py`
2. **Database Changes**: Create migrations with `flask db migrate`
3. **Background Tasks**: Extend `app/tasks.py` and `app/conversion.py`
4. **Cloud Integration**: Add functions to `app/storage.py`

### Testing

```bash
# Run tests (when implemented)
python -m pytest

# Run with coverage
python -m pytest --cov=app

# Run E2E validation
python tools/validate_e2e.py

# Run worker service validation
python tools/validate_e2e.py --worker
```

## Production Deployment

### Main Application (Cloud Run)

1. **Build and deploy the main application**
   ```bash
   gcloud run deploy mdraft \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 1Gi \
     --cpu 1 \
     --max-instances 10
   ```

### Worker Service (Private Cloud Run)

The worker service processes document conversion tasks from Cloud Tasks. It's deployed as a private service that only accepts authenticated requests.

1. **Create service accounts**
   ```bash
   # Create worker service account
   gcloud iam service-accounts create mdraft-worker \
     --display-name="mdraft Worker Service"
   
   # Create invoker service account for Cloud Tasks
   gcloud iam service-accounts create mdraft-invoker \
     --display-name="mdraft Task Invoker"
   ```

2. **Grant permissions**
   ```bash
   # Grant worker service account access to GCS, Document AI, and Cloud SQL
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:mdraft-worker@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.objectViewer"
   
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:mdraft-worker@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/documentai.apiUser"
   
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:mdraft-worker@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/cloudsql.client"
   
   # Grant invoker service account permission to invoke worker service
   gcloud run services add-iam-policy-binding mdraft-worker \
     --region=us-central1 \
     --member="serviceAccount:mdraft-invoker@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.invoker"
   ```

3. **Deploy using Cloud Build**
   ```bash
   # Set substitution variables
   gcloud builds submit --config=cloudbuild_worker.yaml \
     --substitutions=_DATABASE_URL="postgresql://user:pass@host:5432/db",_GCS_BUCKET_NAME="mdraft-uploads",_GCS_PROCESSED_BUCKET_NAME="mdraft-processed",_DOCAI_PROCESSOR_ID="projects/$PROJECT_ID/locations/us/processors/PROCESSOR_ID"
   ```

4. **Alternative: Deploy manually**
   ```bash
   # Build and push image
   docker build -t gcr.io/$PROJECT_ID/mdraft-worker:$COMMIT_SHA .
   docker push gcr.io/$PROJECT_ID/mdraft-worker:$COMMIT_SHA
   
   # Deploy to Cloud Run
   gcloud run deploy mdraft-worker \
     --image gcr.io/$PROJECT_ID/mdraft-worker:$COMMIT_SHA \
     --region us-central1 \
     --platform managed \
     --no-allow-unauthenticated \
     --service-account mdraft-worker@$PROJECT_ID.iam.gserviceaccount.com \
     --memory 2Gi \
     --cpu 2 \
     --max-instances 10 \
     --timeout 3600 \
     --set-env-vars WORKER_SERVICE=true,DATABASE_URL=$DATABASE_URL,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,GCS_PROCESSED_BUCKET_NAME=$GCS_PROCESSED_BUCKET_NAME,DOCAI_PROCESSOR_ID=$DOCAI_PROCESSOR_ID,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,CLOUD_TASKS_QUEUE_NAME=mdraft-conversion-queue,CLOUD_TASKS_LOCATION=us-central1,WORKER_SERVICE_URL=https://mdraft-worker-xxxxx-uc.a.run.app,WORKER_INVOKER_SA_EMAIL=mdraft-invoker@$PROJECT_ID.iam.gserviceaccount.com
   ```

### Cloud Tasks Queue Configuration

1. **Create the queue**
   ```bash
   gcloud tasks queues create mdraft-conversion-queue \
     --location=us-central1
   ```

2. **Configure retry policy**
   ```bash
   gcloud tasks queues update mdraft-conversion-queue \
     --location=us-central1 \
     --max-attempts=5 \
     --min-backoff=20s \
     --max-backoff=600s \
     --max-doublings=3
   ```

3. **Verify configuration**
   ```bash
   gcloud tasks queues describe mdraft-conversion-queue \
     --location=us-central1
   ```

See `infrastructure/tasks/README.md` for detailed queue management commands.

### Environment Variables for Production

Set these in your deployment environment:

```bash
FLASK_DEBUG=0
SECRET_KEY=<strong-secret-key>
DATABASE_URL=<cloud-sql-connection-string>
GCS_BUCKET_NAME=mdraft-uploads
GCS_PROCESSED_BUCKET_NAME=mdraft-processed
CLOUD_TASKS_QUEUE_ID=mdraft-conversion-queue
DOCAI_PROCESSOR_ID=<your-processor-id>
```

### Production Checklist

- [ ] Enable required Google Cloud APIs
- [ ] Create and configure GCS buckets
- [ ] Set up Document AI processor
- [ ] Create Cloud Tasks queue
- [ ] Configure service account with proper permissions
- [ ] Set up Cloud SQL instance
- [ ] Apply lifecycle policies for data retention
- [ ] Configure monitoring and alerting
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup and disaster recovery

## Cost Guardrails

The application includes several cost control mechanisms to prevent unexpected charges:

### Feature Flags

- **PRO_CONVERSION_ENABLED**: Master kill switch for Document AI processing
  - Set to `false` to disable all Document AI calls
  - Automatically falls back to markitdown for all conversions
  - Can be changed without code deployment

### Cost Control Features

- **Dual Engine Routing**: Automatically chooses the most cost-effective conversion engine
  - Document AI: Used only for PDFs (scanned documents)
  - markitdown: Used for all other file types (free)
- **Automatic Fallbacks**: If Document AI fails, falls back to markitdown
- **Timeout Limits**: 120-second timeout prevents runaway processes
- **Resource Limits**: Cloud Run instances have memory and CPU limits

### Emergency Cost Controls

```bash
# Disable Document AI processing (emergency kill switch)
gcloud run services update mdraft \
  --set-env-vars PRO_CONVERSION_ENABLED=false \
  --region=us-central1

# Scale down services to minimize costs
gcloud run services update mdraft \
  --max-instances=1 \
  --region=us-central1
```

### Cost Monitoring

- **Billing Alerts**: Set up budget alerts in Google Cloud Console
- **Usage Monitoring**: Track Document AI API calls and costs
- **Resource Quotas**: Set limits on Cloud Run instances and API calls

## Security Considerations

- **File Upload Validation**: MIME-type checking using magic numbers
- **Rate Limiting**: Built-in protection against abuse
- **Secure Headers**: Configured for production deployment
- **Environment Variables**: Sensitive data stored in environment
- **Signed URLs**: Temporary, expiring download links (V4)
- **Streaming Uploads**: Direct to GCS without temporary files
- **CSRF Protection**: Comprehensive protection against Cross-Site Request Forgery attacks

### CSRF Protection

The application implements robust CSRF protection using Flask-WTF with the following features:

#### HTML Form Protection
- **Automatic Token Generation**: All HTML forms include CSRF tokens via `{{ csrf_token() }}`
- **Token Validation**: Server-side validation of all form submissions
- **Token Expiration**: Configurable token lifetime (default: 1 hour)
- **Secure Token Storage**: Tokens stored in secure, HTTP-only cookies

#### API Route Exemption
- **Bearer Token Authentication**: API routes with `Authorization: Bearer <token>` headers are exempt from CSRF
- **API Key Authentication**: Routes using `X-API-Key` headers are exempt from CSRF
- **Automatic Detection**: CSRF exemption is automatically applied based on authentication headers
- **Manual Exemption**: Custom decorators available for specific route exemptions

#### Implementation Details
```python
# CSRF token in HTML forms
<form method="post" action="/auth/login">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <!-- form fields -->
</form>

# API routes with automatic exemption
@bp.post("/api/convert")
@csrf_exempt_for_api  # Automatically exempts when Bearer token or API key present
def api_convert():
    # Route implementation
```

#### Security Benefits
- **Prevents CSRF Attacks**: Protects against unauthorized form submissions
- **Session Security**: Ensures requests come from legitimate user sessions
- **API Security**: Maintains security for API routes while allowing proper authentication
- **Zero Configuration**: Works automatically with existing authentication systems

#### Configuration
```python
# CSRF settings in app configuration
app.config["WTF_CSRF_ENABLED"] = True
app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # 1 hour
```

#### Testing
Comprehensive test suite validates:
- Form submissions without CSRF tokens are rejected
- Valid CSRF tokens are accepted
- API routes with proper authentication are exempt
- Invalid authentication headers don't bypass CSRF protection

## Monitoring and Logging

- **Structured Logging**: JSON format for production
- **Correlation IDs**: Request tracking across services
- **Health Checks**: Database and service monitoring
- **Error Handling**: Comprehensive exception management
- **GCS Lifecycle**: Automated data retention and cleanup

## Resilience Drills

Regular operational drills help ensure the team is prepared for incidents:

### Scheduled Drills

1. **Monthly Rollback Drill**: Practice rolling back Cloud Run revisions
2. **Quarterly Database Rollback**: Practice rolling back database migrations
3. **Bi-monthly Kill Switch Drill**: Practice using the cost control kill switch

### Drill Procedures

See `OPERATIONS.md` for detailed drill procedures including:
- Intentional error deployment and rollback
- Database migration rollback practice
- Feature flag kill switch activation
- Emergency cost control procedures

### Drill Benefits

- **Team Preparedness**: Ensures familiarity with rollback procedures
- **Procedure Validation**: Tests that documented procedures work
- **Tool Familiarity**: Builds confidence with gcloud and flask commands
- **Incident Response**: Reduces time to recovery during real incidents

### Post-Drill Activities

- Document lessons learned
- Update procedures based on findings
- Schedule follow-up drills for areas needing improvement

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license information here]

## Support

For support and questions, please [create an issue](link-to-issues) or contact [your-email].
