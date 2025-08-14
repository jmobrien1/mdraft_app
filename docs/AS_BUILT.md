# mdraft - As-Built Documentation

## Executive Summary

mdraft is a Flask-based SaaS application that converts documents (PDF, DOCX) to Markdown format using Google Cloud services. The application is designed as a production-ready service with background processing, rate limiting, and comprehensive error handling.

## System Architecture

### High-Level Architecture
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

### Deployment Architecture
- **Platform**: Render.com
- **Services**: 
  - Web service (Flask app)
  - Worker service (Celery)
  - Cron service (cleanup tasks)
- **Database**: PostgreSQL (Cloud SQL)
- **Storage**: Google Cloud Storage
- **Queue**: Google Cloud Tasks

## Technology Stack

### Backend Framework
- **Python**: 3.11.11
- **Flask**: 3.0.3
- **WSGI Server**: Gunicorn (2 workers, 8 threads)
- **Database ORM**: SQLAlchemy 3.1.1
- **Migrations**: Alembic 1.13.1
- **Database Driver**: psycopg[binary] 3.2.9

### Google Cloud Services
- **Cloud Storage**: 2.18.2 (file storage with V4 signed URLs)
- **Cloud Tasks**: 2.16.0 (background job processing)
- **Document AI**: 2.27.0 (OCR and text extraction)
- **Secret Manager**: 2.19.0 (credential management)

### Security & Authentication
- **Password Hashing**: Flask-Bcrypt 1.0.1
- **Session Management**: Flask-Login 0.6.3
- **Rate Limiting**: Flask-Limiter 3.6.0
- **CORS**: flask-cors 4.0.1

### File Processing
- **Document Conversion**: markitdown[all] 0.1.2
- **PDF Processing**: pdfminer.six 20231228, pypdf 4.2
- **MIME Detection**: filetype 1.2.0
- **Report Generation**: reportlab 4.0.4

### Background Processing
- **Task Queue**: Celery 5.4.0
- **Message Broker**: Redis 5.0.7
- **Alternative**: Google Cloud Tasks (async mode)

### Monitoring & Observability
- **Error Tracking**: Sentry SDK 2.9.0
- **HTTP Client**: requests 2.32.3

## Database Schema

### Core Tables

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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
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

#### Conversions Table
```sql
CREATE TABLE conversions (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    markdown TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    sha256 VARCHAR(64),
    original_mime VARCHAR(120),
    original_size INTEGER,
    stored_uri VARCHAR(512),
    expires_at TIMESTAMP
);
```

#### Allowlist Table
```sql
CREATE TABLE allowlist (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(64) DEFAULT 'invited',
    plan VARCHAR(64) DEFAULT 'F&F',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Core Conversion API
- `POST /api/convert` - Upload and convert document
- `GET /api/conversions/{id}` - Get conversion status
- `GET /api/conversions/{id}/markdown` - Download markdown result
- `GET /v/{id}` - View conversion result

### Queue Management API
- `POST /api/queue/estimate` - Estimate conversion time
- `GET /api/queue/status` - Get queue status

### Usage & Billing API
- `GET /api/usage` - Get usage statistics
- `POST /api/billing/webhook` - Stripe webhook handler

### Health & Admin
- `GET /health` - Health check endpoint
- `GET /admin/` - Admin dashboard
- `GET /admin/keys` - API key management

## File Processing Pipeline

### Upload Flow
1. **File Validation**: MIME type detection, size limits, security checks
2. **Storage**: Local temp file or direct GCS upload
3. **Deduplication**: SHA256 hash checking against existing conversions
4. **Job Creation**: Database record with pending status
5. **Queue Processing**: Background task creation (sync/async modes)

### Conversion Flow
1. **Engine Selection**: markitdown for standard docs, Document AI for scanned
2. **Processing**: CLI tool execution or cloud API calls
3. **Post-processing**: Markdown cleaning, quality checks
4. **Storage**: Result storage in GCS with signed URLs
5. **Status Update**: Database record update with completion status

### Security Measures
- **File Type Validation**: Whitelist-based MIME type checking
- **Size Limits**: Category-based file size restrictions
- **Rate Limiting**: Per-user and global rate limits
- **Signed URLs**: V4 signed URLs for secure file access
- **Input Sanitization**: Filename sanitization and content validation

## Configuration Management

### Environment Variables
```bash
# Core Application
FLASK_ENV=production
SECRET_KEY=<generated>
DATABASE_URL=postgresql+psycopg://...

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp.json
GCS_BUCKET_NAME=mdraft-uploads
GCS_PROCESSED_BUCKET_NAME=mdraft-processed

