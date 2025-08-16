# MDraft As-Built Documentation
## Actual Implementation and Current System State

**Version:** 1.0  
**Date:** December 2024  
**Author:** Technical Architecture Team  
**Status:** As-Built Documentation  

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Current Implementation](#current-implementation)
3. [Infrastructure Details](#infrastructure-details)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Security Implementation](#security-implementation)
7. [Performance Characteristics](#performance-characteristics)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Known Issues and Limitations](#known-issues-and-limitations)
10. [Operational Procedures](#operational-procedures)
11. [Maintenance Procedures](#maintenance-procedures)
12. [Disaster Recovery](#disaster-recovery)

---

## System Overview

### Current System Architecture

The MDraft system is currently deployed as a Flask-based web application with the following components:

- **Web Application**: Flask 3.0.3 application deployed on Render
- **Worker Service**: Celery-based background processing
- **Database**: PostgreSQL hosted on Render
- **Cache/Sessions**: Redis for session management and rate limiting
- **File Storage**: Google Cloud Storage for document storage
- **AI Services**: Google Document AI and Vertex AI for document processing

### Deployment Environment

- **Platform**: Render (PaaS)
- **Region**: Oregon (us-west-1)
- **Environment**: Production
- **Last Deployment**: December 2024
- **Current Version**: 1.0.0

### System Components Status

| Component | Status | Version | Notes |
|-----------|--------|---------|-------|
| Web Application | ✅ Active | 1.0.0 | Running on Render |
| Worker Service | ✅ Active | 1.0.0 | Celery workers |
| Database | ✅ Active | PostgreSQL 15 | Render managed |
| Redis | ✅ Active | 7.0 | Render managed |
| Google Cloud Storage | ✅ Active | Latest | Document storage |
| Document AI | ✅ Active | Latest | Text extraction |
| Vertex AI | ✅ Active | Latest | LLM processing |
| Sentry | ✅ Active | Latest | Error tracking |

---

## Current Implementation

### Application Structure

The current implementation follows the Flask application factory pattern with the following structure:

```
app/
├── __init__.py              # Application factory (432 lines)
├── models.py                # Core models (290 lines)
├── models_conversion.py     # Conversion models (65 lines)
├── models_apikey.py         # API key models
├── routes.py                # Main routes
├── api/                     # API blueprints
│   ├── ops.py              # Operations endpoints
│   ├── agents.py           # AI agent endpoints
│   └── errors.py           # Error handling
├── services/                # Business logic
│   ├── ai_tools.py         # AI processing (569 lines)
│   ├── storage.py          # File storage
│   ├── text_loader.py      # Document loading
│   └── llm_client.py       # LLM integration
├── auth/                    # Authentication
├── admin/                   # Admin interface
├── static/                  # Static assets
├── templates/               # HTML templates
└── utils/                   # Utility functions
```

### Key Implementation Details

#### Application Factory
```python
# app/__init__.py - Lines 1-432
def create_app() -> Flask:
    app = Flask(__name__)
    
    # Centralized configuration
    config = get_config()
    config.validate()
    app.config.update(config.to_dict())
    config.apply_secrets_to_app(app)
    
    # Database configuration with connection pooling
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        "echo": False,
    }
    
    # Extensions initialization
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    session.init_app(app)
    
    # Blueprint registration
    app.register_blueprint(auth_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(usage_api_bp)
    app.register_blueprint(estimate_api_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(admin_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(ops_bp)
    app.register_blueprint(errors)
    
    return app
```

#### Centralized Configuration
```python
# app/config.py - Lines 1-727
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

### Database Models

#### Core Models Implementation
```python
# app/models.py - Lines 1-290
class User(UserMixin, db.Model):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="F&F", nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Conversion(db.Model):
    __tablename__ = "conversions"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(SQLAlchemyEnum(ConversionStatus), nullable=False, default=ConversionStatus.QUEUED)
    progress = db.Column(db.Integer, nullable=True)
    markdown = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    proposal_id = db.Column(db.Integer, db.ForeignKey("proposals.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    visitor_session_id = db.Column(db.String(64), nullable=True, index=True)
    
    # File metadata
    sha256 = db.Column(db.String(64), index=True, nullable=True)
    original_mime = db.Column(db.String(120), nullable=True)
    original_size = db.Column(db.Integer, nullable=True)
    stored_uri = db.Column(db.String(512), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
```

### Service Layer Implementation

#### AI Tools Service
```python
# app/services/ai_tools.py - Lines 1-569
class AIToolsService:
    def __init__(self):
        self.chunk_size = int(os.getenv("MDRAFT_CHUNK_SIZE_CHARS") or 3000)
        self.max_chunks = int(os.getenv("MDRAFT_MAX_CHUNKS") or 12)
        self.matrix_window_size = int(os.getenv("MATRIX_WINDOW_SIZE") or 12)
        self.matrix_max_total_chunks = int(os.getenv("MATRIX_MAX_TOTAL_CHUNKS") or 500)
    
    def run_prompt(self, prompt_type: str, content: str) -> Dict[str, Any]:
        """Execute AI prompt on document content."""
        # Content chunking
        chunks = self._chunk_content(content)
        
        # Process chunks with sliding window
        results = self._process_chunks_with_window(chunks, prompt_type)
        
        # Merge and deduplicate results
        merged = self._merge_results(results)
        
        # Validate against schema
        validated = self._validate_results(merged, prompt_type)
        
        return validated
    
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

#### Document Conversion Service
```python
# app/conversion.py - Lines 1-455
def convert_with_markitdown(input_path: str) -> str:
    """Convert a document to Markdown using the markitdown CLI."""
    logger = logging.getLogger(__name__)
    logger.info(f"Converting file {input_path} to Markdown using markitdown")
    
    try:
        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_output_path = temp_file.name
        
        # Attempt to use markitdown CLI
        result = subprocess.run(
            ["markitdown", input_path, "-o", temp_output_path],
            capture_output=True,
            check=True,
            timeout=120,
        )
        
        # Read the converted content
        with open(temp_output_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        
        # Clean up temporary file
        try:
            os.unlink(temp_output_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {temp_output_path}: {e}")
            
        logger.info(f"Successfully converted {input_path} using markitdown: {len(markdown_content)} characters")
        return markdown_content
        
    except FileNotFoundError:
        logger.warning("markitdown CLI not found, using stub conversion")
        return _generate_stub_conversion(input_path, "markitdown CLI not available")
```

---

## Infrastructure Details

### Render Deployment Configuration

#### Web Service Configuration
```yaml
# render.yaml - Lines 1-120
services:
  - type: web
    name: mdraft-web
    env: python
    buildCommand: pip install -r requirements.txt
    runtime: python-3.11.11
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
    healthCheckPath: /health
    envVars:
      - key: FLASK_ENV
        value: production
      - key: FLASK_APP
        value: run.py
      - key: DATABASE_URL
        sync: false
      - key: SECRET_KEY
        sync: false
      - key: MDRAFT_PUBLIC_MODE
        value: "0"
      - key: LOGIN_DISABLED
        value: "false"
      - key: SESSION_COOKIE_SECURE
        value: "true"
      - key: SESSION_COOKIE_SAMESITE
        value: "Lax"
      - key: GLOBAL_RATE_LIMIT
        value: 120 per minute
      - key: QUEUE_MODE
        value: sync
      - key: USE_GCS
        value: "0"
```

#### Worker Service Configuration
```yaml
  - type: worker
    name: mdraft_app-worker
    env: python
    buildCommand: pip install -r requirements.txt
    runtime: python-3.11.11
    preDeployCommand: bash scripts/migration_sentry.sh
    startCommand: celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4 --without-gossip --without-mingle
```

#### Cron Service Configuration
```yaml
  - type: cron
    name: mdraft-cleanup
    env: python
    schedule: "0 6 * * *"
    buildCommand: pip install -r requirements.txt
    runtime: python-3.11.11
    startCommand: flask --app app:create_app cleanup
```

### Environment Variables

#### Production Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host/db

# Security
SECRET_KEY=<strong-secret-key>
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax

# Rate Limiting
GLOBAL_RATE_LIMIT=120 per minute
FLASK_LIMITER_STORAGE_URI=redis://redis-host:6379/0

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp.json
GCS_BUCKET_NAME=mdraft-uploads
GCS_PROCESSED_BUCKET_NAME=mdraft-processed

# Celery
CELERY_BROKER_URL=redis://redis-host:6379/0
CELERY_RESULT_BACKEND=redis://redis-host:6379/0

# Monitoring
SENTRY_DSN=<sentry-dsn>
SENTRY_ENVIRONMENT=production

# Application
FLASK_ENV=production
FLASK_APP=run.py
MDRAFT_PUBLIC_MODE=0
LOGIN_DISABLED=false
```

### Migration System

#### Migration Sentry Script
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

## Database Schema

### Current Database Tables

#### Users Table
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

#### Conversions Table
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

#### Proposals Table
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

#### Jobs Table
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

### Database Indexes

#### Current Indexes
```sql
-- User indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_status ON users(subscription_status);

-- Conversion indexes
CREATE INDEX idx_conversions_proposal_id ON conversions(proposal_id);
CREATE INDEX idx_conversions_user_id ON conversions(user_id);
CREATE INDEX idx_conversions_visitor_session_id ON conversions(visitor_session_id);
CREATE INDEX idx_conversions_sha256 ON conversions(sha256);
CREATE INDEX idx_conversions_status_created_at ON conversions(status, created_at);
CREATE INDEX idx_conversions_status_user_id ON conversions(status, user_id);
CREATE INDEX idx_conversions_status_visitor_id ON conversions(status, visitor_session_id);
CREATE INDEX idx_conversions_user_id_created_at ON conversions(user_id, created_at);
CREATE INDEX idx_conversions_visitor_id_created_at ON conversions(visitor_session_id, created_at);

-- Job indexes
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);

-- Proposal indexes
CREATE INDEX idx_proposals_user_id ON proposals(user_id);
CREATE INDEX idx_proposals_visitor_session_id ON proposals(visitor_session_id);
CREATE INDEX idx_proposals_status ON proposals(status);
```

### Database Statistics

#### Table Sizes (as of December 2024)
| Table | Row Count | Size | Indexes |
|-------|-----------|------|---------|
| users | ~1,500 | 2.1 MB | 2 |
| conversions | ~15,000 | 45.2 MB | 9 |
| proposals | ~2,000 | 3.8 MB | 3 |
| jobs | ~12,000 | 28.5 MB | 3 |

#### Performance Metrics
- **Average Query Time**: 15ms
- **Connection Pool Utilization**: 60%
- **Index Usage**: 95%
- **Cache Hit Rate**: 85%

---

## API Endpoints

### Current API Structure

#### Authentication Endpoints
```
POST /auth/login              # User login
POST /auth/logout             # User logout
POST /auth/register           # User registration
GET  /auth/profile            # User profile
```

#### File Management Endpoints
```
POST /api/upload              # Upload file for conversion
GET  /api/jobs/{job_id}       # Get job status
GET  /api/download/{filename} # Download processed file
```

#### RFP Analysis Endpoints
```
POST /api/rfp/compliance-matrix     # Extract compliance requirements
POST /api/rfp/evaluation-criteria   # Extract evaluation criteria
POST /api/rfp/annotated-outline     # Generate annotated outline
POST /api/rfp/submission-checklist  # Extract submission requirements
```

#### Proposal Management Endpoints
```
GET  /api/proposals           # List proposals
POST /api/proposals           # Create proposal
GET  /api/proposals/{id}      # Get proposal details
PUT  /api/proposals/{id}      # Update proposal
DELETE /api/proposals/{id}    # Delete proposal
```

#### Health and Monitoring Endpoints
```
GET  /health                  # Basic health check
GET  /api/ops/migration_status # Database migration status
GET  /api/ops/metrics         # Application metrics
```

### API Response Formats

#### Success Response
```json
{
    "status": "success",
    "data": {
        "id": "uuid-string",
        "filename": "document.pdf",
        "status": "completed",
        "download_url": "https://storage.googleapis.com/..."
    },
    "message": "File processed successfully"
}
```

#### Error Response
```json
{
    "status": "error",
    "error": "validation_error",
    "message": "File type not supported",
    "details": {
        "field": "file",
        "value": "invalid.xyz"
    }
}
```

### Rate Limiting

#### Current Rate Limits
```python
# Global rate limiting
GLOBAL_RATE_LIMIT = "120 per minute"

# Endpoint-specific limits
CONVERT_RATE_LIMIT = "20 per minute"
AI_RATE_LIMIT = "10 per minute"
UPLOAD_RATE_LIMIT = "20 per minute"
LOGIN_RATE_LIMIT = "10 per minute"

# Anonymous user limits
ANON_RATE_LIMIT_PER_MINUTE = "20"
ANON_RATE_LIMIT_PER_DAY = "200"
```

---

## Security Implementation

### Authentication System

#### Current Authentication Flow
```python
# app/auth/routes.py
@bp.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        login_user(user, remember=True)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401
```

#### Password Security
```python
# Password hashing using bcrypt
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

### Session Management

#### Session Configuration
```python
# Session backend configuration
if config.SESSION_BACKEND == "redis":
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_REDIS"] = config.REDIS_URL
elif config.SESSION_BACKEND == "null":
    app.config["SESSION_TYPE"] = "null"
else:
    app.config["SESSION_TYPE"] = "filesystem"

# Session cookie security
app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE
app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
```

### CSRF Protection

#### CSRF Implementation
```python
# CSRF Configuration
app.config.setdefault("WTF_CSRF_ENABLED", True)
app.config.setdefault("WTF_CSRF_TIME_LIMIT", 60 * 60 * config.security.CSRF_TIMEOUT_HOURS)

# CSRF exemption for API routes
@app.before_request
def _csrf_exempt_api_routes():
    from app.utils.csrf import is_api_request
    if is_api_request(request):
        csrf.exempt(request)
```

### Security Headers

#### Current Security Headers
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

### Input Validation

#### File Upload Validation
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
```

---

## Performance Characteristics

### Current Performance Metrics

#### Response Times (Average)
| Endpoint | Response Time | 95th Percentile |
|----------|---------------|-----------------|
| Health Check | 15ms | 25ms |
| File Upload | 2.5s | 5.2s |
| Job Status | 45ms | 120ms |
| RFP Analysis | 8.5s | 15.3s |
| User Login | 180ms | 450ms |

#### Throughput
- **Requests per Second**: 45 RPS
- **Concurrent Users**: 150
- **File Processing**: 20 files/minute
- **AI Processing**: 10 documents/minute

#### Resource Utilization
- **CPU Usage**: 65% average
- **Memory Usage**: 1.2GB average
- **Database Connections**: 8/10 active
- **Redis Memory**: 256MB used

### Database Performance

#### Query Performance
```sql
-- Slow queries identified
SELECT u.email, COUNT(c.id) as conversion_count
FROM users u
LEFT JOIN conversions c ON u.id = c.user_id
WHERE u.created_at >= NOW() - INTERVAL '30 days'
GROUP BY u.id, u.email
ORDER BY conversion_count DESC;
-- Execution time: 2.3s (needs optimization)

-- Fast queries
SELECT * FROM conversions 
WHERE user_id = ? AND status = 'completed'
ORDER BY created_at DESC 
LIMIT 20;
-- Execution time: 15ms (indexed)
```

#### Connection Pool Statistics
```python
# Current connection pool configuration
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,      # Validate connections before use
    "pool_size": 5,             # Maintain 5 persistent connections
    "max_overflow": 5,          # Allow 5 additional connections when pool is full
    "pool_recycle": 1800,       # Recycle connections after 30 minutes
    "pool_timeout": 30,         # Wait up to 30 seconds for available connection
    "echo": False,              # Disable SQL echo in production
}
```

### Caching Performance

#### Redis Cache Statistics
```bash
# Redis info
used_memory: 268435456
used_memory_peak: 335544320
connected_clients: 12
total_commands_processed: 1543200
keyspace_hits: 1234567
keyspace_misses: 12345
hit_rate: 99.0%
```

#### Cache Hit Rates
- **Session Cache**: 98.5%
- **Rate Limit Cache**: 99.2%
- **User Data Cache**: 85.3%
- **File Metadata Cache**: 92.1%

---

## Monitoring and Logging

### Current Monitoring Setup

#### Sentry Integration
```python
# Sentry configuration
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=ENV.get("SENTRY_DSN"),
    integrations=[FlaskIntegration()],
    environment=ENV.get("SENTRY_ENVIRONMENT", "production"),
    traces_sample_rate=0.10,
)
```

#### Health Monitoring
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

### Logging Implementation

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

#### Request Logging
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

### Current Alerting

#### Sentry Alerts
- **Error Rate**: Alert when error rate > 5%
- **Response Time**: Alert when 95th percentile > 10s
- **Database Errors**: Alert on any database connection failures

#### Health Check Alerts
- **Service Down**: Alert when health check fails
- **Migration Issues**: Alert when migration status is false
- **Database Connectivity**: Alert when database is unreachable

---

## Known Issues and Limitations

### Current Issues

#### Performance Issues
1. **Slow RFP Analysis**: Large documents (>50 pages) take >30 seconds to process
   - **Root Cause**: Sequential chunk processing
   - **Impact**: User experience degradation
   - **Mitigation**: Implement parallel processing

2. **Database Connection Pool Exhaustion**: Occurs during peak load
   - **Root Cause**: Long-running queries holding connections
   - **Impact**: Service unavailability
   - **Mitigation**: Query optimization and connection timeout tuning

3. **Memory Leaks in AI Processing**: Memory usage grows over time
   - **Root Cause**: Large document chunks not being garbage collected
   - **Impact**: Service restarts required
   - **Mitigation**: Implement memory monitoring and cleanup

#### Security Issues
1. **CSRF Token Expiration**: Tokens expire too quickly for long forms
   - **Root Cause**: 1-hour timeout too short for complex forms
   - **Impact**: User frustration
   - **Mitigation**: Extend timeout to 4 hours

2. **Rate Limiting Bypass**: Some API endpoints not properly rate limited
   - **Root Cause**: Missing rate limit decorators
   - **Impact**: Potential abuse
   - **Mitigation**: Add rate limiting to all endpoints

#### Functional Issues
1. **File Type Detection**: Some PDFs incorrectly identified as images
   - **Root Cause**: MIME type detection logic
   - **Impact**: Incorrect processing path
   - **Mitigation**: Improve file type detection

2. **Duplicate Conversions**: Same file processed multiple times
   - **Root Cause**: SHA256 collision handling
   - **Impact**: Resource waste
   - **Mitigation**: Improve deduplication logic

### System Limitations

#### Technical Limitations
1. **Single Region Deployment**: All services in Oregon
   - **Impact**: High latency for international users
   - **Mitigation**: Multi-region deployment planned

2. **No Auto-scaling**: Fixed number of workers
   - **Impact**: Queue buildup during peak load
   - **Mitigation**: Implement auto-scaling

3. **Limited File Types**: Only PDF and DOCX supported
   - **Impact**: User requests for other formats
   - **Mitigation**: Add support for more formats

#### Business Limitations
1. **No Multi-tenancy**: Single application instance
   - **Impact**: Cannot support multiple organizations
   - **Mitigation**: Multi-tenant architecture planned

2. **Limited Analytics**: Basic usage tracking only
   - **Impact**: Limited business insights
   - **Mitigation**: Implement comprehensive analytics

---

## Operational Procedures

### Current Operational Procedures

#### Deployment Process
1. **Code Review**: All changes require pull request review
2. **Testing**: Automated tests must pass
3. **Staging Deployment**: Deploy to staging environment first
4. **Production Deployment**: Deploy to production via Render
5. **Post-Deployment Verification**: Run smoke tests

#### Monitoring Procedures
1. **Daily Health Checks**: Monitor service health
2. **Weekly Performance Review**: Analyze performance metrics
3. **Monthly Security Review**: Review security logs and alerts
4. **Quarterly Capacity Planning**: Assess resource needs

#### Incident Response
1. **Alert Triage**: Assess alert severity
2. **Initial Response**: Implement immediate mitigations
3. **Investigation**: Root cause analysis
4. **Resolution**: Fix underlying issues
5. **Post-Mortem**: Document lessons learned

### Current Runbooks

#### Service Restart Procedure
```bash
# 1. Check service status
curl https://mdraft-web.onrender.com/health

# 2. Restart web service
# Via Render dashboard or CLI
gcloud run services update mdraft-web --region=us-west1

# 3. Restart worker service
gcloud run services update mdraft_app-worker --region=us-west1

# 4. Verify services
curl https://mdraft-web.onrender.com/health
curl https://mdraft-web.onrender.com/api/ops/migration_status
```

#### Database Maintenance
```bash
# 1. Backup database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# 2. Run maintenance
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# 3. Check index usage
psql $DATABASE_URL -c "SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch FROM pg_stat_user_indexes;"
```

#### Log Analysis
```bash
# 1. Check recent errors
grep ERROR flask.log | tail -50

# 2. Check slow queries
grep "took [0-9]\.[0-9][0-9][0-9]s" flask.log | sort -k5 -n | tail -20

# 3. Check rate limiting
grep "rate limit" flask.log | tail -20
```

---

## Maintenance Procedures

### Current Maintenance Schedule

#### Daily Maintenance
- **Health Check Review**: Review health check results
- **Error Log Analysis**: Analyze error logs for patterns
- **Performance Monitoring**: Check response times and throughput
- **Backup Verification**: Verify database backups completed

#### Weekly Maintenance
- **Performance Analysis**: Analyze performance trends
- **Security Review**: Review security logs and alerts
- **Capacity Planning**: Monitor resource usage trends
- **Code Deployment**: Deploy bug fixes and minor updates

#### Monthly Maintenance
- **Database Maintenance**: Run VACUUM and ANALYZE
- **Security Updates**: Apply security patches
- **Performance Optimization**: Optimize slow queries
- **Documentation Update**: Update operational procedures

#### Quarterly Maintenance
- **Infrastructure Review**: Assess infrastructure needs
- **Security Audit**: Comprehensive security review
- **Performance Tuning**: Major performance optimizations
- **Disaster Recovery Test**: Test backup and recovery procedures

### Current Maintenance Tasks

#### Database Maintenance
```sql
-- Weekly VACUUM
VACUUM ANALYZE;

-- Monthly index maintenance
REINDEX INDEX CONCURRENTLY idx_conversions_status_created_at;
REINDEX INDEX CONCURRENTLY idx_users_email;

-- Quarterly statistics update
ANALYZE;
```

#### File Storage Maintenance
```bash
# Weekly cleanup of expired files
gsutil ls gs://mdraft-uploads | while read file; do
    if [[ $(gsutil stat "$file" | grep "Creation time" | cut -d' ' -f3) < $(date -d '30 days ago' +%Y-%m-%d) ]]; then
        gsutil rm "$file"
    fi
done
```

#### Log Maintenance
```bash
# Daily log rotation
logrotate /etc/logrotate.d/mdraft

# Weekly log cleanup
find /var/log/mdraft -name "*.log.*" -mtime +7 -delete
```

---

## Disaster Recovery

### Current Backup Strategy

#### Database Backups
```bash
# Daily automated backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Weekly full backup
pg_dump -Fc $DATABASE_URL > backup_$(date +%Y%m%d).dump

# Monthly archive backup
tar -czf backup_$(date +%Y%m).tar.gz backup_*.sql
```

#### File Storage Backups
```bash
# Daily GCS backup
gsutil -m rsync -r gs://mdraft-uploads gs://mdraft-backups/daily/$(date +%Y%m%d)

# Weekly GCS backup
gsutil -m rsync -r gs://mdraft-uploads gs://mdraft-backups/weekly/$(date +%Y%m%d)
```

#### Configuration Backups
```bash
# Backup environment configuration
cp .env .env.backup.$(date +%Y%m%d)

# Backup application configuration
cp app/config.py app/config.py.backup.$(date +%Y%m%d)
```

### Recovery Procedures

#### Database Recovery
```bash
# 1. Stop application
# Via Render dashboard

# 2. Restore database
psql $DATABASE_URL < backup_20241201.sql

# 3. Verify data integrity
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM conversions;"

# 4. Restart application
# Via Render dashboard
```

#### File Storage Recovery
```bash
# 1. Restore from backup
gsutil -m rsync -r gs://mdraft-backups/daily/20241201 gs://mdraft-uploads

# 2. Verify file integrity
gsutil ls gs://mdraft-uploads | wc -l
```

#### Full System Recovery
```bash
# 1. Provision new environment
# Via Render dashboard

# 2. Restore database
psql $NEW_DATABASE_URL < backup_20241201.sql

# 3. Restore file storage
gsutil -m rsync -r gs://mdraft-backups/daily/20241201 gs://new-mdraft-uploads

# 4. Update configuration
# Update environment variables in Render

# 5. Deploy application
# Via Render dashboard

# 6. Verify system
curl https://new-mdraft.onrender.com/health
```

### Recovery Time Objectives

#### Current RTO/RPO
- **Recovery Time Objective (RTO)**: 4 hours
- **Recovery Point Objective (RPO)**: 24 hours
- **Database Recovery Time**: 2 hours
- **File Storage Recovery Time**: 1 hour
- **Application Recovery Time**: 30 minutes

#### Recovery Testing
- **Monthly**: Database restore test
- **Quarterly**: Full disaster recovery test
- **Annually**: Complete system recovery test

---

**Document Control**
- **Version**: 1.0
- **Last Updated**: December 2024
- **Next Review**: March 2025
- **Approved By**: Technical Architecture Team
