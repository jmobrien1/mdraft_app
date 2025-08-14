# mdraft - Comprehensive As-Built and Technical Design Document

## Executive Summary

mdraft is a production-ready Flask-based SaaS application that provides document-to-markdown conversion services with integrated AI-powered proposal assistance tools. The application leverages Google Cloud Platform services for scalability, reliability, and advanced document processing capabilities. Designed for government contractors and proposal teams, mdraft streamlines the RFP analysis and proposal development process.

### Key Features
- **Document Conversion**: Multi-engine PDF/DOCX to Markdown conversion with OCR support
- **AI Proposal Tools**: Free-tier AI assistance for RFP analysis and proposal generation
- **Background Processing**: Asynchronous job processing with real-time status tracking
- **Google Cloud Integration**: Comprehensive GCP service utilization for scalability
- **Production Ready**: Structured logging, monitoring, security, and error handling
- **Non-Blocking UI**: Modern web interface with real-time status updates

### Business Value
- **Time Savings**: Automated document conversion reduces manual transcription time by 80%
- **Quality Improvement**: AI-powered analysis ensures comprehensive RFP coverage
- **Cost Efficiency**: Free-tier tools provide immediate value without upfront investment
- **Scalability**: Cloud-native architecture supports enterprise-level workloads

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  Web UI (Flask Templates)  │  REST API  │  Admin Interface     │
│  - Non-blocking status UI  │  - JSON responses │  - User mgmt   │
│  - Real-time feedback      │  - Error handling │  - Analytics   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    Application Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  Flask App (Blueprint-based)  │  Celery Workers  │  CLI Tools   │
│  - Request routing            │  - Async tasks   │  - Admin ops │
│  - Authentication             │  - Job processing│  - Monitoring│
│  - Rate limiting              │  - Error recovery│  - Debugging │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                     Service Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  AI Tools  │  Storage  │  Text Loader  │  LLM Client  │  Tasks  │
│  - Chunking│  - GCS    │  - Extraction │  - OpenAI    │  - Queue│
│  - Merging │  - Caching│  - Truncation │  - Error hdl │  - Retry│
│  - Schema  │  - CDN    │  - Validation │  - Rate limit│  - DLQ  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    Infrastructure Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Google Cloud Storage  │  Cloud Tasks  │  Redis  │
│  - User data │  - File storage        │  - Job queue  │  - Cache│
│  - Job state │  - CDN delivery        │  - Scheduling │  - Sessions│
│  - Analytics │  - Backup/archive      │  - Retry logic│  - Rate limit│
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Render Platform                          │
├─────────────────────────────────────────────────────────────────┤
│  Web Service  │  Worker Service  │  Cron Service  │  Database  │
│  (mdraft-web) │  (mdraft-worker) │  (mdraft-cleanup) │ (PostgreSQL) │
│  - Gunicorn   │  - Celery        │  - Scheduled   │  - Managed │
│  - 1 worker   │  - Multi-thread  │  - Cleanup     │  - Backup  │
│  - 2 threads  │  - Auto-scale    │  - Monitoring  │  - HA      │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                    Google Cloud Platform                      │
├───────────────────────────────────────────────────────────────┤
│  Cloud Storage  │  Cloud Tasks  │  Document AI  │  Vertex AI  │
│  - File buckets │  - Job queue  │  - OCR/Text   │  - AI models│
│  - CDN cache    │  - Scheduling │  - Extraction │  - Inference│
│  - Lifecycle    │  - Retry      │  - Tables     │  - Batch    │
└───────────────────────────────────────────────────────────────┘
```

### Data Flow Architecture

```
1. Document Upload Flow:
   Client → Flask App → GCS Storage → Cloud Tasks → Celery Worker → Document AI → Markdown → GCS → Client

2. AI Tools Flow:
   Client → Flask App → Text Loader → AI Tools → LLM Client → OpenAI → Response Processing → Client

3. Background Processing Flow:
   Upload → Job Creation → Task Queue → Worker Processing → Status Updates → Webhook (optional)
