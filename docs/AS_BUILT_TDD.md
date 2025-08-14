# mdraft - As-Built and Technical Design Document

## Executive Summary

mdraft is a Flask-based SaaS application that provides document-to-markdown conversion services with integrated AI-powered proposal assistance tools. The application leverages Google Cloud Platform services for scalability, reliability, and advanced document processing capabilities.

### Key Features
- **Document Conversion**: PDF/DOCX to Markdown conversion using multiple engines
- **AI Proposal Tools**: Free-tier AI assistance for RFP analysis and proposal generation
- **Background Processing**: Asynchronous job processing with status tracking
- **Google Cloud Integration**: Comprehensive GCP service utilization
- **Production Ready**: Structured logging, monitoring, and security features

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  Web UI (Flask Templates)  │  REST API  │  Admin Interface     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    Application Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  Flask App (Blueprint-based)  │  Celery Workers  │  CLI Tools   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                     Service Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  AI Tools  │  Storage  │  Text Loader  │  LLM Client  │  Tasks  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    Infrastructure Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Google Cloud Storage  │  Cloud Tasks  │  Redis  │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Render Platform                          │
├─────────────────────────────────────────────────────────────────┤
│  Web Service  │  Worker Service  │  Cron Service  │  Database  │
│  (mdraft-web) │  (mdraft-worker) │  (mdraft-cleanup) │ (PostgreSQL) │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                    Google Cloud Platform                      │
├───────────────────────────────────────────────────────────────┤
│  Cloud Storage  │  Cloud Tasks  │  Document AI  │  Vertex AI  │
└───────────────────────────────────────────────────────────────┘
```

## Technical Stack

### Backend Framework
- **Flask 3.0.3**: Modern Python web framework with blueprint architecture
- **Gunicorn**: Production WSGI server with multi-worker configuration
- **Python 3.11.11**: Latest stable Python runtime

### Database & ORM
- **PostgreSQL**: Primary production database (Cloud SQL)
- **SQLite**: Development database
- **SQLAlchemy 3.1.1**: Modern ORM with type annotations
- **Alembic 1.13.1**: Database migration management
- **psycopg[binary] 3.2.9**: PostgreSQL adapter

### Cloud Services (Google Cloud Platform)
- **Cloud Storage**: File storage with streaming uploads
- **Cloud Tasks**: Asynchronous task processing
- **Document AI**: Advanced document processing and OCR
- **Vertex AI**: AI/ML model hosting and inference
- **Secret Manager**: Secure credential management
- **Cloud SQL**: Managed PostgreSQL database

### AI/ML Integration
- **OpenAI API**: GPT-4o-mini for AI-powered text generation
- **JSON Schema Validation**: Structured AI responses
- **Text Chunking**: Large document processing optimization

### Asynchronous Processing
- **Celery 5.4.0**: Distributed task queue
- **Redis 5.0.7**: Message broker and result backend
- **Thread-based Workers**: Scalable processing architecture

### Security & Authentication
- **Flask-Bcrypt**: Password hashing
- **Flask-Login**: Session management
- **Flask-Limiter**: Rate limiting and abuse protection
- **CORS**: Cross-origin resource sharing
- **Security Headers**: XSS, CSRF, and other protections

### File Processing
- **markitdown**: Open-source document conversion
- **PyPDF2/PyPDF**: PDF processing
- **filetype**: MIME-type validation
- **reportlab**: PDF generation

### Monitoring & Observability
- **Sentry**: Error tracking and performance monitoring
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Health Checks**: Application and database health monitoring

## Application Structure

### Core Application Factory (`app/__init__.py`)

The application uses a factory pattern for flexible configuration and testing:

```python
def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configuration management
    # Extension initialization
    # Blueprint registration
    # Error handlers
    # Middleware setup