# Processing Configuration
QUEUE_MODE=sync  # or async
USE_GCS=0  # or 1
DOCAI_PROCESSOR_ID=projects/...
DOCAI_LOCATION=us

# Rate Limiting
GLOBAL_RATE_LIMIT=120 per minute
CONVERT_RATE_LIMIT_DEFAULT=20 per minute

# Monitoring
SENTRY_DSN=<sentry-dsn>
SENTRY_ENVIRONMENT=production
```

### Deployment Configuration
- **Render Services**: 3 services (web, worker, cron)
- **Health Checks**: `/health` endpoint monitoring
- **Auto-scaling**: Based on queue depth and response times
- **SSL/TLS**: Automatic HTTPS termination

## Error Handling & Monitoring

### Error Categories
1. **File Processing Errors**: Unsupported formats, corrupted files
2. **Conversion Errors**: Tool failures, timeouts, API errors
3. **Storage Errors**: GCS upload/download failures
4. **Database Errors**: Connection issues, constraint violations
5. **Authentication Errors**: Invalid API keys, rate limit exceeded

### Logging Strategy
- **Structured Logging**: JSON format with correlation IDs
- **Request Tracing**: Request ID propagation across services
- **Error Context**: Stack traces with relevant metadata
- **Performance Metrics**: Response times, queue depths

### Monitoring Integration
- **Sentry**: Error tracking and performance monitoring
- **Health Checks**: Automated service health monitoring
- **Custom Metrics**: Conversion success rates, processing times

## Performance Characteristics

### Scalability
- **Horizontal Scaling**: Stateless web services
- **Queue-based Processing**: Asynchronous job handling
- **Database Connection Pooling**: SQLAlchemy connection management
- **CDN Integration**: GCS with global edge caching

### Performance Metrics
- **Upload Processing**: < 5 seconds for file validation
- **Conversion Time**: 30-120 seconds depending on file size/complexity
- **API Response Time**: < 200ms for status checks
- **Concurrent Users**: 100+ simultaneous conversions

### Resource Requirements
- **Memory**: 512MB-1GB per service instance
- **CPU**: 1-2 vCPUs per service instance
- **Storage**: Ephemeral (GCS for persistent storage)
- **Network**: High bandwidth for file uploads/downloads

## Security Posture

### Data Protection
- **Encryption at Rest**: GCS bucket encryption
- **Encryption in Transit**: TLS 1.3 for all communications
- **Access Control**: IAM-based GCS permissions
- **API Security**: Rate limiting, input validation

### Authentication & Authorization
- **API Key Management**: Secure key storage and rotation
- **User Sessions**: Secure session management
- **Admin Access**: Role-based access control
- **Audit Logging**: Comprehensive access logging

### Compliance Considerations
- **Data Retention**: Configurable file retention policies
- **Privacy**: No PII storage in logs
- **GDPR**: Data deletion capabilities
- **SOC 2**: Security controls implementation

## Known Limitations

### Current Constraints
1. **File Size Limits**: 25MB maximum upload size
2. **Supported Formats**: PDF, DOCX, TXT primarily
3. **Processing Time**: Up to 2 minutes for large documents
4. **Concurrent Processing**: Limited by worker pool size

### Technical Debt
1. **Legacy Code**: Some unused models and endpoints
2. **Error Handling**: Inconsistent error response formats
3. **Testing**: Limited automated test coverage
4. **Documentation**: API documentation needs improvement

## Future Enhancements

### Planned Improvements
1. **Additional Formats**: Support for more document types
2. **Batch Processing**: Multiple file upload and processing
3. **Advanced OCR**: Improved scanned document handling
4. **Real-time Updates**: WebSocket-based status updates
5. **Analytics Dashboard**: Usage analytics and insights

### Scalability Improvements
1. **Microservices**: Service decomposition
2. **Event-driven Architecture**: Event sourcing implementation
3. **Caching Layer**: Redis-based result caching
4. **Load Balancing**: Multi-region deployment

## Maintenance Procedures

### Regular Maintenance
- **Database Backups**: Daily automated backups
- **Log Rotation**: Automated log cleanup
- **Security Updates**: Regular dependency updates
- **Performance Monitoring**: Continuous performance tracking

### Emergency Procedures
- **Service Recovery**: Automated failover procedures
- **Data Recovery**: Backup restoration procedures
- **Incident Response**: Escalation and communication protocols
- **Rollback Procedures**: Version rollback capabilities

---

*Document Version: 1.0*  
*Last Updated: December 2024*  
*Maintained By: Development Team*