```

## Technical Stack

### Backend Framework
- **Flask 3.0.3**: Modern Python web framework with blueprint architecture
  - Blueprint-based modular design for maintainability
  - Application factory pattern for flexible configuration
  - Request context management and error handling
- **Gunicorn**: Production WSGI server with optimized configuration
  - Single worker with 2 threads for memory efficiency
  - 120-second timeout for long-running operations
  - Graceful shutdown handling
- **Python 3.11.11**: Latest stable Python runtime with performance improvements

### Database & ORM
- **PostgreSQL**: Primary production database (Cloud SQL)
  - ACID compliance for data integrity
  - Connection pooling for performance
  - Automated backups and point-in-time recovery
- **SQLite**: Development database for local development
- **SQLAlchemy 3.1.1**: Modern ORM with type annotations
  - Declarative mapping with type hints
  - Relationship management and lazy loading
  - Query optimization and caching
- **Alembic 1.13.1**: Database migration management
  - Version-controlled schema changes
  - Rollback capabilities
  - Environment-specific migrations
- **psycopg[binary] 3.2.9**: PostgreSQL adapter with binary protocol

### Cloud Services (Google Cloud Platform)

#### Storage & CDN
- **Cloud Storage**: Primary file storage with advanced features
  - Multi-region buckets for global access
  - Object lifecycle management
  - Signed URLs for secure access
  - Streaming uploads for large files
- **Cloud CDN**: Content delivery network
  - Global edge caching
  - Automatic cache invalidation
  - Bandwidth optimization

#### Compute & Processing
- **Cloud Tasks**: Asynchronous task processing
  - Reliable message delivery
  - Automatic retry with exponential backoff
  - Dead letter queues for failed tasks
  - Task scheduling and rate limiting
- **Document AI**: Advanced document processing
  - OCR for scanned documents
  - Table extraction and structure recognition
  - Form parsing and data extraction
  - Multi-language support
- **Vertex AI**: AI/ML model hosting and inference
  - Model versioning and deployment
  - Auto-scaling inference endpoints
  - Batch prediction capabilities
  - Model monitoring and logging

#### Security & Management
- **Secret Manager**: Secure credential management
  - Centralized secret storage
  - Version control for secrets
  - IAM-based access control
  - Automatic rotation capabilities
- **Cloud SQL**: Managed PostgreSQL database
  - Automated backups and maintenance
  - High availability configuration
  - Connection encryption
  - Performance monitoring

### AI/ML Integration
- **OpenAI API**: GPT-4o-mini for AI-powered text generation
  - Structured JSON responses with schema validation
  - Rate limiting and error handling
  - Token optimization for cost efficiency
  - Fallback mechanisms for reliability
- **JSON Schema Validation**: Structured AI responses
  - Type-safe response handling
  - Schema evolution support
  - Validation error reporting
- **Text Chunking**: Large document processing optimization
  - Configurable chunk sizes (3000-8000 characters)
  - Overlap handling for context preservation
  - Memory-efficient streaming processing

### Asynchronous Processing
- **Celery 5.4.0**: Distributed task queue
  - Task routing and prioritization
  - Worker pool management
  - Result backend integration
  - Task monitoring and metrics
- **Redis 5.0.7**: Message broker and result backend
  - In-memory caching for performance
  - Session storage
  - Rate limiting counters
  - Pub/sub messaging
- **Thread-based Workers**: Scalable processing architecture
  - Configurable concurrency levels
  - Memory-efficient processing
  - Graceful shutdown handling

### Security & Authentication
- **Flask-Bcrypt**: Password hashing with salt
  - Configurable work factor
  - Secure password verification
  - Migration support for hash upgrades
- **Flask-Login**: Session management
  - User session tracking
  - Remember me functionality
  - Session security features
- **Flask-Limiter**: Rate limiting and abuse protection
  - IP-based rate limiting
  - User-based rate limiting
  - Custom rate limit rules
  - Rate limit headers
- **CORS**: Cross-origin resource sharing
  - Configurable allowed origins
  - Credential support
  - Preflight request handling
- **Security Headers**: XSS, CSRF, and other protections
  - Content Security Policy
  - X-Frame-Options
  - X-Content-Type-Options
  - Strict-Transport-Security

### File Processing
- **markitdown**: Open-source document conversion
  - PDF to Markdown conversion
  - DOCX to Markdown conversion
  - Table preservation
  - Image handling
- **PyPDF2/PyPDF**: PDF processing
  - Text extraction
  - Metadata handling
  - Page manipulation
- **filetype**: MIME-type validation
  - Secure file type detection
  - Extension validation
  - Malicious file detection
- **reportlab**: PDF generation
  - Dynamic PDF creation
  - Template-based generation
  - Image embedding

### Monitoring & Observability
- **Sentry**: Error tracking and performance monitoring
  - Real-time error reporting
  - Performance profiling
  - Release tracking
  - User feedback integration
- **Structured Logging**: JSON-formatted logs with correlation IDs
  - Request tracing
  - Performance metrics
  - Error context
  - Audit trail
- **Health Checks**: Application and database health monitoring
  - Liveness probes
  - Readiness probes
  - Dependency health checks
  - Custom health metrics

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
- Environment-based configuration with secure defaults
- Structured JSON logging with correlation IDs and request tracing
- Security headers and CORS configuration for web security
- Rate limiting with IP allowlisting and user-based limits
- Request ID middleware for distributed tracing
- Sentry integration for error tracking and performance monitoring
- Global error handlers for consistent error responses

### Blueprint Architecture

The application is organized into focused blueprints for maintainability and scalability:

#### 1. **Main Routes** (`app/routes.py`)
- Core API endpoints and health checks
- AI generation endpoints with robust error handling
- Development and diagnostic endpoints
- Request validation and sanitization

#### 2. **UI** (`app/ui.py`)
- Web interface templates and static assets
- User experience components
- Responsive design implementation

#### 3. **Beta** (`app/beta.py`)
- Beta features and experimental functionality
- Feature flag management
- User feedback collection

#### 4. **API Convert** (`app/api_convert.py`)
- Document conversion endpoints
- File upload handling and validation
- Conversion status tracking
- Public mode support for unauthenticated access

#### 5. **API Queue** (`app/api_queue.py`)
- Job status and queue management
- Background task monitoring
- Queue health and performance metrics

#### 6. **API Usage** (`app/api_usage.py`)
- Usage tracking and analytics
- Rate limit enforcement
- Billing integration

#### 7. **API Estimate** (`app/api_estimate.py`)
- Cost estimation for document processing
- Page count analysis
- Pricing calculations

#### 8. **Admin** (`app/admin.py`)
- Administrative interface
- User management
- System monitoring
- Configuration management

#### 9. **Billing** (`app/billing.py`)
- Stripe integration for payment processing
- Subscription management
- Invoice generation
- Usage-based billing

#### 10. **Health** (`app/health.py`)
- Health check endpoints
- Dependency monitoring
- Performance metrics
- System status reporting

#### 11. **Worker Routes** (`app/worker_routes.py`)
- Background task endpoints
- Job processing status
- Error handling and retry logic

### Data Models

#### User Management (`app/models.py`)
```python
class User(UserMixin, db.Model):
    """Represent a registered user of the mdraft system."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="F&F", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[List["ApiKey"]] = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
```

#### Job Tracking (`app/models.py`)
```python
class Job(db.Model):
    """Represent a document conversion job."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    gcs_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")