```

**Key Features:**
- Environment-based configuration
- Structured JSON logging with correlation IDs
- Security headers and CORS configuration
- Rate limiting with IP allowlisting
- Request ID middleware for tracing
- Sentry integration for error tracking

### Blueprint Architecture

The application is organized into focused blueprints:

1. **Main Routes** (`app/routes.py`): Core API endpoints and health checks
2. **UI** (`app/ui.py`): Web interface templates
3. **Beta** (`app/beta.py`): Beta features and AI tools
4. **API Convert** (`app/api_convert.py`): Document conversion endpoints
5. **API Queue** (`app/api_queue.py`): Job status and queue management
6. **API Usage** (`app/api_usage.py`): Usage tracking and analytics
7. **API Estimate** (`app/api_estimate.py`): Cost estimation
8. **Admin** (`app/admin.py`): Administrative interface
9. **Billing** (`app/billing.py`): Stripe integration
10. **Health** (`app/health.py`): Health check endpoints
11. **Worker Routes** (`app/worker_routes.py`): Background task endpoints

### Data Models

#### User Management
```python
class User(UserMixin, db.Model):
    """Represent a registered user of the mdraft system."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="F&F", nullable=False)
    # ... additional fields
```

#### Job Tracking
```python
class Job(db.Model):
    """Represent a document conversion job."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    gcs_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ... additional fields
```

#### API Key Management
```python
class ApiKey(db.Model):
    """Represent an API key for programmatic access."""
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # ... additional fields
```

## Service Layer Architecture

### AI Tools Service (`app/services/ai_tools.py`)

The AI tools service provides intelligent document analysis and proposal assistance:

**Key Features:**
- **Text Chunking**: Processes large documents in 8000-character chunks
- **Schema Validation**: Ensures AI responses match expected JSON schemas
- **Dev Stub Mode**: Deterministic responses for development and testing
- **Error Recovery**: Retry logic with correction hints
- **Array Merging**: Deduplicates and merges results from multiple chunks

**Core Functions:**
```python
def run_prompt(prompt_path: str, rfp_text: str, json_schema: Optional[Dict[str, Any]]) -> Any:
    """Primary entry point for AI-powered document analysis."""
    
def _chunk_text(s: str, max_chars: int = 8000) -> list[str]:
    """Split text into manageable chunks for AI processing."""
    
def _merge_arrays(items: list[list[dict]], key_candidates: list[str]) -> list[dict]:
    """Merge and deduplicate array results from multiple chunks."""
    
def _merge_outline(parts: list[dict]) -> dict:
    """Merge outline results with annotations."""
```

**Supported AI Tools:**
1. **Compliance Matrix**: Extracts requirements and compliance criteria
2. **Evaluation Criteria**: Identifies evaluation factors and weights
3. **Annotated Outline**: Generates proposal structure with RFP references
4. **Submission Checklist**: Creates submission requirements checklist

### Storage Service (`app/services/storage.py`)

Unified storage abstraction supporting both Google Cloud Storage and local file system:

**Key Features:**
- **Dual Storage Backends**: GCS for production, local for development
- **Streaming Uploads**: Efficient large file handling
- **Signed URLs**: Secure file access with expiration
- **Error Handling**: Consistent error handling across backends

**Core Methods:**
```python
class Storage:
    def write_bytes(self, path: str, data: bytes) -> None
    def read_bytes(self, path: str) -> bytes
    def delete(self, path: str) -> None
    def generate_signed_url(self, path: str, expiration: int = 3600) -> str
    def list_files(self, prefix: str = "") -> List[str]
