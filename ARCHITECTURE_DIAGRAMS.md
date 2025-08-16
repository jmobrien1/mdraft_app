# MDraft Architecture Diagrams
## Visual System Design Documentation

**Version:** 1.0  
**Date:** December 2024  
**Author:** Technical Architecture Team  

---

## Table of Contents

1. [System Overview Diagram](#system-overview-diagram)
2. [Application Architecture](#application-architecture)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Deployment Architecture](#deployment-architecture)
5. [Security Architecture](#security-architecture)
6. [Processing Pipelines](#processing-pipelines)
7. [Database Schema](#database-schema)
8. [API Architecture](#api-architecture)

---

## System Overview Diagram

### High-Level System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Web UI]
        API_CLIENT[API Client]
        MOBILE[Mobile App]
    end
    
    subgraph "Application Layer"
        WEB[Flask Web App]
        WORKER[Celery Worker]
        ADMIN[Admin Interface]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL)]
        REDIS[(Redis)]
        GCS[Google Cloud Storage]
    end
    
    subgraph "External Services"
        DOCAI[Document AI]
        VERTEX[Vertex AI]
        TASKS[Cloud Tasks]
        SENTRY[Sentry]
    end
    
    UI --> WEB
    API_CLIENT --> WEB
    MOBILE --> WEB
    WEB --> WORKER
    WEB --> DB
    WEB --> REDIS
    WORKER --> DB
    WORKER --> REDIS
    WORKER --> GCS
    WORKER --> DOCAI
    WORKER --> VERTEX
    WORKER --> TASKS
    WEB --> SENTRY
    WORKER --> SENTRY
```

### Component Interaction Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web App
    participant Q as Queue
    participant C as Celery Worker
    participant G as Google Cloud
    participant D as Database
    
    U->>W: Upload Document
    W->>G: Store in GCS
    W->>D: Create Job Record
    W->>Q: Queue Conversion Task
    Q->>C: Process Task
    C->>G: Download File
    C->>G: Extract Text (Document AI)
    C->>G: Convert to Markdown
    C->>G: Store Result
    C->>D: Update Job Status
    W->>U: Return Job ID
    U->>W: Check Status
    W->>D: Get Job Status
    W->>U: Return Status
```

---

## Application Architecture

### Flask Application Structure

```mermaid
graph TD
    subgraph "Flask Application Factory"
        APP[create_app()]
        CONFIG[Configuration]
        EXTENSIONS[Extensions]
        BLUEPRINTS[Blueprints]
    end
    
    subgraph "Extensions"
        DB[SQLAlchemy]
        MIGRATE[Flask-Migrate]
        LOGIN[Flask-Login]
        LIMITER[Flask-Limiter]
        SESSION[Flask-Session]
        CSRF[CSRF Protection]
    end
    
    subgraph "Blueprints"
        MAIN[Main Routes]
        API[API Routes]
        AUTH[Authentication]
        ADMIN[Admin Interface]
        HEALTH[Health Checks]
        WORKER[Worker Routes]
    end
    
    subgraph "Services"
        AI[AI Tools Service]
        STORAGE[Storage Service]
        TEXT[Text Loader Service]
        LLM[LLM Client Service]
    end
    
    APP --> CONFIG
    APP --> EXTENSIONS
    APP --> BLUEPRINTS
    BLUEPRINTS --> SERVICES
```

### Service Layer Architecture

```mermaid
graph LR
    subgraph "API Layer"
        ROUTES[Route Handlers]
        VALIDATION[Input Validation]
        AUTH[Authentication]
    end
    
    subgraph "Service Layer"
        AI_SERVICE[AI Tools Service]
        STORAGE_SERVICE[Storage Service]
        TEXT_SERVICE[Text Loader Service]
        LLM_SERVICE[LLM Client Service]
    end
    
    subgraph "Data Layer"
        MODELS[SQLAlchemy Models]
        REPOSITORY[Repository Pattern]
        MIGRATIONS[Alembic Migrations]
    end
    
    subgraph "External Services"
        GCS[Google Cloud Storage]
        DOCAI[Document AI]
        VERTEX[Vertex AI]
        REDIS[Redis]
    end
    
    ROUTES --> AI_SERVICE
    ROUTES --> STORAGE_SERVICE
    ROUTES --> TEXT_SERVICE
    ROUTES --> LLM_SERVICE
    
    AI_SERVICE --> MODELS
    STORAGE_SERVICE --> GCS
    TEXT_SERVICE --> DOCAI
    LLM_SERVICE --> VERTEX
    
    MODELS --> REPOSITORY
    REPOSITORY --> MIGRATIONS
```

---

## Data Flow Diagrams

### Document Upload Flow

```mermaid
flowchart TD
    A[User Uploads File] --> B{File Validation}
    B -->|Valid| C[Generate Unique Filename]
    B -->|Invalid| D[Return Error]
    
    C --> E[Upload to GCS]
    E --> F{Upload Success?}
    F -->|Yes| G[Create Job Record]
    F -->|No| H[Return Error]
    
    G --> I[Queue Conversion Task]
    I --> J[Return Job ID]
    
    J --> K[User Polls Status]
    K --> L[Check Job Status]
    L --> M{Job Complete?}
    M -->|No| K
    M -->|Yes| N[Return Download URL]
```

### RFP Analysis Flow

```mermaid
flowchart TD
    A[User Uploads RFP] --> B[Extract Text]
    B --> C[Chunk Content]
    C --> D[Process with AI]
    D --> E[Merge Results]
    E --> F[Deduplicate]
    F --> G[Validate Schema]
    G --> H[Store Results]
    H --> I[Return Analysis]
    
    subgraph "AI Processing"
        D1[Compliance Matrix]
        D2[Evaluation Criteria]
        D3[Annotated Outline]
        D4[Submission Checklist]
    end
    
    D --> D1
    D --> D2
    D --> D3
    D --> D4
```

### Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web App
    participant D as Database
    participant R as Redis
    
    U->>W: Login Request
    W->>D: Validate Credentials
    D->>W: User Data
    W->>R: Create Session
    W->>U: Session Cookie
    
    U->>W: API Request
    W->>R: Validate Session
    R->>W: Session Data
    W->>U: Response
    
    U->>W: Logout Request
    W->>R: Destroy Session
    W->>U: Clear Cookie
```

---

## Deployment Architecture

### Render Deployment Structure

```mermaid
graph TB
    subgraph "Render Platform"
        WEB_SERVICE[Web Service]
        WORKER_SERVICE[Worker Service]
        CRON_SERVICE[Cron Service]
    end
    
    subgraph "External Services"
        POSTGRES[PostgreSQL Database]
        REDIS_INSTANCE[Redis Instance]
        GCS_BUCKETS[GCS Buckets]
    end
    
    subgraph "Google Cloud"
        DOCAI_SERVICE[Document AI]
        VERTEX_SERVICE[Vertex AI]
        TASKS_SERVICE[Cloud Tasks]
    end
    
    WEB_SERVICE --> POSTGRES
    WEB_SERVICE --> REDIS_INSTANCE
    WORKER_SERVICE --> POSTGRES
    WORKER_SERVICE --> REDIS_INSTANCE
    WORKER_SERVICE --> GCS_BUCKETS
    WORKER_SERVICE --> DOCAI_SERVICE
    WORKER_SERVICE --> VERTEX_SERVICE
    WORKER_SERVICE --> TASKS_SERVICE
    CRON_SERVICE --> POSTGRES
    CRON_SERVICE --> GCS_BUCKETS
```

### Environment Configuration

```mermaid
graph LR
    subgraph "Environment Variables"
        DB_URL[DATABASE_URL]
        GCS_BUCKET[GCS_BUCKET_NAME]
        SECRET_KEY[SECRET_KEY]
        SENTRY_DSN[SENTRY_DSN]
        REDIS_URL[REDIS_URL]
    end
    
    subgraph "Application Config"
        CONFIG[AppConfig]
        VALIDATION[Config Validation]
        SECRETS[Secret Management]
    end
    
    subgraph "Flask App"
        APP[Flask Application]
        EXTENSIONS[Extensions]
        BLUEPRINTS[Blueprints]
    end
    
    DB_URL --> CONFIG
    GCS_BUCKET --> CONFIG
    SECRET_KEY --> CONFIG
    SENTRY_DSN --> CONFIG
    REDIS_URL --> CONFIG
    
    CONFIG --> VALIDATION
    CONFIG --> SECRETS
    CONFIG --> APP
    APP --> EXTENSIONS
    APP --> BLUEPRINTS
```

---

## Security Architecture

### Authentication & Authorization Flow

```mermaid
graph TD
    A[Request] --> B{Has Session?}
    B -->|No| C[Redirect to Login]
    B -->|Yes| D{Valid Session?}
    
    D -->|No| C
    D -->|Yes| E{API Route?}
    
    E -->|No| F[CSRF Check]
    E -->|Yes| G{Has API Key?}
    
    F -->|Pass| H[Route Handler]
    F -->|Fail| I[CSRF Error]
    
    G -->|Yes| H
    G -->|No| J[401 Unauthorized]
    
    H --> K{Requires Subscription?}
    K -->|Yes| L{Has Subscription?}
    K -->|No| M[Process Request]
    
    L -->|Yes| M
    L -->|No| N[403 Forbidden]
```

### Security Headers Implementation

```mermaid
graph LR
    subgraph "Request Processing"
        REQUEST[Incoming Request]
        VALIDATION[Input Validation]
        RATE_LIMIT[Rate Limiting]
    end
    
    subgraph "Response Processing"
        RESPONSE[Response Generation]
        SECURITY_HEADERS[Security Headers]
        CSP[CSP Policy]
    end
    
    subgraph "Security Headers"
        HSTS[Strict-Transport-Security]
        XFO[X-Frame-Options]
        XCTO[X-Content-Type-Options]
        RP[Referrer-Policy]
        PP[Permissions-Policy]
    end
    
    REQUEST --> VALIDATION
    VALIDATION --> RATE_LIMIT
    RATE_LIMIT --> RESPONSE
    RESPONSE --> SECURITY_HEADERS
    SECURITY_HEADERS --> CSP
    SECURITY_HEADERS --> HSTS
    SECURITY_HEADERS --> XFO
    SECURITY_HEADERS --> XCTO
    SECURITY_HEADERS --> RP
    SECURITY_HEADERS --> PP
```

---

## Processing Pipelines

### Document Conversion Pipeline

```mermaid
graph TD
    subgraph "Upload Phase"
        A[File Upload] --> B[File Validation]
        B --> C[Generate SHA256]
        C --> D[Check Duplicates]
        D --> E[Upload to GCS]
    end
    
    subgraph "Processing Phase"
        E --> F[Create Job Record]
        F --> G[Queue Task]
        G --> H[Celery Worker]
        H --> I[Download from GCS]
        I --> J[Extract Text]
        J --> K[Convert to Markdown]
        K --> L[Store Result]
    end
    
    subgraph "Completion Phase"
        L --> M[Update Job Status]
        M --> N[Generate Download URL]
        N --> O[Notify User]
    end
```

### AI Processing Pipeline

```mermaid
graph TD
    subgraph "Input Processing"
        A[Document Content] --> B[Text Extraction]
        B --> C[Content Cleaning]
        C --> D[Chunking]
    end
    
    subgraph "AI Processing"
        D --> E[Sliding Window]
        E --> F[LLM Processing]
        F --> G[Result Extraction]
        G --> H[Schema Validation]
    end
    
    subgraph "Output Processing"
        H --> I[Result Merging]
        I --> J[Deduplication]
        J --> K[Final Validation]
        K --> L[Structured Output]
    end
```

### Error Handling Pipeline

```mermaid
graph TD
    A[Error Occurs] --> B{Error Type?}
    
    B -->|Validation| C[Return 400 Bad Request]
    B -->|Authentication| D[Return 401 Unauthorized]
    B -->|Authorization| E[Return 403 Forbidden]
    B -->|Not Found| F[Return 404 Not Found]
    B -->|Rate Limit| G[Return 429 Too Many Requests]
    B -->|Server Error| H[Log Error]
    
    H --> I[Send to Sentry]
    I --> J[Return 500 Internal Server Error]
    
    C --> K[Error Response]
    D --> K
    E --> K
    F --> K
    G --> K
    J --> K
```

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    USERS {
        int id PK
        string email UK
        string password_hash
        string stripe_customer_id
        string subscription_status
        string plan
        datetime last_login_at
        boolean revoked
        boolean email_verified
        datetime created_at
        datetime updated_at
    }
    
    PROPOSALS {
        int id PK
        int user_id FK
        string visitor_session_id
        string title
        string status
        datetime expires_at
        datetime created_at
        datetime updated_at
    }
    
    CONVERSIONS {
        string id PK
        string filename
        string status
        int progress
        text markdown
        text error
        int proposal_id FK
        int user_id FK
        string visitor_session_id
        string sha256
        string original_mime
        int original_size
        string stored_uri
        datetime expires_at
        datetime created_at
        datetime updated_at
    }
    
    JOBS {
        int id PK
        int user_id FK
        string filename
        string status
        text gcs_uri
        text output_uri
        text error_message
        datetime started_at
        datetime completed_at
        datetime created_at
        datetime updated_at
    }
    
    USERS ||--o{ PROPOSALS : "has"
    USERS ||--o{ CONVERSIONS : "has"
    USERS ||--o{ JOBS : "has"
    PROPOSALS ||--o{ CONVERSIONS : "contains"
```

### Database Indexes

```mermaid
graph TD
    subgraph "User Indexes"
        UI1[users.email]
        UI2[users.subscription_status]
        UI3[users.created_at]
    end
    
    subgraph "Proposal Indexes"
        PI1[proposals.user_id]
        PI2[proposals.visitor_session_id]
        PI3[proposals.status]
    end
    
    subgraph "Conversion Indexes"
        CI1[conversions.proposal_id]
        CI2[conversions.user_id]
        CI3[conversions.visitor_session_id]
        CI4[conversions.sha256]
        CI5[conversions.status]
        CI6[conversions.created_at]
    end
    
    subgraph "Job Indexes"
        JI1[jobs.user_id]
        JI2[jobs.status]
        JI3[jobs.created_at]
    end
```

---

## API Architecture

### RESTful API Structure

```mermaid
graph TD
    subgraph "Authentication"
        AUTH_LOGIN[POST /auth/login]
        AUTH_LOGOUT[POST /auth/logout]
        AUTH_REGISTER[POST /auth/register]
    end
    
    subgraph "File Management"
        UPLOAD[POST /api/upload]
        DOWNLOAD[GET /api/download/{filename}]
        STATUS[GET /api/jobs/{job_id}]
    end
    
    subgraph "RFP Analysis"
        COMPLIANCE[POST /api/rfp/compliance-matrix]
        EVALUATION[POST /api/rfp/evaluation-criteria]
        OUTLINE[POST /api/rfp/annotated-outline]
        CHECKLIST[POST /api/rfp/submission-checklist]
    end
    
    subgraph "Proposal Management"
        PROPOSALS[GET /api/proposals]
        PROPOSAL_CREATE[POST /api/proposals]
        PROPOSAL_GET[GET /api/proposals/{id}]
        PROPOSAL_UPDATE[PUT /api/proposals/{id}]
    end
    
    subgraph "Health & Monitoring"
        HEALTH[GET /health]
        MIGRATION_STATUS[GET /api/ops/migration_status]
        METRICS[GET /api/ops/metrics]
    end
```

### API Response Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API Gateway
    participant V as Validation
    participant H as Handler
    participant S as Service
    participant D as Database
    
    C->>A: API Request
    A->>V: Validate Input
    V->>A: Validation Result
    
    alt Valid Request
        A->>H: Route to Handler
        H->>S: Call Service
        S->>D: Database Operation
        D->>S: Return Data
        S->>H: Service Response
        H->>A: Handler Response
        A->>C: Success Response
    else Invalid Request
        A->>C: Error Response
    end
```

### Rate Limiting Architecture

```mermaid
graph TD
    A[Request] --> B{Rate Limit Check}
    B -->|Under Limit| C[Process Request]
    B -->|Over Limit| D[Return 429]
    
    C --> E[Update Rate Limit Counter]
    E --> F[Response]
    
    subgraph "Rate Limit Storage"
        RL1[Redis Storage]
        RL2[In-Memory Cache]
    end
    
    B --> RL1
    B --> RL2
    E --> RL1
    E --> RL2
```

---

## Monitoring & Observability

### Logging Architecture

```mermaid
graph TD
    subgraph "Application Logs"
        APP_LOG[Application Logs]
        REQUEST_LOG[Request Logs]
        ERROR_LOG[Error Logs]
    end
    
    subgraph "Structured Logging"
        JSON_FORMAT[JSON Formatter]
        CORRELATION_ID[Correlation IDs]
        REQUEST_ID[Request IDs]
    end
    
    subgraph "External Services"
        SENTRY[Sentry]
        LOG_AGGREGATOR[Log Aggregator]
    end
    
    APP_LOG --> JSON_FORMAT
    REQUEST_LOG --> JSON_FORMAT
    ERROR_LOG --> JSON_FORMAT
    
    JSON_FORMAT --> CORRELATION_ID
    JSON_FORMAT --> REQUEST_ID
    
    JSON_FORMAT --> SENTRY
    JSON_FORMAT --> LOG_AGGREGATOR
```

### Health Check Architecture

```mermaid
graph TD
    A[Health Check Request] --> B{Database Check}
    B -->|Healthy| C{Redis Check}
    B -->|Unhealthy| D[Return 503]
    
    C -->|Healthy| E{External Services}
    C -->|Unhealthy| F[Return 503]
    
    E -->|Healthy| G[Return 200 OK]
    E -->|Unhealthy| H[Return 503]
    
    subgraph "Health Checks"
        DB_CHECK[Database Connectivity]
        REDIS_CHECK[Redis Connectivity]
        GCS_CHECK[GCS Connectivity]
        DOCAI_CHECK[Document AI Health]
    end
    
    B --> DB_CHECK
    C --> REDIS_CHECK
    E --> GCS_CHECK
    E --> DOCAI_CHECK
```

---

## Performance Optimization

### Caching Strategy

```mermaid
graph TD
    A[Request] --> B{Cache Hit?}
    B -->|Yes| C[Return Cached Data]
    B -->|No| D[Process Request]
    
    D --> E[Store in Cache]
    E --> F[Return Response]
    
    subgraph "Cache Layers"
        L1[L1 Cache - Memory]
        L2[L2 Cache - Redis]
        L3[L3 Cache - Database]
    end
    
    B --> L1
    B --> L2
    B --> L3
    
    E --> L1
    E --> L2
```

### Connection Pooling

```mermaid
graph TD
    A[Database Request] --> B{Available Connection?}
    B -->|Yes| C[Use Connection]
    B -->|No| D{Max Pool Size?}
    
    D -->|No| E[Create New Connection]
    D -->|Yes| F[Wait for Connection]
    
    C --> G[Execute Query]
    E --> G
    F --> G
    
    G --> H[Return Connection to Pool]
    
    subgraph "Connection Pool"
        POOL[Connection Pool]
        ACTIVE[Active Connections]
        IDLE[Idle Connections]
    end
    
    B --> POOL
    E --> POOL
    H --> POOL
```

---

**Document Control**
- **Version**: 1.0
- **Last Updated**: December 2024
- **Next Review**: March 2025
- **Approved By**: Technical Architecture Team