```

#### API Key Management (`app/models_apikey.py`)
```python
class ApiKey(db.Model):
    """Represent an API key for programmatic access."""
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")
```

#### Conversion Tracking (`app/models_conversion.py`)
```python
class Conversion(db.Model):
    """Represent a document conversion with detailed tracking."""
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
```

## Service Layer Architecture

### AI Tools Service (`app/services/ai_tools.py`)

The AI tools service provides intelligent document analysis and proposal assistance with robust error handling and performance optimization:

**Key Features:**
- **Text Chunking**: Processes large documents in configurable chunks (3000-8000 characters)
- **Schema Validation**: Ensures AI responses match expected JSON schemas
- **Error Recovery**: Fallback mechanisms for failed API calls
- **Memory Management**: Streaming processing to handle large documents
- **Response Merging**: Intelligent merging of partial responses from multiple chunks

**Configuration Parameters:**
```python
# Environment-driven limits with safe defaults
CHUNK_SIZE_CHARS = int(os.getenv("MDRAFT_CHUNK_SIZE_CHARS") or 3000)  # conservative
MAX_CHUNKS = int(os.getenv("MDRAFT_MAX_CHUNKS") or 12)                # hard stop
TRUNCATE_CHARS = int(os.getenv("MDRAFT_TRUNCATE_CHARS") or 200_000)   # pre-truncate big docs
MAX_MERGED_ITEMS = int(os.getenv("MDRAFT_MAX_MERGED_ITEMS") or 300)   # cap list growth
DEFAULT_MODEL_MAX_TOKENS = int(os.getenv("MDRAFT_MAX_TOKENS") or 700) # arrays don't need a lot
RELAX_MAX_OBJS_PER_CHUNK = int(os.getenv("MDRAFT_RELAX_MAX_OBJS_PER_CHUNK") or 80)
```

**Core Functions:**
```python
def run_prompt(prompt_path: str, rfp_text: str, json_schema: Optional[Dict[str, Any]], model_name: str | None = None) -> Any:
    """
    Primary entry point for AI-powered document analysis.
    
    Features:
    - Input truncation for large documents
    - Streaming chunk processing
    - Robust error handling
    - Response validation and normalization
    - Memory-efficient processing
    """