```

### LLM Client Service (`app/services/llm_client.py`)

OpenAI API integration with JSON response formatting:

**Key Features:**
- **JSON Response Formatting**: Forces structured JSON responses
- **Configurable Models**: Supports different OpenAI models
- **Timeout Handling**: Configurable request timeouts
- **Error Handling**: Robust error handling and retry logic

### Text Loader Service (`app/services/text_loader.py`)

Document text extraction and caching:

**Key Features:**
- **Multiple Sources**: GCS, local files, and direct text input
- **Caching**: Reduces redundant processing
- **Error Handling**: Graceful handling of missing or corrupted files
- **Format Support**: Multiple document formats

## API Design

### RESTful API Endpoints

#### Document Conversion
```
POST /api/convert/upload          # Upload and convert document
GET  /api/convert/status/{job_id} # Get conversion status
GET  /api/convert/download/{job_id} # Download converted file
```

#### AI Tools (Free Tier)
```
POST /api/generate/compliance-matrix     # Generate compliance matrix
POST /api/generate/evaluation-criteria   # Generate evaluation criteria
POST /api/generate/annotated-outline     # Generate annotated outline
POST /api/generate/submission-checklist  # Generate submission checklist
```

#### Job Management
```
GET  /api/queue/status/{job_id}    # Get job status
GET  /api/queue/jobs               # List user jobs
DELETE /api/queue/jobs/{job_id}    # Delete job
```

#### Usage Analytics
```
GET  /api/usage/stats              # Get usage statistics
GET  /api/usage/limits             # Get usage limits
```

#### Health & Diagnostics
```
GET  /health                       # Basic health check
GET  /healthz                      # Simple health check
GET  /api/dev/diag                 # Development diagnostics
GET  /api/dev/openai-ping          # OpenAI connectivity test
```

### Request/Response Patterns

**Standard Response Format:**
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

**Error Response Format:**
```json
{
  "error": "error_type",
  "detail": "Detailed error message",
  "code": 400
}
```

**AI Tool Response Format:**
```json
[
  {
    "requirement_id": "L-1",
    "requirement_text": "Offeror shall submit a Technical Volume...",
    "rfp_reference": "Section L, p.10",
    "requirement_type": "format",
    "suggested_proposal_section": "I. Technical Approach"
  }
]
```

## Background Processing

### Celery Configuration

**Worker Configuration:**
```python
celery = Celery('mdraft')
celery.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)
```

**Task Types:**
1. **Document Conversion**: PDF/DOCX to Markdown conversion
2. **Document AI Processing**: OCR and text extraction
3. **File Cleanup**: Automatic file deletion and cleanup
4. **Usage Tracking**: Analytics and billing updates

### Queue Management

**Queue Modes:**
- **Sync Mode**: Immediate processing (development)
- **Async Mode**: Background processing (production)
- **Hybrid Mode**: Selective background processing

## Security Architecture

### Authentication & Authorization

**User Authentication:**
- Email/password authentication with bcrypt hashing
- Session-based authentication with Flask-Login
- API key authentication for programmatic access

**Access Control:**
- Allowlist-based user registration
- Role-based access control (Free, Pro, Admin)
- IP-based rate limiting with allowlisting

### Data Protection

**File Security:**
- MIME-type validation for uploads
- Virus scanning integration capability
- Secure file storage with signed URLs
- Automatic file cleanup and retention policies

**API Security:**
- Rate limiting per endpoint
- CORS configuration for cross-origin requests
- Input validation and sanitization
- SQL injection prevention with SQLAlchemy

### Infrastructure Security

**Google Cloud Security:**
- Service account-based authentication
- IAM role-based access control
- VPC network isolation
- Secret Manager for credential management

## Monitoring & Observability

### Logging Strategy

**Structured Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Document conversion completed",
  "correlation_id": "req-12345",
  "request_id": "req-12345",
  "job_id": "job-67890",
  "logger": "app.services.conversion"
}
```

**Log Levels:**
- **DEBUG**: Detailed debugging information
- **INFO**: General application flow
- **WARNING**: Potential issues
- **ERROR**: Error conditions
- **CRITICAL**: System failures

### Health Monitoring

**Health Check Endpoints:**
- `/health`: Database connectivity and basic health
- `/healthz`: Simple availability check
- `/api/dev/diag`: Development diagnostics

**Monitoring Metrics:**
- Request latency and throughput
- Error rates and types
- Database connection health
- Background task queue depth
- Storage usage and performance

### Error Tracking

**Sentry Integration:**
- Automatic error capture and reporting
- Performance monitoring
- Release tracking
- Environment-specific error handling

## Deployment Architecture

### Render Platform Configuration

**Web Service (`mdraft-web`):**
```yaml
type: web
name: mdraft-web
env: python
buildCommand: pip install -r requirements.txt
runtime: python-3.11.11
startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
healthCheckPath: /health
```

**Worker Service (`mdraft-worker`):**
```yaml
type: worker
name: mdraft_app-worker
env: python
startCommand: celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4
```

**Cron Service (`mdraft-cleanup`):**
```yaml
type: cron
name: mdraft-cleanup
schedule: "0 6 * * *"  # Daily at 06:00 UTC
startCommand: flask --app app:create_app cleanup
```

