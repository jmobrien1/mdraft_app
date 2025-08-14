# mdraft - Technical Design Document (TDD)

## 1. Introduction

### 1.1 Purpose
This document provides a comprehensive technical design for mdraft, a document-to-markdown conversion SaaS platform. It outlines the system architecture, design decisions, and implementation strategies.

### 1.2 Scope
The document covers the complete technical architecture, including:
- System design and component interactions
- Database schema and data flow
- API design and security considerations
- Deployment and scaling strategies
- Performance and reliability requirements

### 1.3 Definitions
- **Conversion Job**: A single document conversion request
- **Worker**: Background service that processes conversion jobs
- **GCS**: Google Cloud Storage
- **Document AI**: Google's document processing service
- **markitdown**: Open-source document conversion tool

## 2. System Overview

### 2.1 Business Requirements
- Convert documents (PDF, DOCX) to Markdown format
- Support both synchronous and asynchronous processing
- Provide RESTful API for integration
- Implement rate limiting and security measures
- Support multiple users with usage tracking
- Provide web interface for document management

### 2.2 Functional Requirements
1. **Document Upload**: Secure file upload with validation
2. **Format Conversion**: Convert supported formats to Markdown
3. **Status Tracking**: Real-time job status updates
4. **Result Delivery**: Secure download of converted files
5. **User Management**: Authentication and authorization
6. **Usage Analytics**: Track conversion usage and limits

### 2.3 Non-Functional Requirements
- **Performance**: < 5s upload processing, < 2min conversion time
- **Scalability**: Support 100+ concurrent users
- **Reliability**: 99.9% uptime target
- **Security**: Encrypted storage, secure file access
- **Maintainability**: Modular design, comprehensive logging

## 3. Architecture Design

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  Web Browser  │  Mobile App  │  API Client  │  CLI Tool        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Presentation Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Flask Web App  │  API Gateway  │  Admin Dashboard              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Application Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Conversion Service  │  File Service  │  User Service           │
│  Queue Service      │  Billing Service│  Analytics Service      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Google Cloud Storage  │  Redis Cache            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  Google Document AI  │  Cloud Tasks  │  Sentry Monitoring       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Architecture

#### 3.2.1 Web Application Component
```
┌─────────────────┐
│   Flask App     │
├─────────────────┤
│  Request Router │
│  Authentication │
│  Rate Limiting  │
│  Error Handling │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Blueprint      │
│  Controllers    │
├─────────────────┤
│  API Routes     │
│  UI Routes      │
│  Admin Routes   │
└─────────────────┘
```

#### 3.2.2 Background Processing Component
```
┌─────────────────┐
│  Task Queue     │
├─────────────────┤
│  Celery         │
│  Cloud Tasks    │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Worker Pool    │
├─────────────────┤
│  Conversion     │
│  Workers        │
│  Cleanup        │
│  Workers        │
└─────────────────┘
```

### 3.3 Data Flow Architecture

#### 3.3.1 Document Upload Flow
```
1. Client Upload Request
   │
   ▼
2. File Validation (MIME, Size, Security)
   │
   ▼
3. Storage Decision (Local vs GCS)
   │
   ▼
4. Database Record Creation
   │
   ▼
5. Queue Task Creation
   │
   ▼
6. Response with Job ID
```

#### 3.3.2 Document Processing Flow
```
1. Worker Picks Task
   │
   ▼
2. File Retrieval (Local/GCS)
   │
   ▼
3. Conversion Engine Selection
   │
   ▼
4. Document Processing
   │
   ▼
5. Result Storage (GCS)
   │
   ▼
6. Database Status Update
   │
   ▼
7. Webhook Notification (if configured)
```

## 4. Database Design

### 4.1 Entity Relationship Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Users    │     │    Jobs     │     │ Conversions │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id (PK)     │◄────┤ user_id (FK)│     │ id (PK)     │
│ email       │     │ id (PK)     │     │ filename    │
│ password    │     │ filename    │     │ status      │
│ stripe_id   │     │ status      │     │ markdown    │
│ plan        │     │ gcs_uri     │     │ sha256      │
│ created_at  │     │ output_uri  │     │ stored_uri  │
└─────────────┘     │ created_at  │     │ created_at  │
                    └─────────────┘     └─────────────┘
                              │
                              ▼
                    ┌─────────────┐
                    │  Allowlist  │
                    ├─────────────┤
                    │ id (PK)     │
                    │ email       │
                    │ status      │
                    │ plan        │
                    │ created_at  │
                    └─────────────┘