def _extract_first_json_array(s: str):
    """Extract JSON array from model response with fallback parsing."""

def _extract_relaxed_array(s: str):
    """Grab every complete {...} object even from truncated arrays."""

def _normalize_eval_criteria(arr):
    """Normalize evaluation criteria data with weight coercion."""
```

### LLM Client Service (`app/services/llm_client.py`)

The LLM client provides a robust interface to OpenAI's API with comprehensive error handling:

**Key Features:**
- **Error Mapping**: Maps OpenAI errors to user-friendly codes
- **Rate Limiting**: Built-in rate limit handling with exponential backoff
- **Response Format**: Intelligent handling of JSON response format
- **Token Optimization**: Configurable token limits for cost efficiency
- **Fallback Mechanisms**: Graceful degradation for API failures

**Error Codes:**
- `openai_auth`: Authentication issues
- `openai_permission`: Model access or quota issues
- `openai_rate_limit`: Rate limiting with retry guidance
- `openai_bad_request`: Invalid requests or model configuration
- `openai_unprocessable`: Input too long or invalid
- `openai_not_found`: Model not found
- `openai_connection`: Network connectivity issues
- `openai_api`: Transient server errors
- `openai_other`: Unhandled errors with safe detail inclusion

### Storage Service (`app/services/storage.py`)

The storage service provides a unified interface for Google Cloud Storage operations:

**Key Features:**
- **File Upload**: Streaming uploads with progress tracking
- **File Download**: Efficient downloading with caching
- **File Management**: Lifecycle management and cleanup
- **Security**: Signed URLs for secure access
- **CDN Integration**: Automatic CDN caching and invalidation

### Text Loader Service (`app/services/text_loader.py`)

The text loader service extracts and processes text from converted documents:

**Key Features:**
- **Document Retrieval**: Fetches converted markdown from database
- **Text Truncation**: Configurable truncation for large documents
- **Error Handling**: Graceful handling of missing or corrupted documents
- **Performance**: Efficient querying with proper indexing

## API Design

### RESTful API Endpoints

#### Document Conversion
```
POST /api/convert
- Upload and convert documents to markdown
- Supports PDF, DOCX, and other formats
- Returns conversion status and download links

GET /api/conversions
- List recent conversions with pagination
- Supports public mode for unauthenticated access
- Returns plain array with limit/offset in headers

GET /api/conversions/{id}
- Get specific conversion details
- Includes status, error messages, and download links

GET /api/conversions/{id}/markdown
- Download markdown content directly
- Supports streaming for large files
```

#### AI Tools
```
POST /api/generate/compliance-matrix
- Extract compliance requirements from RFP
- Returns structured JSON array of requirements
- Includes requirement types and proposal sections

POST /api/generate/evaluation-criteria
- Extract evaluation factors and weights
- Returns normalized criteria with weight coercion
- Handles percentage and numeric formats

POST /api/generate/annotated-outline
- Generate proposal outline with RFP references
- Returns markdown outline with annotations
- Includes source section mapping