### Environment Configuration

**Required Environment Variables:**
```bash
# Core Configuration
FLASK_ENV=production
SECRET_KEY=<generated>
DATABASE_URL=postgresql://...

# Google Cloud Services
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp.json
GCS_BUCKET_NAME=mdraft-storage
CLOUD_TASKS_QUEUE_ID=mdraft-queue

# AI Services
OPENAI_API_KEY=<api_key>
MDRAFT_MODEL=gpt-4o-mini

# Monitoring
SENTRY_DSN=<sentry_dsn>
SENTRY_ENVIRONMENT=production

# Rate Limiting
GLOBAL_RATE_LIMIT=120 per minute
CONVERT_RATE_LIMIT_DEFAULT=20 per minute
AI_RATE_LIMIT_DEFAULT=10 per minute
```

## Performance Optimization

### Caching Strategy

**Redis Caching:**
- Session storage
- Task result caching
- API response caching
- Rate limiting storage

**Application Caching:**
- Document text caching
- User session caching
- Configuration caching

### Database Optimization

**Indexing Strategy:**
- User email index for authentication
- Job status index for filtering
- Created/updated timestamp indexes
- Foreign key indexes

**Query Optimization:**
- Eager loading for relationships
- Pagination for large result sets
- Connection pooling
- Query result caching

### File Processing Optimization

**Streaming Processing:**
- Large file streaming uploads
- Chunked document processing
- Memory-efficient text processing
- Background task processing

## Testing Strategy

### Test Types

**Unit Tests:**
- Service layer testing
- Model validation testing
- Utility function testing
- Configuration testing

**Integration Tests:**
- API endpoint testing
- Database integration testing
- External service integration testing
- Authentication flow testing

**End-to-End Tests:**
- Complete user workflow testing
- File upload and conversion testing
- AI tool integration testing
- Error handling testing

### Test Configuration

**Test Environment:**
- SQLite database for testing
- Mock external services
- In-memory file storage
- Test-specific configuration

**Test Data:**
- Fixture-based test data
- Factory pattern for model creation
- Isolated test databases
- Cleanup after tests

## Disaster Recovery

### Backup Strategy

**Database Backups:**
- Automated daily backups
- Point-in-time recovery capability
- Cross-region backup replication
- Backup verification and testing

**File Storage Backups:**
- GCS object versioning
- Cross-region replication
- Backup retention policies
- Recovery testing procedures

### High Availability

**Service Redundancy:**
- Multiple worker instances
- Load balancer configuration
- Database read replicas
- Failover procedures

**Monitoring and Alerting:**
- Service health monitoring
- Automated failover triggers
- Alert notification systems
- Incident response procedures

## Future Enhancements

### Planned Features

**AI Enhancements:**
- Multi-language support
- Custom model fine-tuning
- Advanced document analysis
- Real-time collaboration tools

**Performance Improvements:**
- CDN integration
- Advanced caching strategies
- Database sharding
- Microservice architecture

**Security Enhancements:**
- Multi-factor authentication
- Advanced threat detection
- Compliance certifications
- Enhanced audit logging

### Scalability Considerations

**Horizontal Scaling:**
- Stateless application design
- Database connection pooling
- Load balancer configuration
- Auto-scaling policies

**Vertical Scaling:**
- Resource monitoring
- Performance optimization
- Capacity planning
- Resource allocation strategies

## Conclusion

The mdraft application represents a modern, scalable SaaS platform that successfully integrates document processing capabilities with AI-powered analysis tools. The architecture demonstrates best practices in terms of:

- **Modularity**: Clean separation of concerns with blueprint architecture
- **Scalability**: Cloud-native design with horizontal scaling capabilities
- **Reliability**: Comprehensive error handling and monitoring
- **Security**: Multi-layered security approach
- **Maintainability**: Well-structured codebase with comprehensive documentation

The application is production-ready and provides a solid foundation for future enhancements and scaling requirements.

---

**Document Version**: 1.0  
**Last Updated**: January 2024  
**Author**: mdraft Development Team  
**Review Cycle**: Quarterly