```

### 4.2 Schema Design Principles

#### 4.2.1 Normalization Strategy
- **3NF Compliance**: Eliminate transitive dependencies
- **Denormalization**: Strategic denormalization for performance
- **Audit Trails**: Timestamp fields for all entities
- **Soft Deletes**: Status-based deletion for data retention

#### 4.2.2 Indexing Strategy
```sql
-- Primary indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX idx_conversions_sha256 ON conversions(sha256);
CREATE INDEX idx_allowlist_email ON allowlist(email);

-- Composite indexes for common queries
CREATE INDEX idx_jobs_created_status ON jobs(created_at, status);
CREATE INDEX idx_conversions_status_created ON conversions(status, created_at);
```

### 4.3 Data Migration Strategy
- **Alembic Migrations**: Version-controlled schema changes
- **Backward Compatibility**: Maintain API compatibility during migrations
- **Rollback Procedures**: Automated rollback capabilities
- **Data Validation**: Pre and post-migration data integrity checks

## 5. API Design

### 5.1 RESTful API Principles
- **Resource-Oriented**: URLs represent resources
- **Stateless**: No client-side state management
- **Cacheable**: Appropriate HTTP caching headers
- **Uniform Interface**: Consistent HTTP methods and status codes

### 5.2 API Endpoint Design

#### 5.2.1 Conversion API
```yaml
POST /api/convert:
  description: Upload and convert document
  request:
    multipart/form-data:
      file: Document file
      callback_url: Optional webhook URL
  response:
    200: Job created successfully
    400: Invalid request
    413: File too large
    415: Unsupported file type

GET /api/conversions/{id}:
  description: Get conversion status
  response:
    200: Conversion details
    404: Conversion not found

GET /api/conversions/{id}/markdown:
  description: Download markdown result
  response:
    200: Markdown content
    404: Conversion not found
    410: Conversion expired
```

#### 5.2.2 Queue Management API
```yaml
POST /api/queue/estimate:
  description: Estimate conversion time
  request:
    application/json:
      file_size: File size in bytes
      file_type: MIME type
  response:
    200: Estimated processing time

GET /api/queue/status:
  description: Get queue status
  response:
    200: Queue depth and processing stats
```

### 5.3 Error Handling Strategy
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error context"
  },
  "request_id": "correlation_id_for_tracking"
}
```

## 6. Security Design

### 6.1 Authentication & Authorization
- **API Key Authentication**: Secure key-based access
- **Session Management**: Secure session handling
- **Rate Limiting**: Per-user and global rate limits
- **Input Validation**: Comprehensive input sanitization

### 6.2 Data Protection
```python
# File upload security
def validate_file_upload(file):
    # MIME type validation
    allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    
    # Size limit validation
    max_size = 25 * 1024 * 1024  # 25MB
    
    # Content validation
    file_content = file.read(8192)
    file.seek(0)
    
    return validate_content(file_content, allowed_types)
```

### 6.3 Secure File Access
- **Signed URLs**: V4 signed URLs for GCS access
- **Time-limited Access**: Configurable URL expiration
- **Access Logging**: Comprehensive access audit trails
- **Encryption**: At-rest and in-transit encryption

## 7. Performance Design

### 7.1 Caching Strategy
```python
# Redis caching layers
CACHE_LAYERS = {
    'conversion_results': 3600,  # 1 hour
    'user_sessions': 86400,      # 24 hours
    'rate_limits': 60,           # 1 minute
    'file_metadata': 1800        # 30 minutes
}
```

### 7.2 Database Optimization
- **Connection Pooling**: SQLAlchemy connection management
- **Query Optimization**: Efficient query patterns
- **Read Replicas**: For read-heavy operations
- **Partitioning**: Time-based table partitioning

### 7.3 Asynchronous Processing
```python
# Task queue configuration
CELERY_CONFIG = {
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0',
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'UTC',
    'enable_utc': True,
    'task_routes': {
        'app.tasks.convert_document': {'queue': 'conversion'},
        'app.tasks.cleanup_files': {'queue': 'maintenance'}
    }
}
```

## 8. Scalability Design

### 8.1 Horizontal Scaling
- **Stateless Services**: No shared state between instances
- **Load Balancing**: Round-robin or least-connections
- **Auto-scaling**: Based on CPU, memory, and queue depth
- **Database Scaling**: Read replicas and connection pooling