POST /api/generate/submission-checklist
- Extract submission requirements and deadlines
- Returns categorized checklist items
- Includes format and delivery constraints
```

#### Development and Diagnostics
```
GET /api/dev/openai-ping
- Test OpenAI API connectivity
- Returns connection status and response time

GET /api/dev/openai-ping-detailed
- Detailed OpenAI API diagnostics
- Returns raw error codes and messages

GET /api/dev/selftest
- Comprehensive system health check
- Tests database, prompts, and OpenAI connectivity

GET /api/dev/check-prompts
- Verify prompt file availability
- Reports missing or corrupted prompt files

POST /api/dev/gen-smoke
- Direct AI tool testing with hardcoded RFP snippet
- Bypasses document loader for isolated testing
```

### Error Handling

The API implements comprehensive error handling with consistent response formats:

**Error Response Format:**
```json
{
  "error": "error_code",
  "hint": "User-friendly guidance",
  "detail": "Technical details for debugging"
}
```

**Common Error Codes:**
- `file_required`: No file provided in upload
- `file_empty`: Uploaded file is empty
- `file_type_not_allowed`: Unsupported file format
- `extract_failed`: Document processing failed
- `storage_error`: File storage operation failed
- `openai_auth`: OpenAI authentication failed
- `openai_rate_limit`: OpenAI rate limit exceeded
- `json_parse`: AI response parsing failed
- `model_error`: Generic AI model error

### Rate Limiting

The API implements multi-level rate limiting:

**IP-based Limits:**
- Global: 120 requests per minute
- Upload: 10 requests per minute
- AI Tools: 60 requests per minute

**User-based Limits:**
- Authenticated users: Higher limits based on plan
- API key users: Configurable limits per key
- Anonymous users: Reduced limits for abuse prevention

## Frontend Architecture

### Web Interface (`app/templates/`)

The web interface provides a modern, responsive user experience with non-blocking interactions:

**Key Features:**
- **Non-blocking Status UI**: Real-time status updates without page blocking
- **Drag-and-Drop Upload**: Intuitive file upload interface
- **Real-time Feedback**: Live status updates during processing
- **Error Handling**: User-friendly error messages with actionable guidance
- **Responsive Design**: Mobile-friendly interface with adaptive layouts

**Status UI Implementation:**
```html
<div id="ai-status" aria-live="polite" class="hidden"></div>

<style>
#ai-status { 
  position: fixed; right: 16px; bottom: 16px; 
  padding: 10px 12px; 
  background: rgba(0,0,0,.8); color:#fff; 
  border-radius: 10px; 
  font: 14px/1.3 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; 
  box-shadow: 0 6px 18px rgba(0,0,0,.25); 
  max-width: 360px; z-index: 1000; 
}
#ai-status.hidden { display: none; }
#ai-status .spinner { 
  display:inline-block; width:14px; height:14px; 
  border:2px solid #fff; border-right-color: transparent; 
  border-radius:50%; margin-right:8px; 
  animation:spin .9s linear infinite; vertical-align:-2px;
}
@keyframes spin{to{transform:rotate(360deg)}}
.btn-busy[disabled]{opacity:.6; cursor: wait;}
</style>
```

**JavaScript Architecture:**
```javascript
// Non-blocking status UI helpers
function showStatus(msg, busy = false) {
  const el = document.getElementById('ai-status');
  if (!el) return;
  el.innerHTML = busy ? `<span class="spinner"></span>${msg}` : msg;
  el.classList.toggle('hidden', !msg);
}

function withBusyButton(btn, busy) {
  if (!btn) return;
  btn.classList.toggle('btn-busy', busy);
  btn.disabled = !!busy;
  btn.setAttribute('aria-busy', busy ? 'true' : 'false');
}

