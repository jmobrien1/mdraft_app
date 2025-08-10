# mdraft - Document to Markdown Conversion SaaS

A Flask-based SaaS application that converts documents (PDF, DOCX) to Markdown format using Google Cloud services.

## Features

- **Document Upload**: Secure file upload with MIME-type validation
- **Multiple Conversion Engines**: 
  - Open-source markitdown for standard documents
  - Google Document AI for scanned documents and OCR
- **Background Processing**: Asynchronous job processing with status tracking
- **Google Cloud Integration**: 
  - Cloud Storage for file management
  - Cloud Tasks for background job processing
  - Document AI for advanced text extraction
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
  - Cloud Storage
  - Cloud Tasks
  - Document AI
- **Security**: Flask-Bcrypt, rate limiting
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
   pip install -r requirements.txt
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

The application will be available at `http://localhost:5000`

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
CLOUD_TASKS_QUEUE_ID=mdraft-conversion-queue
CLOUD_TASKS_LOCATION=us-central1

# Google Document AI
DOCAI_PROCESSOR_ID=your-docai-processor-id
DOCAI_LOCATION=us

# Database (Google Cloud SQL)
DATABASE_URL=postgresql://username:password@/database_name?host=/cloudsql/project:region:instance
```

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
```

## Production Deployment

### Google Cloud Run

1. **Create Dockerfile**
2. **Build and deploy**
   ```bash
   gcloud run deploy mdraft \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

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

## Security Considerations

- **File Upload Validation**: MIME-type checking using magic numbers
- **Rate Limiting**: Built-in protection against abuse
- **Secure Headers**: Configured for production deployment
- **Environment Variables**: Sensitive data stored in environment
- **Signed URLs**: Temporary, expiring download links

## Monitoring and Logging

- **Structured Logging**: JSON format for production
- **Correlation IDs**: Request tracking across services
- **Health Checks**: Database and service monitoring
- **Error Handling**: Comprehensive exception management

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
