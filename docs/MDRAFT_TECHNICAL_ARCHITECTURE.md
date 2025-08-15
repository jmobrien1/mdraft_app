# MDraft Technical Architecture: Comprehensive System Design Document

## Executive Summary

MDraft is a sophisticated document processing and RFP analysis platform built on Flask, designed to convert documents to markdown and extract structured data from RFP documents using AI. The system employs a microservices architecture with Google Cloud integration, asynchronous processing, and comprehensive monitoring.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Patterns](#architecture-patterns)
3. [Technology Stack](#technology-stack)
4. [Application Architecture](#application-architecture)
5. [Data Layer](#data-layer)
6. [Service Layer](#service-layer)
7. [API Design](#api-design)
8. [Processing Pipeline](#processing-pipeline)
9. [Security Architecture](#security-architecture)
10. [Deployment Architecture](#deployment-architecture)
11. [Monitoring and Observability](#monitoring-and-observability)
12. [Performance Considerations](#performance-considerations)

## System Overview

### Core Functionality

MDraft provides three primary capabilities:

1. **Document Conversion**: Convert PDFs and other documents to markdown
2. **RFP Analysis**: Extract structured data from RFP documents using AI
3. **Proposal Management**: Track and manage proposal-related conversions

### System Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   Flask API      │    │   Celery Worker │
│   (Static)      │◄──►│   (Synchronous)  │◄──►│   (Async)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   PostgreSQL     │
                       │   Database       │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Google Cloud   │
                       │   Services       │
                       └──────────────────┘
```

## Architecture Patterns

### 1. Application Factory Pattern

The system uses Flask's application factory pattern for modular initialization:

```python
# app/__init__.py
def create_app() -> Flask:
    app = Flask(__name__)
    
    # Configure extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    
    return app
```

**Benefits:**
- Multiple application instances (web, worker, testing)
- Lazy initialization of extensions
- Environment-specific configuration
- Simplified testing

### 2. Service Layer Pattern

Business logic is encapsulated in service classes:

```python
# app/services/ai_tools.py
class AIToolsService:
    def run_prompt(self, prompt_type: str, content: str) -> Dict[str, Any]:
        # AI processing logic
        pass

# app/services/storage.py
class StorageService:
    def upload_file(self, file_stream, filename: str) -> str:
        # File upload logic
        pass
```

**Benefits:**
- Separation of concerns
- Reusable business logic
- Testable components
- Clear interfaces

### 3. Repository Pattern

Data access is abstracted through model classes:

```python
# app/models.py
class User(UserMixin, db.Model):
    @staticmethod
    def get_or_create_by_email(email: str):
        # Data access logic
        pass

class Job(db.Model):
    def __repr__(self) -> str:
        return f"<Job {self.id} ({self.status})>"
```

### 4. Blueprint Pattern

Route organization using Flask blueprints:

```python
# app/routes.py
bp = Blueprint("main", __name__)

@bp.route("/api/upload", methods=["POST"])
def upload_file():
    # Route logic
    pass

# app/api/ops.py
ops = Blueprint("ops", __name__)

@ops.get("/api/ops/migration_status")
def migration_status():
    # Health check logic
    pass
```

## Technology Stack

### Backend Framework
- **Flask 3.0.3**: Lightweight web framework
- **SQLAlchemy 3.1.1**: ORM with declarative models
- **Flask-Migrate 4.0.7**: Database migration management
- **Alembic 1.13.1**: Migration engine

### Database
- **PostgreSQL**: Primary database with psycopg v3 driver
- **Connection Pooling**: SQLAlchemy connection management
- **Migrations**: Alembic for schema versioning

### Asynchronous Processing
- **Celery 5.4.0**: Distributed task queue
- **Redis 5.0.7**: Message broker and result backend
- **Thread Pool**: Worker concurrency management

### Cloud Services (Google Cloud)
- **Cloud Storage**: File storage and retrieval
- **Cloud Tasks**: Task queue for async processing
- **Document AI**: Document text extraction
- **Vertex AI**: LLM integration (Gemini)
- **Secret Manager**: Credential management

### Authentication & Security
- **Flask-Login 0.6.3**: Session management
- **Flask-Bcrypt 1.0.1**: Password hashing
- **Flask-Limiter 3.6.0**: Rate limiting
- **CORS**: Cross-origin resource sharing

### Monitoring & Observability
- **Sentry SDK**: Error tracking and performance monitoring
- **JSON Logging**: Structured logging with correlation IDs
- **Health Checks**: Application and database health monitoring

## Application Architecture

### Core Application Structure

```
app/
├── __init__.py              # Application factory
├── models.py                # Core data models
├── models_conversion.py     # Conversion-specific models
├── models_apikey.py         # API key models
├── routes.py                # Main web routes
├── api/                     # API blueprints
│   ├── ops.py              # Operations/monitoring
│   ├── agents.py           # AI agent endpoints
│   └── errors.py           # Error handling
├── services/                # Business logic layer
│   ├── ai_tools.py         # AI processing
│   ├── storage.py          # File storage
│   ├── text_loader.py      # Document loading
│   └── llm_client.py       # LLM integration
├── auth/                    # Authentication
├── admin/                   # Admin interface
├── static/                  # Static assets
├── templates/               # HTML templates
└── utils/                   # Utility functions
```

### Extension Configuration

```python
# Global extensions (initialized without app context)
db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
bcrypt: Bcrypt = Bcrypt()
login_manager: LoginManager = LoginManager()

# Rate limiter with Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=ENV.get("FLASK_LIMITER_STORAGE_URI"),
    default_limits=[ENV.get("GLOBAL_RATE_LIMIT", "120 per minute")],
)
```

### Environment Configuration

```python
# Environment-based configuration
app.config["SECRET_KEY"] = ENV.get("SECRET_KEY", "changeme")
app.config["SQLALCHEMY_DATABASE_URI"] = normalize_db_url(ENV.get("DATABASE_URL", ""))
app.config["GCS_BUCKET_NAME"] = ENV.get("GCS_BUCKET_NAME")
app.config["CELERY_BROKER_URL"] = ENV.get("CELERY_BROKER_URL")
```

## Data Layer

### Database Schema Design

#### Core Tables

**Users Table**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    stripe_customer_id VARCHAR(255),
    subscription_status VARCHAR(64) DEFAULT 'free',
    plan VARCHAR(64) DEFAULT 'F&F',
    last_login_at TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Jobs Table**
```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(64) DEFAULT 'pending',
    gcs_uri TEXT,
    output_uri TEXT,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Conversions Table**
```sql
CREATE TABLE conversions (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    markdown TEXT,
    error TEXT,
    proposal_id INTEGER REFERENCES proposals(id),
    user_id INTEGER REFERENCES users(id),
    visitor_session_id VARCHAR(64),
    sha256 VARCHAR(64),
    original_mime VARCHAR(120),
    original_size INTEGER,
    stored_uri VARCHAR(512),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Proposals Table**
```sql
CREATE TABLE proposals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    visitor_session_id VARCHAR(64),
    title VARCHAR(255),
    status VARCHAR(64) DEFAULT 'draft',
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT ck_proposals_owner_present 
        CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL))
);
```

### Model Relationships

```python
# User -> Jobs (one-to-many)
class User(UserMixin, db.Model):
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")

class Job(db.Model):
    user: Mapped[User] = relationship("User", back_populates="jobs")

# Proposal -> Conversions (one-to-many)
class Proposal(db.Model):
    conversions: Mapped[list[Conversion]] = relationship("Conversion", back_populates="proposal")

class Conversion(db.Model):
    proposal: Mapped[Optional[Proposal]] = relationship("Proposal", back_populates="conversions")
```

### Data Access Patterns

#### Repository Methods
```python
class User(UserMixin, db.Model):
    @staticmethod
    def get_or_create_by_email(email: str):
        """Get existing user or create new one."""
        e = (email or '').strip().lower()
        u = User.query.filter_by(email=e).first()
        if not u:
            u = User(email=e)
            db.session.add(u)
            db.session.commit()
        return u

class Job(db.Model):
    @classmethod
    def create_for_user(cls, user_id: int, filename: str) -> 'Job':
        """Create a new job for a user."""
        job = cls(user_id=user_id, filename=filename)
        db.session.add(job)
        db.session.commit()
        return job
```

#### Query Optimization
```python
# Eager loading for relationships
jobs = Job.query.options(joinedload(Job.user)).filter_by(status='pending').all()

# Indexed queries
user = User.query.filter_by(email=email).first()  # Uses email index

# Batch operations
db.session.bulk_insert_mappings(Job, job_data)
```

## Service Layer

### AI Tools Service

The AI Tools service handles document analysis and structured data extraction:

```python
# app/services/ai_tools.py
class AIToolsService:
    def __init__(self):
        self.chunk_size = int(os.getenv("MDRAFT_CHUNK_SIZE_CHARS") or 3000)
        self.max_chunks = int(os.getenv("MDRAFT_MAX_CHUNKS") or 12)
        self.matrix_window_size = int(os.getenv("MATRIX_WINDOW_SIZE") or 12)
    
    def run_prompt(self, prompt_type: str, content: str) -> Dict[str, Any]:
        """Execute AI prompt on document content."""
        # 1. Chunk the content
        chunks = self._chunk_content(content)
        
        # 2. Process chunks with sliding window
        results = self._process_chunks_with_window(chunks, prompt_type)
        
        # 3. Merge and deduplicate results
        merged = self._merge_results(results)
        
        # 4. Validate against schema
        validated = self._validate_results(merged, prompt_type)
        
        return validated
    
    def _chunk_content(self, content: str) -> List[str]:
        """Split content into manageable chunks."""
        # Implementation details...
        pass
    
    def _process_chunks_with_window(self, chunks: List[str], prompt_type: str) -> List[Dict]:
        """Process chunks using sliding window approach."""
        # Implementation details...
        pass
```

### Storage Service

The Storage service manages file upload, storage, and retrieval:

```python
# app/services/storage.py
class StorageService:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
    
    def upload_file(self, file_stream, filename: str, content_type: str = None) -> str:
        """Upload file to Google Cloud Storage."""
        blob = self.bucket.blob(filename)
        
        # Set metadata
        if content_type:
            blob.content_type = content_type
        
        # Upload with retry logic
        blob.upload_from_file(file_stream, retry=storage.retry.DEFAULT_RETRY)
        
        return f"gs://{self.bucket_name}/{filename}"
    
    def generate_download_url(self, gcs_uri: str, expiration: int = 3600) -> str:
        """Generate signed download URL."""
        # Implementation details...
        pass
    
    def delete_file(self, gcs_uri: str) -> bool:
        """Delete file from storage."""
        # Implementation details...
        pass
```

### Text Loader Service

The Text Loader service handles document text extraction:

```python
# app/services/text_loader.py
class TextLoaderService:
    def __init__(self):
        self.documentai_client = documentai.DocumentProcessorServiceClient()
        self.processor_id = os.getenv("DOCAI_PROCESSOR_ID")
    
    def extract_text(self, file_content: bytes, mime_type: str) -> str:
        """Extract text from document using Document AI."""
        # 1. Create document
        document = {"content": file_content, "mime_type": mime_type}
        
        # 2. Process with Document AI
        request = documentai.ProcessRequest(
            name=f"projects/{project_id}/locations/{location}/processors/{self.processor_id}",
            document=document
        )
        
        # 3. Extract text
        result = self.documentai_client.process_document(request=request)
        return result.document.text
```

## API Design

### RESTful API Structure

#### Core Endpoints

**File Upload and Processing**
```
POST /api/upload                    # Upload file for conversion
GET  /api/jobs/{job_id}            # Get job status
GET  /api/jobs/{job_id}/download   # Download processed file
```

**RFP Analysis**
```
POST /api/rfp/compliance-matrix     # Extract compliance requirements
POST /api/rfp/evaluation-criteria   # Extract evaluation criteria
POST /api/rfp/annotated-outline     # Generate annotated outline
POST /api/rfp/submission-checklist  # Extract submission requirements
```

**Proposal Management**
```
POST /api/proposals                 # Create new proposal
GET  /api/proposals                 # List proposals
GET  /api/proposals/{id}            # Get proposal details
PUT  /api/proposals/{id}            # Update proposal
```

**Health and Monitoring**
```
GET  /health                        # Basic health check
GET  /api/ops/migration_status      # Database migration status
GET  /api/ops/metrics               # Application metrics
```

### Request/Response Patterns

#### Standard Response Format
```python
@bp.route("/api/upload", methods=["POST"])
def upload_file():
    try:
        # Process request
        result = process_upload(request)
        return jsonify({
            "status": "success",
            "data": result,
            "message": "File uploaded successfully"
        }), 200
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "error": "validation_error",
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": "internal_error",
            "message": "An unexpected error occurred"
        }), 500
```

#### Error Handling
```python
@bp.errorhandler(400)
def bad_request(e):
    return jsonify({
        "status": "error",
        "error": "bad_request",
        "message": str(e)
    }), 400

@bp.errorhandler(404)
def not_found(e):
    return jsonify({
        "status": "error", 
        "error": "not_found",
        "message": "Resource not found"
    }), 404
```

### Rate Limiting

```python
# Global rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"]
)

# Endpoint-specific limits
@bp.route("/api/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file():
    # Implementation...
    pass

# User-specific limits
@bp.route("/api/rfp/analysis", methods=["POST"])
@limiter.limit("30 per minute")
def analyze_rfp():
    # Implementation...
    pass
```

## Processing Pipeline

### Document Conversion Pipeline

```mermaid
graph TD
    A[File Upload] --> B[Validation]
    B --> C[Store in GCS]
    C --> D[Create Job Record]
    D --> E[Queue Conversion Task]
    E --> F[Celery Worker]
    F --> G[Extract Text]
    G --> H[Convert to Markdown]
    H --> I[Store Result]
    I --> J[Update Job Status]
    J --> K[Notify User]
```

#### Implementation Details

**1. File Upload Handler**
```python
@bp.route("/api/upload", methods=["POST"])
def upload_file():
    # Validate file
    if 'file' not in request.files:
        raise ValidationError("No file provided")
    
    file = request.files['file']
    if not is_file_allowed(file.filename):
        raise ValidationError("File type not allowed")
    
    # Generate unique filename
    filename = generate_job_id() + "_" + secure_filename(file.filename)
    
    # Upload to GCS
    gcs_uri = upload_stream_to_gcs(file.stream, filename, file.content_type)
    
    # Create job record
    job = Job.create_for_user(current_user.id, file.filename)
    job.gcs_uri = gcs_uri
    db.session.commit()
    
    # Queue conversion task
    enqueue_conversion_task.delay(job.id)
    
    return jsonify({
        "status": "success",
        "job_id": job.id,
        "message": "File uploaded and queued for processing"
    })
```

**2. Celery Task**
```python
@celery.task(bind=True)
def convert_document(self, job_id: int):
    try:
        # Get job
        job = Job.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Update status
        job.status = "processing"
        job.started_at = datetime.utcnow()
        db.session.commit()
        
        # Download file from GCS
        file_content = download_from_gcs(job.gcs_uri)
        
        # Extract text
        text = extract_text_from_document(file_content, job.filename)
        
        # Convert to markdown
        markdown = convert_text_to_markdown(text)
        
        # Store result
        output_uri = store_markdown_result(markdown, job_id)
        
        # Update job
        job.status = "completed"
        job.output_uri = output_uri
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
    except Exception as e:
        # Handle error
        job.status = "failed"
        job.error_message = str(e)
        db.session.commit()
        raise
```

### RFP Analysis Pipeline

```mermaid
graph TD
    A[RFP Upload] --> B[Text Extraction]
    B --> C[Content Chunking]
    C --> D[AI Processing]
    D --> E[Result Merging]
    E --> F[Schema Validation]
    F --> G[Structured Output]
```

#### Implementation Details

**1. Content Chunking**
```python
def _chunk_content(self, content: str) -> List[str]:
    """Split content into manageable chunks for AI processing."""
    chunks = []
    current_chunk = ""
    
    for paragraph in content.split('\n\n'):
        if len(current_chunk) + len(paragraph) > self.chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks[:self.max_chunks]
```

**2. Sliding Window Processing**
```python
def _process_chunks_with_window(self, chunks: List[str], prompt_type: str) -> List[Dict]:
    """Process chunks using sliding window approach."""
    results = []
    
    for i in range(0, len(chunks), self.matrix_window_size):
        window = chunks[i:i + self.matrix_window_size]
        window_text = "\n\n".join(window)
        
        # Process window with AI
        window_result = self._process_with_ai(window_text, prompt_type)
        results.extend(window_result)
    
    return results
```

**3. Result Merging and Deduplication**
```python
def _merge_results(self, results: List[Dict]) -> List[Dict]:
    """Merge and deduplicate results from multiple chunks."""
    seen = {}
    merged = []
    
    for result in results:
        # Create stable key for deduplication
        key = f"{result.get('requirement_text', '')}|{result.get('rfp_reference', '')}"
        
        if key not in seen:
            seen[key] = result
            merged.append(result)
    
    return merged[:self.max_merged_items]
```

## Security Architecture

### Authentication System

#### User Authentication
```python
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)
    
    @staticmethod
    def create_user(email: str, password: str) -> 'User':
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        return user
```

#### Session Management
```python
# Session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

@bp.route("/login", methods=["POST"])
def login():
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        login_user(user, remember=True)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401
```

### Authorization

#### Role-Based Access Control
```python
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "authentication_required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_subscription(plan: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "authentication_required"}), 401
            if current_user.subscription_status != plan:
                return jsonify({"error": "subscription_required"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### Data Protection

#### Input Validation
```python
def validate_file_upload(file):
    """Validate uploaded file."""
    if not file:
        raise ValidationError("No file provided")
    
    if not is_file_allowed(file.filename):
        raise ValidationError("File type not allowed")
    
    if file.content_length > MAX_FILE_SIZE:
        raise ValidationError("File too large")
    
    return file

def validate_rfp_content(content: str):
    """Validate RFP content."""
    if not content or len(content.strip()) < 100:
        raise ValidationError("Content too short")
    
    if len(content) > MAX_CONTENT_LENGTH:
        raise ValidationError("Content too long")
    
    return content
```

#### SQL Injection Prevention
```python
# Use parameterized queries
def get_user_by_email(email: str):
    return User.query.filter_by(email=email).first()

# Use SQLAlchemy ORM
def get_jobs_for_user(user_id: int):
    return Job.query.filter_by(user_id=user_id).all()
```

### API Security

#### Rate Limiting
```python
# Global rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=ENV.get("FLASK_LIMITER_STORAGE_URI"),
    default_limits=["120 per minute"]
)

# Endpoint-specific limits
@bp.route("/api/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file():
    # Implementation...
    pass
```

#### CORS Configuration
```python
# Configure CORS for API endpoints
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://yourdomain.com"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

## Deployment Architecture

### Render Deployment Configuration

#### Web Service
```yaml
services:
  - type: web
    name: mdraft-web
    env: python
    buildCommand: pip install -r requirements.txt
    runtime: python-3.11.11
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
    healthCheckPath: /health
```

#### Worker Service
```yaml
services:
  - type: worker
    name: mdraft_app-worker
    env: python
    buildCommand: pip install -r requirements.txt
    runtime: python-3.11.11
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4
```

#### Cron Service
```yaml
services:
  - type: cron
    name: mdraft-cleanup
    env: python
    schedule: "0 6 * * *"
    buildCommand: pip install -r requirements.txt
    runtime: python-3.11.11
    startCommand: flask --app app:create_app cleanup
```

### Environment Configuration

#### Required Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host/db

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp.json
GCS_BUCKET_NAME=your-bucket-name
DOCAI_PROCESSOR_ID=your-processor-id

# Celery
CELERY_BROKER_URL=redis://redis-host:6379/0
CELERY_RESULT_BACKEND=redis://redis-host:6379/0

# Security
SECRET_KEY=your-secret-key
SENTRY_DSN=your-sentry-dsn

# Application
FLASK_APP=run.py
FLASK_ENV=production
```

### Migration System

#### Migration Sentry
```bash
#!/usr/bin/env bash
# scripts/migration_sentry.sh

# 1. Environment validation
: "${DATABASE_URL:?DATABASE_URL is not set}"

# 2. Database connectivity test
python - <<'PY'
# Test database connection
PY

# 3. Migration execution with auto-repair
flask db upgrade
if [[ $rc -ne 0 ]]; then
    flask db stamp base
    flask db upgrade
fi

# 4. Schema verification
python - <<'PY'
# Verify required columns exist
PY
```

## Monitoring and Observability

### Logging Strategy

#### Structured JSON Logging
```python
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "correlation_id": self._get_correlation_id(),
            "request_id": self._get_request_id(),
            "user_id": self._get_user_id(),
        }
        return json.dumps(log_data, default=str)
```

#### Correlation IDs
```python
@app.before_request
def set_request_id():
    """Set request ID for logging and tracing."""
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    request.environ['X-Request-ID'] = request_id
    request.environ['HTTP_X_REQUEST_ID'] = request_id
```

### Health Monitoring

#### Health Check Endpoints
```python
@bp.route("/health", methods=["GET"])
def health_check():
    """Database health check."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "database_error"}), 503

@bp.route("/api/ops/migration_status")
def migration_status():
    """Migration status check."""
    try:
        # Check required columns
        checks = {}
        for table, col in [("proposals", "visitor_session_id"), ("conversions", "proposal_id")]:
            cnt = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name=:t AND column_name=:c
            """), {"t": table, "c": col}).scalar()
            checks[f"{table}.{col}"] = (cnt == 1)
        
        return jsonify({
            "migrated": all(checks.values()),
            "checks": checks
        })
    except Exception as e:
        return jsonify({"migrated": False, "error": str(e)}), 500
```

### Error Tracking

#### Sentry Integration
```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=ENV.get("SENTRY_DSN"),
    integrations=[FlaskIntegration()],
    environment=ENV.get("SENTRY_ENVIRONMENT", "production"),
    traces_sample_rate=0.10,
)
```

### Performance Monitoring

#### Request Timing
```python
@app.before_request
def start_timer():
    g.start = time.time()

@app.after_request
def log_request(response):
    if hasattr(g, 'start'):
        duration = time.time() - g.start
        current_app.logger.info(
            f"Request {request.method} {request.path} took {duration:.3f}s",
            extra={
                "duration": duration,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code
            }
        )
    return response
```

## Performance Considerations

### Database Optimization

#### Indexing Strategy
```sql
-- User queries
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_status ON users(subscription_status);

-- Job queries
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);

-- Conversion queries
CREATE INDEX idx_conversions_proposal_id ON conversions(proposal_id);
CREATE INDEX idx_conversions_user_id ON conversions(user_id);
CREATE INDEX idx_conversions_visitor_session_id ON conversions(visitor_session_id);
CREATE INDEX idx_conversions_sha256 ON conversions(sha256);
```

#### Query Optimization
```python
# Use eager loading for relationships
jobs = Job.query.options(joinedload(Job.user)).filter_by(status='pending').all()

# Use pagination for large result sets
jobs = Job.query.filter_by(user_id=user_id).paginate(
    page=page, per_page=20, error_out=False
)

# Use bulk operations for large datasets
db.session.bulk_insert_mappings(Job, job_data)
```

### Caching Strategy

#### Redis Caching
```python
import redis

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"))

def get_cached_result(key: str) -> Optional[Dict]:
    """Get cached result from Redis."""
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def cache_result(key: str, result: Dict, ttl: int = 3600):
    """Cache result in Redis."""
    redis_client.setex(key, ttl, json.dumps(result))
```

### Asynchronous Processing

#### Celery Task Configuration
```python
# Celery configuration
celery = Celery('mdraft')
celery.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND"),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

# Task routing
celery.conf.task_routes = {
    'app.celery_tasks.convert_document': {'queue': 'conversion'},
    'app.celery_tasks.analyze_rfp': {'queue': 'analysis'},
}
```

#### Task Retry Logic
```python
@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def convert_document(self, job_id: int):
    try:
        # Task implementation
        pass
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### File Processing Optimization

#### Streaming Uploads
```python
def upload_stream_to_gcs(file_stream, filename: str, content_type: str = None) -> str:
    """Upload file stream to GCS without loading into memory."""
    blob = bucket.blob(filename)
    
    if content_type:
        blob.content_type = content_type
    
    # Stream upload to avoid memory issues
    blob.upload_from_file(file_stream, retry=storage.retry.DEFAULT_RETRY)
    
    return f"gs://{bucket.name}/{filename}"
```

#### Chunked Processing
```python
def process_large_document(content: str, chunk_size: int = 3000) -> List[Dict]:
    """Process large documents in chunks."""
    chunks = []
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i + chunk_size]
        chunks.append(chunk)
    
    # Process chunks in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_chunk, chunks))
    
    return merge_results(results)
```

This comprehensive technical architecture document provides excruciating detail about how mdraft is designed, written, and implemented, covering all aspects from the application factory pattern to performance optimization strategies.