async function runTool(btnSelector, url, body, onSuccess) {
  const btn = document.querySelector(btnSelector);
  showStatus('Working… this can take ~10–30s depending on RFP size.', true);
  withBusyButton(btn, true);

  try {
    const data = await apiPostJSON(url, body);
    if (typeof onSuccess === 'function') onSuccess(data);
    showStatus('Done.');
    setTimeout(() => showStatus('', false), 1600);
  } catch (err) {
    console.error('AI tool failed', err);
    let msg = 'Something went wrong.';
    if (err.json && err.json.error) {
      const { error, hint, detail } = err.json;
      msg = `${error}${hint ? ' — ' + hint : ''}${detail ? ' — ' + detail : ''}`;
    } else if (err.text) {
      msg = `${err.http || ''} ${err.text.slice(0,180)}`;
    }
    showStatus(msg, false);
  } finally {
    withBusyButton(btn, false);
  }
}
```

### Static Assets (`app/static/`)

The static assets provide the foundation for the user interface:

**CSS Architecture:**
- **Base Styles**: Typography, layout, and component styles
- **Responsive Design**: Mobile-first approach with breakpoints
- **Component Library**: Reusable UI components
- **Accessibility**: ARIA support and keyboard navigation

**JavaScript Modules:**
- **Core Utilities**: Common functions for DOM manipulation
- **API Client**: HTTP request handling with error management
- **UI Components**: Interactive components with state management
- **Form Handling**: Validation and submission logic

## Security Architecture

### Authentication & Authorization

**User Authentication:**
- **Password Hashing**: Bcrypt with configurable work factor
- **Session Management**: Secure session handling with expiration
- **Remember Me**: Secure token-based persistent login
- **Password Reset**: Secure token-based password recovery

**API Key Authentication:**
- **Key Generation**: Cryptographically secure random keys
- **Key Hashing**: Secure storage with bcrypt hashing
- **Usage Tracking**: Last used timestamps and usage analytics
- **Key Rotation**: Support for key expiration and rotation

**Authorization:**
- **Role-based Access**: User roles and permissions
- **Resource Ownership**: User-specific resource access
- **Admin Access**: Administrative interface protection
- **Rate Limiting**: Abuse prevention and fair usage

### Data Protection

**Input Validation:**
- **File Upload Security**: MIME type validation and virus scanning
- **SQL Injection Prevention**: Parameterized queries and ORM usage
- **XSS Prevention**: Output encoding and Content Security Policy
- **CSRF Protection**: Token-based request validation

**Data Encryption:**
- **Transport Security**: TLS 1.3 for all communications
- **Storage Encryption**: Database and file storage encryption
- **Secret Management**: Secure credential storage and rotation
- **Key Management**: Secure key generation and storage

**Privacy & Compliance:**
- **Data Minimization**: Collection of only necessary data
- **Data Retention**: Configurable retention policies
- **User Rights**: Data export and deletion capabilities
- **Audit Logging**: Comprehensive activity logging

## Performance & Scalability

### Performance Optimization

**Database Optimization:**
- **Indexing Strategy**: Optimized indexes for common queries
- **Query Optimization**: Efficient SQL with proper joins
- **Connection Pooling**: Managed database connections
- **Caching**: Redis-based caching for frequently accessed data

**Application Optimization:**
- **Code Optimization**: Efficient algorithms and data structures
- **Memory Management**: Streaming processing for large files
- **Async Processing**: Non-blocking operations for better responsiveness
- **CDN Integration**: Global content delivery for static assets

**Infrastructure Optimization:**
- **Auto-scaling**: Dynamic resource allocation based on demand
- **Load Balancing**: Distributed traffic across multiple instances
- **Caching Layers**: Multi-level caching for performance
- **Resource Monitoring**: Real-time performance monitoring

### Scalability Architecture

**Horizontal Scaling:**
- **Stateless Design**: Application instances can be scaled independently
- **Database Sharding**: Support for database partitioning
- **Microservices Ready**: Modular architecture for service decomposition
- **Containerization**: Docker support for consistent deployment

**Vertical Scaling:**
- **Resource Allocation**: Configurable CPU and memory limits
- **Performance Tuning**: Optimized configuration for different workloads
- **Monitoring**: Resource usage tracking and optimization
- **Capacity Planning**: Predictive scaling based on usage patterns

## Monitoring & Observability

### Logging Strategy

**Structured Logging:**
```python
class JSONFormatter(logging.Formatter):
    """Format log records as JSON with correlation IDs."""
    
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

**Log Levels:**
- **DEBUG**: Detailed debugging information
- **INFO**: General application information
- **WARNING**: Warning conditions that don't stop execution
- **ERROR**: Error conditions that affect functionality
- **CRITICAL**: Critical errors that may cause system failure

