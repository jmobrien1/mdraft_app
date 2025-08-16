# MDraft Technical Design Document (TDD)
## Document Processing & RFP Analysis SaaS Platform

**Version:** 1.0  
**Date:** December 2024  
**Author:** Technical Architecture Team  
**Status:** As-Built Documentation  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Architecture Design](#architecture-design)
4. [Technology Stack](#technology-stack)
5. [Data Architecture](#data-architecture)
6. [Application Architecture](#application-architecture)
7. [Security Architecture](#security-architecture)
8. [Deployment Architecture](#deployment-architecture)
9. [Performance & Scalability](#performance--scalability)
10. [Monitoring & Observability](#monitoring--observability)
11. [Implementation Details](#implementation-details)
12. [Testing Strategy](#testing-strategy)
13. [Operational Procedures](#operational-procedures)
14. [Risk Assessment](#risk-assessment)
15. [Future Enhancements](#future-enhancements)

---

## Executive Summary

MDraft is a sophisticated document processing and RFP analysis SaaS platform built on Flask, designed to convert documents to markdown and extract structured data from RFP documents using AI. The system employs a microservices architecture with Google Cloud integration, asynchronous processing, and comprehensive monitoring.

### Key Capabilities
- **Document Conversion**: PDF/DOCX to Markdown conversion using dual engines (markitdown + Document AI)
- **RFP Analysis**: AI-powered extraction of compliance matrices, evaluation criteria, and submission requirements
- **Proposal Management**: Multi-user proposal tracking with visitor session support
- **Asynchronous Processing**: Background job processing with Celery and Cloud Tasks
- **Enterprise Security**: Comprehensive authentication, authorization, and data protection

### Technical Highlights
- **Flask 3.0** application factory pattern with modular blueprints
- **PostgreSQL** with SQLAlchemy ORM and Alembic migrations
- **Google Cloud** integration (Storage, Tasks, Document AI, Vertex AI)
- **Redis** for session management and rate limiting
- **Celery** for asynchronous task processing
- **Sentry** for error tracking and performance monitoring

---

## System Overview

### Core System Components

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

### Primary Use Cases

1. **Document Upload & Conversion**
   - User uploads PDF/DOCX document
   - System validates file type and size
   - Document stored in Google Cloud Storage
   - Background conversion to Markdown
   - User receives download link

2. **RFP Analysis**
   - User uploads RFP document
   - AI extracts compliance requirements
   - System generates structured data (compliance matrix, evaluation criteria)
   - Results stored with proposal context

3. **Proposal Management**
   - Users create and manage proposals
   - Track conversion history and analysis results
   - Support for both authenticated users and anonymous visitors

---

## Architecture Design

### Application Factory Pattern

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

### Service Layer Pattern

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

### Blueprint Pattern

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

---

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

---

## Data Architecture

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
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Conversions Table**
```sql
CREATE TABLE conversions (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'QUEUED',
    progress INTEGER,
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
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_conversions_sha256_owner 
        UNIQUE (sha256, user_id, visitor_session_id)
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

# Proposal -> Conversions (one-to-many)
class Proposal(db.Model):
    conversions: Mapped[list[Conversion]] = relationship("Conversion", back_populates="proposal")

# Conversion -> Proposal (many-to-one)
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

class Conversion(db.Model):
    def transition_status(self, new_status: str) -> None:
        """Safely transition conversion status with validation."""
        if not ConversionStatus.is_valid_transition(self.status.value, new_status):
            raise ValueError(f"Invalid status transition from {self.status.value} to {new_status}")
        self.status = ConversionStatus(new_status)
```

---

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

### Centralized Configuration

```python
# app/config.py
@dataclass
class AppConfig:
    def __init__(self):
        # File size limits
        self.file_sizes = FileSizeLimits(
            PDF_MB=int(os.getenv("MAX_UPLOAD_PDF_MB", "25")),
            OFFICE_MB=int(os.getenv("MAX_UPLOAD_OFFICE_MB", "20")),
            TEXT_MB=int(os.getenv("MAX_UPLOAD_TEXT_MB", "5")),
            BINARY_MB=int(os.getenv("MAX_UPLOAD_BINARY_MB", "10"))
        )
        
        # Rate limits
        self.rate_limits = RateLimits(
            GLOBAL_PER_MINUTE=os.getenv("GLOBAL_RATE_LIMIT", "120 per minute"),
            CONVERT_PER_MINUTE=os.getenv("CONVERT_RATE_LIMIT_DEFAULT", "20 per minute"),
            AI_PER_MINUTE=os.getenv("AI_RATE_LIMIT_DEFAULT", "10 per minute")
        )
        
        # Security configuration
        self.security = SecurityConfig(
            SESSION_LIFETIME_DAYS=int(os.getenv("SESSION_LIFETIME_DAYS", "14")),
            CSRF_TIMEOUT_HOURS=int(os.getenv("CSRF_TIMEOUT_HOURS", "1")),
            PASSWORD_MIN_LENGTH=int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
        )
```

---

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
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Session backend configuration
if config.SESSION_BACKEND == "redis":
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_REDIS"] = config.REDIS_URL
elif config.SESSION_BACKEND == "null":
    app.config["SESSION_TYPE"] = "null"
else:
    app.config["SESSION_TYPE"] = "filesystem"
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

#### CSRF Protection
```python
# CSRF Configuration
app.config.setdefault("WTF_CSRF_ENABLED", True)
app.config.setdefault("WTF_CSRF_TIME_LIMIT", 60 * 60 * config.security.CSRF_TIMEOUT_HOURS)

# CSRF exemption for API routes
@app.before_request
def _csrf_exempt_api_routes():
    """Exempt API routes from CSRF when using proper authentication."""
    from app.utils.csrf import is_api_request
    if is_api_request(request):
        csrf.exempt(request)
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

# User-specific limits
@bp.route("/api/rfp/analysis", methods=["POST"])
@limiter.limit("30 per minute")
def analyze_rfp():
    # Implementation...
    pass
```

#### Security Headers
```python
@app.after_request
def _set_secure_headers(resp):
    # Basic security headers
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    
    # HSTS
    resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains; preload")
    
    # CSP for HTML responses
    if resp.mimetype == 'text/html':
        csp_policy = config.csp.build_policy()
        resp.headers.setdefault("Content-Security-Policy", csp_policy)
    
    return resp
```

---

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
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    result = conn.execute(text("SELECT 1"))
    print("Database connection successful")
PY

# 3. Migration execution with auto-repair
flask db upgrade
if [[ $? -ne 0 ]]; then
    echo "Migration failed, attempting repair..."
    flask db stamp base
    flask db upgrade
fi

# 4. Schema verification
python - <<'PY'
# Verify required columns exist
PY
```

---

## Performance & Scalability

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
CREATE INDEX idx_conversions_status_created_at ON conversions(status, created_at);
```

#### Connection Pooling
```python
# SQLAlchemy engine pooling configuration for Render
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,      # Validate connections before use
    "pool_size": 5,             # Maintain 5 persistent connections
    "max_overflow": 5,          # Allow 5 additional connections when pool is full
    "pool_recycle": 1800,       # Recycle connections after 30 minutes
    "pool_timeout": 30,         # Wait up to 30 seconds for available connection
    "echo": False,              # Disable SQL echo in production
}
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

---

## Monitoring & Observability

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

---

## Implementation Details

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

---

## Testing Strategy

### Unit Testing
```python
# Test conversion logic
def test_convert_with_markitdown():
    """Test markitdown conversion."""
    with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
        temp_file.write(b"test content")
        temp_file.flush()
        
        result = convert_with_markitdown(temp_file.name)
        assert "test content" in result

# Test AI tools
def test_ai_tools_chunking():
    """Test content chunking."""
    service = AIToolsService()
    content = "paragraph 1\n\nparagraph 2\n\nparagraph 3"
    chunks = service._chunk_content(content)
    assert len(chunks) > 0
```

### Integration Testing
```python
# Test file upload workflow
def test_file_upload_workflow():
    """Test complete file upload workflow."""
    with app.test_client() as client:
        # Login
        client.post('/auth/login', data={'email': 'test@example.com', 'password': 'password'})
        
        # Upload file
        with open('test.pdf', 'rb') as f:
            response = client.post('/api/upload', data={'file': f})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'job_id' in data
```

### End-to-End Testing
```python
# Test complete RFP analysis
def test_rfp_analysis_e2e():
    """Test complete RFP analysis workflow."""
    with app.test_client() as client:
        # Upload RFP
        with open('test_rfp.pdf', 'rb') as f:
            response = client.post('/api/upload', data={'file': f})
        
        job_id = response.get_json()['job_id']
        
        # Wait for processing
        while True:
            status_response = client.get(f'/api/jobs/{job_id}')
            status = status_response.get_json()['status']
            if status == 'completed':
                break
            time.sleep(1)
        
        # Analyze RFP
        analysis_response = client.post('/api/rfp/compliance-matrix', 
                                      json={'content': 'test content'})
        assert analysis_response.status_code == 200
```

---

## Operational Procedures

### Deployment Procedures

#### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Database migrations tested
- [ ] Environment variables configured
- [ ] Google Cloud services enabled
- [ ] Monitoring alerts configured

#### Deployment Steps
1. **Code Review**: Ensure all changes are reviewed and approved
2. **Testing**: Run full test suite in staging environment
3. **Database Migration**: Execute migrations with rollback plan
4. **Deployment**: Deploy to production using Render
5. **Health Check**: Verify all services are healthy
6. **Smoke Test**: Run basic functionality tests
7. **Monitoring**: Monitor error rates and performance

### Backup and Recovery

#### Database Backup
```bash
# Automated daily backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Point-in-time recovery
pg_restore --clean --if-exists backup_20241201.sql
```

#### File Storage Backup
```bash
# GCS bucket backup
gsutil -m rsync -r gs://source-bucket gs://backup-bucket

# Restore from backup
gsutil -m rsync -r gs://backup-bucket gs://source-bucket
```

### Incident Response

#### Error Monitoring
- **Sentry**: Real-time error tracking and alerting
- **Health Checks**: Automated monitoring of service health
- **Log Analysis**: Structured logging for troubleshooting

#### Escalation Procedures
1. **Level 1**: Automated alerts and basic recovery
2. **Level 2**: Manual intervention and investigation
3. **Level 3**: Emergency response and rollback

---

## Risk Assessment

### Technical Risks

#### High Risk
- **Database Connection Issues**: Mitigated by connection pooling and health checks
- **Google Cloud Service Outages**: Mitigated by fallback mechanisms and monitoring
- **Memory Leaks**: Mitigated by proper resource management and monitoring

#### Medium Risk
- **Rate Limiting Bypass**: Mitigated by multiple layers of protection
- **File Upload Vulnerabilities**: Mitigated by comprehensive validation
- **AI Service Failures**: Mitigated by fallback to markitdown

#### Low Risk
- **Minor Performance Degradation**: Mitigated by monitoring and optimization
- **Configuration Errors**: Mitigated by validation and testing

### Business Risks

#### High Risk
- **Data Loss**: Mitigated by automated backups and redundancy
- **Service Downtime**: Mitigated by health monitoring and quick recovery
- **Security Breaches**: Mitigated by comprehensive security measures

#### Medium Risk
- **Cost Overruns**: Mitigated by monitoring and cost controls
- **Performance Issues**: Mitigated by optimization and scaling

---

## Future Enhancements

### Planned Features

#### Short Term (3-6 months)
- **Enhanced AI Models**: Integration with more advanced LLM models
- **Real-time Collaboration**: Multi-user editing capabilities
- **Advanced Analytics**: Usage analytics and insights
- **Mobile Application**: Native mobile app for iOS/Android

#### Medium Term (6-12 months)
- **Enterprise Features**: SSO integration, advanced permissions
- **API Marketplace**: Third-party integrations
- **Advanced Workflows**: Custom conversion pipelines
- **Machine Learning**: Predictive analytics and recommendations

#### Long Term (12+ months)
- **Multi-tenant Architecture**: SaaS platform for multiple organizations
- **Global Deployment**: Multi-region deployment for better performance
- **Advanced AI**: Custom AI models for specific industries
- **Blockchain Integration**: Immutable audit trails

### Technical Improvements

#### Performance Optimization
- **Caching Layer**: Redis caching for frequently accessed data
- **CDN Integration**: Global content delivery network
- **Database Sharding**: Horizontal scaling for large datasets
- **Microservices**: Decomposition into smaller, focused services

#### Security Enhancements
- **Zero Trust Architecture**: Advanced security model
- **Encryption at Rest**: Full data encryption
- **Advanced Authentication**: Multi-factor authentication
- **Compliance**: SOC 2, GDPR, HIPAA compliance

---

## Conclusion

The MDraft Technical Design Document provides a comprehensive overview of the system architecture, implementation details, and operational procedures. The system is designed with scalability, security, and maintainability in mind, using modern technologies and best practices.

Key strengths of the architecture include:
- **Modular Design**: Application factory pattern with clear separation of concerns
- **Scalable Architecture**: Asynchronous processing with Celery and Cloud Tasks
- **Comprehensive Security**: Multi-layered security with authentication, authorization, and data protection
- **Robust Monitoring**: Structured logging, health checks, and error tracking
- **Cloud-Native**: Built for Google Cloud with managed services

The system is production-ready and can handle the current workload while providing a foundation for future growth and enhancements.

---

**Document Control**
- **Version**: 1.0
- **Last Updated**: December 2024
- **Next Review**: March 2025
- **Approved By**: Technical Architecture Team