### 8.2 Queue-based Architecture
```python
# Queue configuration
QUEUE_CONFIG = {
    'conversion_queue': {
        'max_concurrent': 10,
        'max_retries': 3,
        'retry_delay': 60,
        'dead_letter_queue': 'failed_conversions'
    },
    'cleanup_queue': {
        'max_concurrent': 5,
        'max_retries': 1,
        'retry_delay': 300
    }
}
```

### 8.3 Microservices Considerations
- **Service Boundaries**: Clear separation of concerns
- **API Gateway**: Centralized routing and authentication
- **Service Discovery**: Dynamic service registration
- **Circuit Breakers**: Fault tolerance patterns

## 9. Monitoring & Observability

### 9.1 Logging Strategy
```python
# Structured logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'json': {
            'class': 'app.utils.logging.JSONFormatter',
            'format': '%(timestamp)s %(level)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json'
        }
    },
    'loggers': {
        'app': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }
}
```

### 9.2 Metrics Collection
- **Application Metrics**: Request rates, response times, error rates
- **Business Metrics**: Conversion success rates, user engagement
- **Infrastructure Metrics**: CPU, memory, disk, network usage
- **Custom Metrics**: Queue depths, processing times

### 9.3 Alerting Strategy
```yaml
alerts:
  - name: high_error_rate
    condition: error_rate > 5%
    duration: 5m
    severity: critical
    
  - name: queue_backlog
    condition: queue_depth > 100
    duration: 10m
    severity: warning
    
  - name: service_down
    condition: health_check_failed
    duration: 1m
    severity: critical
```

## 10. Deployment Design

### 10.1 Infrastructure as Code
```yaml
# render.yaml configuration
services:
  - type: web
    name: mdraft-web
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --bind 0.0.0.0:$PORT wsgi:app
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: GOOGLE_APPLICATION_CREDENTIALS
        value: /etc/secrets/gcp.json
```

### 10.2 Environment Management
- **Environment Separation**: Development, staging, production
- **Configuration Management**: Environment-specific configs
- **Secret Management**: Secure credential storage
- **Feature Flags**: Runtime feature toggles

### 10.3 CI/CD Pipeline
```yaml
# GitHub Actions workflow
name: Deploy to Production
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: pytest
      - name: Deploy to Render
        run: |
          curl -X POST $RENDER_DEPLOY_HOOK
```

## 11. Testing Strategy

### 11.1 Test Pyramid
```
        E2E Tests (10%)
       ┌─────────────┐
       │             │
      ┌┴─────────────┴┐
      │ Integration   │
      │ Tests (20%)   │
     ┌┴────────────────┴┐
     │ Unit Tests (70%)  │
     └───────────────────┘
```

### 11.2 Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **API Tests**: Endpoint functionality testing
- **Performance Tests**: Load and stress testing
- **Security Tests**: Vulnerability assessment

### 11.3 Test Implementation
```python
# Example test structure
class TestConversionAPI:
    def test_upload_valid_document(self):
        """Test successful document upload and conversion"""
        pass
    
    def test_upload_invalid_file_type(self):
        """Test rejection of unsupported file types"""
        pass
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        pass
```

## 12. Risk Assessment

### 12.1 Technical Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Database connection failures | Medium | High | Connection pooling, retry logic |
| File processing timeouts | High | Medium | Async processing, timeouts |
| Storage quota exceeded | Low | High | Monitoring, cleanup jobs |
| API rate limit exceeded | Medium | Medium | Rate limiting, caching |

### 12.2 Security Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| File upload vulnerabilities | Medium | High | Input validation, sandboxing |
| API key compromise | Low | High | Key rotation, monitoring |
| Data exposure | Low | High | Encryption, access controls |
| DDoS attacks | Medium | Medium | Rate limiting, CDN |

## 13. Future Considerations

### 13.1 Scalability Improvements
- **Microservices Migration**: Service decomposition
- **Event Sourcing**: Event-driven architecture
- **CQRS Pattern**: Command Query Responsibility Segregation
- **GraphQL API**: Flexible data querying

### 13.2 Technology Evolution
- **Container Orchestration**: Kubernetes deployment
- **Serverless Functions**: Event-driven processing
- **Machine Learning**: Intelligent document processing
- **Blockchain**: Immutable audit trails

### 13.3 Business Expansion
- **Multi-tenancy**: SaaS platform features
- **White-label Solutions**: Custom branding options
- **API Marketplace**: Third-party integrations
- **Enterprise Features**: Advanced security and compliance

---

*Document Version: 1.0*  
*Last Updated: December 2024*  
*Maintained By: Architecture Team*