### Health Monitoring

**Health Check Endpoints:**
```
GET /healthz
- Basic application health check
- Returns 200 OK if application is running

GET /healthz/detailed
- Comprehensive health check
- Tests all dependencies and services
- Returns detailed status information
```

**Monitoring Metrics:**
- **Application Metrics**: Request rates, response times, error rates
- **Database Metrics**: Connection pool usage, query performance
- **Infrastructure Metrics**: CPU, memory, disk usage
- **Business Metrics**: User activity, conversion rates, revenue

### Error Tracking

**Sentry Integration:**
- **Error Capture**: Automatic error reporting and aggregation
- **Performance Monitoring**: Request timing and performance profiling
- **Release Tracking**: Version-based error tracking
- **User Feedback**: Error context and user impact assessment

**Error Handling:**
- **Global Error Handlers**: Consistent error response formatting
- **Error Recovery**: Graceful degradation and fallback mechanisms
- **Error Reporting**: Detailed error context for debugging
- **User Communication**: User-friendly error messages

## Deployment & Operations

### Deployment Architecture

**Render Platform Configuration:**
```yaml
# render.yaml
services:
  - type: web
    name: mdraft-web
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: ./bin/start-web.sh
    envVars:
      - key: WEB_CONCURRENCY
        value: 1
      - key: PYTHONUNBUFFERED
        value: 1
      - key: MDRAFT_MODEL
        value: gpt-4o-mini
      - key: MDRAFT_PUBLIC_MODE
        value: 1
      - key: MDRAFT_CHUNK_SIZE_CHARS
        value: 3000
      - key: MDRAFT_MAX_CHUNKS
        value: 12
      - key: MDRAFT_TRUNCATE_CHARS
        value: 200000
      - key: MDRAFT_MAX_MERGED_ITEMS
        value: 300
      - key: MDRAFT_MAX_TOKENS
        value: 700
      - key: MDRAFT_RELAX_MAX_OBJS_PER_CHUNK
        value: 80
```

**Start Script Configuration:**
```bash
#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-}"
if [[ -z "$PORT" ]]; then
  PORT="10000"
  echo "[start-web] PORT was empty; using fallback ${PORT}"
else
  echo "[start-web] PORT=${PORT}"
fi

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
echo "[start-web] WEB_CONCURRENCY=${WEB_CONCURRENCY}"

exec gunicorn run:app \
  --workers "${WEB_CONCURRENCY}" \
  --threads 2 \
  --timeout 120 \
  --bind "0.0.0.0:${PORT}"
```

### Environment Configuration

**Production Environment Variables:**
```bash
# Application Configuration
FLASK_ENV=production
SECRET_KEY=<secure-random-key>
DATABASE_URL=<postgresql-connection-string>

# Google Cloud Configuration
GOOGLE_APPLICATION_CREDENTIALS=<service-account-key>
GCS_BUCKET_NAME=<storage-bucket>
GCS_PROCESSED_BUCKET_NAME=<processed-bucket>

# OpenAI Configuration
OPENAI_API_KEY=<openai-api-key>
MDRAFT_MODEL=gpt-4o-mini

# Performance Configuration
WEB_CONCURRENCY=1
MDRAFT_CHUNK_SIZE_CHARS=3000
MDRAFT_MAX_CHUNKS=12
MDRAFT_TRUNCATE_CHARS=200000
MDRAFT_MAX_MERGED_ITEMS=300
MDRAFT_MAX_TOKENS=700

# Security Configuration
MDRAFT_PUBLIC_MODE=1
RATE_LIMIT_STORAGE_URI=<redis-connection-string>
```

### Backup & Recovery

**Database Backup Strategy:**
- **Automated Backups**: Daily automated backups with point-in-time recovery
- **Backup Retention**: 30-day backup retention with weekly archives
- **Backup Testing**: Regular backup restoration testing
- **Disaster Recovery**: Cross-region backup replication

**File Storage Backup:**
- **Object Versioning**: Automatic versioning for all uploaded files
- **Lifecycle Management**: Automated archival and deletion policies
- **Cross-Region Replication**: Geographic redundancy for critical data
- **Backup Monitoring**: Automated backup success monitoring

### Maintenance & Updates

**Deployment Process:**
1. **Code Review**: Automated testing and code review
2. **Staging Deployment**: Testing in staging environment
3. **Production Deployment**: Blue-green deployment with rollback capability
4. **Health Monitoring**: Post-deployment health checks
5. **Rollback Plan**: Automated rollback on health check failures

**Update Strategy:**
- **Dependency Updates**: Regular security and feature updates
- **Database Migrations**: Version-controlled schema changes
- **Configuration Updates**: Environment-specific configuration management
- **Monitoring Updates**: Continuous monitoring and alerting improvements

## Testing Strategy

### Testing Pyramid

**Unit Tests:**
- **Service Layer**: Comprehensive testing of business logic
- **Data Models**: Model validation and relationship testing
- **Utility Functions**: Helper function testing
- **Configuration**: Environment configuration testing

**Integration Tests:**
- **API Endpoints**: End-to-end API testing
- **Database Operations**: Database integration testing
- **External Services**: Third-party service integration testing
- **Authentication**: Authentication flow testing

**End-to-End Tests:**
- **User Workflows**: Complete user journey testing
- **File Processing**: Document upload and conversion testing
- **AI Tools**: AI-powered feature testing
- **Error Scenarios**: Error handling and recovery testing

### Test Implementation

**Test Framework:**
```python
# tests/test_ai_tools.py
import pytest
from app.services.ai_tools import run_prompt, _extract_first_json_array

class TestAITools:
    def test_text_chunking(self):
        """Test text chunking with various input sizes."""
        # Test implementation
        
    def test_json_extraction(self):
        """Test JSON extraction from model responses."""
        # Test implementation
        
    def test_error_handling(self):
        """Test error handling and recovery."""
        # Test implementation
```

**Test Configuration:**
```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --verbose
    --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
```

## Future Roadmap

### Planned Features

**Short-term (3-6 months):**
- **Enhanced AI Models**: Integration with additional AI providers
- **Advanced Analytics**: User behavior and usage analytics
- **Team Collaboration**: Multi-user workspace and sharing
- **API Enhancements**: GraphQL API and webhook improvements

**Medium-term (6-12 months):**
- **Mobile Application**: Native mobile apps for iOS and Android
- **Enterprise Features**: SSO, LDAP integration, and advanced security
- **Advanced AI Tools**: Custom model training and fine-tuning
- **Marketplace**: Third-party plugin and integration marketplace

**Long-term (12+ months):**
- **AI-Powered Insights**: Predictive analytics and recommendations
- **Global Expansion**: Multi-language and multi-region support
- **Advanced Automation**: Workflow automation and process optimization
- **Industry Specialization**: Domain-specific AI models and tools

### Technical Improvements

**Performance Enhancements:**
- **Caching Strategy**: Multi-level caching for improved performance
- **Database Optimization**: Query optimization and indexing improvements
- **CDN Enhancement**: Advanced CDN configuration for global performance
- **Load Balancing**: Intelligent load balancing and traffic management

**Scalability Improvements:**
- **Microservices Architecture**: Service decomposition for better scalability
- **Event-Driven Architecture**: Event sourcing and CQRS implementation
- **Container Orchestration**: Kubernetes deployment for better resource management
- **Auto-scaling**: Advanced auto-scaling based on custom metrics

**Security Enhancements:**
- **Zero Trust Architecture**: Advanced security model implementation
- **Compliance Framework**: SOC 2, GDPR, and other compliance certifications
- **Advanced Monitoring**: Security monitoring and threat detection
- **Penetration Testing**: Regular security assessments and vulnerability management

## Conclusion

mdraft represents a modern, scalable, and production-ready SaaS application that demonstrates best practices in web application development. The application's architecture provides a solid foundation for future growth and feature development while maintaining high standards for security, performance, and user experience.

The comprehensive integration with Google Cloud Platform services, robust error handling, and modern development practices make mdraft a reliable and maintainable solution for document processing and AI-powered proposal assistance. The application's modular design and comprehensive testing strategy ensure long-term maintainability and scalability.

As the application continues to evolve, the established patterns and architectural decisions will support rapid feature development while maintaining the high standards for quality, security, and performance that have been established in the current implementation.
