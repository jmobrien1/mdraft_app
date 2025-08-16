# MDraft Implementation Guide
## Developer's Guide to Building and Extending the System

**Version:** 1.0  
**Date:** December 2024  
**Author:** Technical Architecture Team  

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment Setup](#development-environment-setup)
3. [Code Organization](#code-organization)
4. [Adding New Features](#adding-new-features)
5. [Database Operations](#database-operations)
6. [Testing Guidelines](#testing-guidelines)
7. [Deployment Procedures](#deployment-procedures)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [API Development](#api-development)

---

## Getting Started

### Prerequisites

Before you begin development, ensure you have the following installed:

- **Python 3.11+**: The application requires Python 3.11 or higher
- **pip**: Python package installer
- **Git**: Version control system
- **PostgreSQL**: Database (local or cloud)
- **Redis**: For session management and rate limiting
- **Google Cloud SDK**: For cloud service integration

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mdraft_app
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development tools
   ```

4. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   python run.py
   ```

---

## Development Environment Setup

### Environment Configuration

Create a `.env` file with the following configuration:

```bash
# Flask Configuration
FLASK_APP=run.py
FLASK_DEBUG=1
SECRET_KEY=your-development-secret-key

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost/mdraft_dev

# Google Cloud Configuration (for production features)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
GCS_BUCKET_NAME=mdraft-uploads-dev
GCS_PROCESSED_BUCKET_NAME=mdraft-processed-dev

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Development Settings
MDRAFT_DEV_STUB=1
USE_GCS=0  # Use local storage for development
```

### Local Services Setup

#### PostgreSQL Setup
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb mdraft_dev

# Create user
sudo -u postgres createuser --interactive mdraft_user
```

#### Redis Setup
```bash
# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server
```

#### Google Cloud Setup (Optional)
```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login
gcloud config set project your-project-id

# Create service account
gcloud iam service-accounts create mdraft-dev \
  --display-name="MDraft Development Service Account"

# Download key
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=mdraft-dev@your-project-id.iam.gserviceaccount.com
```

### IDE Configuration

#### VS Code Setup
Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ]
}
```

#### PyCharm Setup
1. Open project in PyCharm
2. Configure Python interpreter to use `.venv/bin/python`
3. Set up run configurations for Flask app and tests

---

## Code Organization

### Project Structure

```
mdraft_app/
├── app/                          # Main application package
│   ├── __init__.py              # Application factory
│   ├── models.py                # Core data models
│   ├── models_conversion.py     # Conversion-specific models
│   ├── models_apikey.py         # API key models
│   ├── routes.py                # Main web routes
│   ├── api/                     # API blueprints
│   │   ├── ops.py              # Operations/monitoring
│   │   ├── agents.py           # AI agent endpoints
│   │   └── errors.py           # Error handling
│   ├── services/                # Business logic layer
│   │   ├── ai_tools.py         # AI processing
│   │   ├── storage.py          # File storage
│   │   ├── text_loader.py      # Document loading
│   │   └── llm_client.py       # LLM integration
│   ├── auth/                    # Authentication
│   ├── admin/                   # Admin interface
│   ├── static/                  # Static assets
│   ├── templates/               # HTML templates
│   └── utils/                   # Utility functions
├── migrations/                   # Database migrations
├── tests/                       # Test suite
├── scripts/                     # Utility scripts
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
├── run.py                       # Application entry point
└── wsgi.py                      # WSGI entry point
```

### Key Design Patterns

#### Application Factory Pattern
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

#### Service Layer Pattern
```python
# app/services/ai_tools.py
class AIToolsService:
    def __init__(self):
        self.chunk_size = int(os.getenv("MDRAFT_CHUNK_SIZE_CHARS") or 3000)
        self.max_chunks = int(os.getenv("MDRAFT_MAX_CHUNKS") or 12)
    
    def run_prompt(self, prompt_type: str, content: str) -> Dict[str, Any]:
        """Execute AI prompt on document content."""
        chunks = self._chunk_content(content)
        results = self._process_chunks_with_window(chunks, prompt_type)
        merged = self._merge_results(results)
        return self._validate_results(merged, prompt_type)
```

#### Repository Pattern
```python
# app/models.py
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
```

---

## Adding New Features

### Adding a New API Endpoint

1. **Create the route handler**
   ```python
   # app/api/new_feature.py
   from flask import Blueprint, request, jsonify
   from app.utils.auth import require_auth
   from app.services.new_service import NewService
   
   bp = Blueprint("new_feature", __name__)
   
   @bp.route("/api/new-feature", methods=["POST"])
   @require_auth
   def new_feature():
       try:
           data = request.get_json()
           
           # Validate input
           if not data or 'required_field' not in data:
               return jsonify({"error": "missing_required_field"}), 400
           
           # Process request
           service = NewService()
           result = service.process(data)
           
           return jsonify({
               "status": "success",
               "data": result
           }), 200
           
       except Exception as e:
           return jsonify({
               "status": "error",
               "message": str(e)
           }), 500
   ```

2. **Register the blueprint**
   ```python
   # app/__init__.py
   from .api.new_feature import bp as new_feature_bp
   app.register_blueprint(new_feature_bp)
   ```

3. **Add tests**
   ```python
   # tests/test_new_feature.py
   def test_new_feature_endpoint():
       with app.test_client() as client:
           response = client.post('/api/new-feature', 
                                json={'required_field': 'test_value'})
           assert response.status_code == 200
           data = response.get_json()
           assert data['status'] == 'success'
   ```

### Adding a New Database Model

1. **Create the model**
   ```python
   # app/models.py
   class NewModel(db.Model):
       __tablename__ = "new_models"
       
       id = db.Column(db.Integer, primary_key=True)
       name = db.Column(db.String(255), nullable=False)
       description = db.Column(db.Text)
       user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
       created_at = db.Column(db.DateTime, default=datetime.utcnow)
       updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       
       # Relationships
       user = db.relationship("User", back_populates="new_models")
       
       def __repr__(self):
           return f"<NewModel {self.id} ({self.name})>"
   ```

2. **Create migration**
   ```bash
   flask db migrate -m "Add new_model table"
   flask db upgrade
   ```

3. **Update related models**
   ```python
   # app/models.py
   class User(UserMixin, db.Model):
       # ... existing fields ...
       
       # Add relationship
       new_models: Mapped[list[NewModel]] = relationship("NewModel", back_populates="user")
   ```

### Adding a New Service

1. **Create the service class**
   ```python
   # app/services/new_service.py
   import logging
   from typing import Dict, Any
   
   logger = logging.getLogger(__name__)
   
   class NewService:
       def __init__(self):
           self.config = get_config()
       
       def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
           """Process the input data."""
           logger.info(f"Processing data: {data}")
           
           # Business logic here
           result = self._transform_data(data)
           
           logger.info(f"Processing complete: {result}")
           return result
       
       def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
           """Transform the input data."""
           # Implementation details
           return {"transformed": data}
   ```

2. **Add configuration**
   ```python
   # app/config.py
   @dataclass
   class NewServiceConfig:
       ENABLED: bool = True
       TIMEOUT_SEC: int = 30
       
   class AppConfig:
       def __init__(self):
           # ... existing config ...
           self.new_service = NewServiceConfig(
               ENABLED=os.getenv("NEW_SERVICE_ENABLED", "true").lower() == "true",
               TIMEOUT_SEC=int(os.getenv("NEW_SERVICE_TIMEOUT_SEC", "30"))
           )
   ```

---

## Database Operations

### Creating Migrations

```bash
# Create a new migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Rollback migration
flask db downgrade

# View migration history
flask db history
```

### Migration Best Practices

1. **Always test migrations**
   ```bash
   # Test migration on copy of production data
   pg_dump production_db > test_db.sql
   createdb test_db
   psql test_db < test_db.sql
   flask db upgrade
   ```

2. **Use reversible migrations**
   ```python
   # migrations/versions/xxx_add_new_column.py
   def upgrade():
       op.add_column('users', sa.Column('new_field', sa.String(255)))
   
   def downgrade():
       op.drop_column('users', 'new_field')
   ```

3. **Handle data migrations**
   ```python
   def upgrade():
       # Add column
       op.add_column('users', sa.Column('new_field', sa.String(255)))
       
       # Migrate existing data
       connection = op.get_bind()
       connection.execute(
           "UPDATE users SET new_field = 'default_value' WHERE new_field IS NULL"
       )
   ```

### Database Queries

#### Using SQLAlchemy ORM
```python
# Basic queries
users = User.query.all()
user = User.query.filter_by(email='test@example.com').first()
active_users = User.query.filter_by(revoked=False).all()

# Complex queries
from sqlalchemy import and_, or_
recent_jobs = Job.query.filter(
    and_(
        Job.status == 'completed',
        Job.created_at >= datetime.utcnow() - timedelta(days=7)
    )
).all()

# Joins
jobs_with_users = Job.query.join(User).filter(
    User.subscription_status == 'pro'
).all()

# Pagination
jobs = Job.query.paginate(
    page=1, per_page=20, error_out=False
)
```

#### Using Raw SQL
```python
from sqlalchemy import text

# Raw SQL query
result = db.session.execute(text("""
    SELECT u.email, COUNT(j.id) as job_count
    FROM users u
    LEFT JOIN jobs j ON u.id = j.user_id
    WHERE u.revoked = false
    GROUP BY u.id, u.email
    HAVING COUNT(j.id) > 0
    ORDER BY job_count DESC
"""))

for row in result:
    print(f"{row.email}: {row.job_count} jobs")
```

---

## Testing Guidelines

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Pytest configuration
├── test_models.py             # Model tests
├── test_api.py                # API endpoint tests
├── test_services.py           # Service layer tests
├── test_integration.py        # Integration tests
└── fixtures/                  # Test fixtures
    ├── sample_files/
    └── test_data.json
```

### Writing Tests

#### Unit Tests
```python
# tests/test_models.py
import pytest
from app.models import User, Job
from app import db

def test_user_creation():
    """Test user creation."""
    user = User(email='test@example.com')
    db.session.add(user)
    db.session.commit()
    
    assert user.id is not None
    assert user.email == 'test@example.com'
    assert user.subscription_status == 'free'

def test_job_status_transitions():
    """Test job status transitions."""
    job = Job(filename='test.pdf')
    
    # Test valid transitions
    job.status = 'processing'
    assert job.status == 'processing'
    
    job.status = 'completed'
    assert job.status == 'completed'
    
    # Test invalid transition
    with pytest.raises(ValueError):
        job.status = 'pending'  # Cannot go back to pending from completed
```

#### API Tests
```python
# tests/test_api.py
def test_upload_endpoint(client, auth_headers):
    """Test file upload endpoint."""
    with open('tests/fixtures/sample_files/test.pdf', 'rb') as f:
        response = client.post(
            '/api/upload',
            data={'file': f},
            headers=auth_headers
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'job_id' in data
    assert data['status'] == 'success'

def test_upload_invalid_file(client, auth_headers):
    """Test upload with invalid file."""
    response = client.post(
        '/api/upload',
        data={'file': 'invalid'},
        headers=auth_headers
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
```

#### Service Tests
```python
# tests/test_services.py
from app.services.ai_tools import AIToolsService

def test_ai_tools_chunking():
    """Test content chunking."""
    service = AIToolsService()
    content = "paragraph 1\n\nparagraph 2\n\nparagraph 3"
    chunks = service._chunk_content(content)
    
    assert len(chunks) > 0
    assert all(len(chunk) <= service.chunk_size for chunk in chunks)

def test_ai_tools_processing():
    """Test AI processing."""
    service = AIToolsService()
    content = "Test content for processing"
    
    # Mock the AI service for testing
    with patch('app.services.llm_client.chat_json') as mock_llm:
        mock_llm.return_value = {"result": "test"}
        result = service.run_prompt("compliance_matrix", content)
        
        assert result is not None
        mock_llm.assert_called_once()
```

### Test Configuration

#### Pytest Configuration
```python
# tests/conftest.py
import pytest
from app import create_app, db
from app.models import User, Job

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def auth_headers(app, client):
    """Create authenticated headers."""
    with app.app_context():
        # Create test user
        user = User(email='test@example.com')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        
        return {'Cookie': 'session=test-session'}

@pytest.fixture
def sample_file():
    """Provide sample file for testing."""
    return 'tests/fixtures/sample_files/test.pdf'
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/test_models.py tests/test_services.py

# Run integration tests
pytest tests/test_integration.py
```

---

## Deployment Procedures

### Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Code review completed
- [ ] Database migrations tested
- [ ] Environment variables configured
- [ ] Google Cloud services enabled
- [ ] Monitoring alerts configured

### Deployment Steps

1. **Code Review**
   ```bash
   # Ensure all changes are committed
   git status
   git add .
   git commit -m "Feature: Add new functionality"
   git push origin main
   ```

2. **Testing**
   ```bash
   # Run full test suite
   pytest
   
   # Run security scan
   make security-scan
   
   # Run build validation
   make build-validate
   ```

3. **Database Migration**
   ```bash
   # Test migration on staging
   flask db upgrade
   
   # Verify schema
   flask db current
   ```

4. **Deploy to Production**
   ```bash
   # Deploy using Render (automatic from git push)
   # Or manual deployment
   gcloud run deploy mdraft \
     --source . \
     --platform managed \
     --region us-central1
   ```

5. **Post-Deployment Verification**
   ```bash
   # Health check
   curl https://your-app.onrender.com/health
   
   # Migration status
   curl https://your-app.onrender.com/api/ops/migration_status
   
   # Smoke test
   python scripts/smoke_test.py
   ```

### Rollback Procedures

```bash
# Rollback deployment
gcloud run revisions list --service=mdraft
gcloud run services update-traffic mdraft --to-revisions=REVISION_NAME=100

# Rollback database migration
flask db downgrade

# Emergency rollback
gcloud run services update mdraft \
  --image gcr.io/project-id/mdraft:previous-version
```

---

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database connectivity
flask db current

# Test connection
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.session.execute('SELECT 1')
    print('Database connection successful')
"
```

#### Redis Connection Issues
```bash
# Test Redis connection
redis-cli ping

# Check Redis configuration
echo $REDIS_URL
```

#### Google Cloud Issues
```bash
# Verify authentication
gcloud auth list

# Test GCS access
gsutil ls gs://your-bucket-name

# Check service account permissions
gcloud projects get-iam-policy your-project-id
```

### Debugging

#### Enable Debug Mode
```bash
export FLASK_DEBUG=1
export LOG_LEVEL=DEBUG
python run.py
```

#### Log Analysis
```bash
# View application logs
tail -f flask.log

# Search for errors
grep ERROR flask.log

# Monitor requests
grep "Request.*took" flask.log
```

#### Performance Issues
```bash
# Check database performance
flask db execute "SELECT * FROM pg_stat_activity"

# Monitor Redis
redis-cli info memory

# Check GCS usage
gsutil du -sh gs://your-bucket-name
```

### Error Handling

#### Common Error Codes

- **400 Bad Request**: Invalid input data
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error

#### Error Response Format
```python
{
    "status": "error",
    "error": "error_type",
    "message": "Human readable message",
    "details": {
        "field": "specific error details"
    }
}
```

---

## Best Practices

### Code Style

#### Python Style Guide
```python
# Use type hints
def process_file(filename: str) -> Dict[str, Any]:
    """Process a file and return results."""
    pass

# Use docstrings
class FileProcessor:
    """Process uploaded files and convert to markdown."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize processor with configuration."""
        self.config = config

# Use meaningful variable names
user_email = user.email  # Good
e = user.email          # Bad

# Use constants for magic numbers
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
CHUNK_SIZE = 3000
```

#### Flask Best Practices
```python
# Use blueprints for organization
from flask import Blueprint

bp = Blueprint("api", __name__)

@bp.route("/api/endpoint", methods=["POST"])
def endpoint():
    pass

# Use decorators for common functionality
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "authentication_required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Use proper error handling
@bp.route("/api/endpoint", methods=["POST"])
def endpoint():
    try:
        # Process request
        result = process_request(request)
        return jsonify({"status": "success", "data": result})
    except ValidationError as e:
        return jsonify({"error": "validation_error", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "internal_error"}), 500
```

### Security Best Practices

#### Input Validation
```python
# Validate file uploads
def validate_file_upload(file):
    if not file:
        raise ValidationError("No file provided")
    
    if not is_file_allowed(file.filename):
        raise ValidationError("File type not allowed")
    
    if file.content_length > MAX_FILE_SIZE:
        raise ValidationError("File too large")
    
    return file

# Validate JSON input
def validate_json_schema(data, schema):
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        raise ValidationError(f"Invalid data: {e.message}")

# Sanitize user input
from app.services.prompt_sanitization import sanitize_for_prompt

def process_user_input(user_input: str) -> str:
    return sanitize_for_prompt(user_input)
```

#### Authentication & Authorization
```python
# Always check authentication
@require_auth
def protected_endpoint():
    pass

# Check permissions
def require_subscription(plan: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.subscription_status != plan:
                return jsonify({"error": "subscription_required"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Use secure session configuration
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

### Performance Best Practices

#### Database Optimization
```python
# Use eager loading for relationships
jobs = Job.query.options(joinedload(Job.user)).filter_by(status='pending').all()

# Use pagination for large result sets
jobs = Job.query.paginate(page=page, per_page=20, error_out=False)

# Use bulk operations
db.session.bulk_insert_mappings(Job, job_data)

# Use appropriate indexes
# Add to migration files
op.create_index('idx_jobs_status_created', 'jobs', ['status', 'created_at'])
```

#### Caching
```python
# Cache expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user_by_id(user_id: int):
    return User.query.get(user_id)

# Use Redis for distributed caching
import redis

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"))

def get_cached_data(key: str) -> Optional[Dict]:
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def cache_data(key: str, data: Dict, ttl: int = 3600):
    redis_client.setex(key, ttl, json.dumps(data))
```

---

## API Development

### API Design Principles

#### RESTful Design
```python
# Use proper HTTP methods
@bp.route("/api/resources", methods=["GET"])
def list_resources():
    """List all resources."""
    pass

@bp.route("/api/resources", methods=["POST"])
def create_resource():
    """Create a new resource."""
    pass

@bp.route("/api/resources/<int:id>", methods=["GET"])
def get_resource(id):
    """Get a specific resource."""
    pass

@bp.route("/api/resources/<int:id>", methods=["PUT"])
def update_resource(id):
    """Update a resource."""
    pass

@bp.route("/api/resources/<int:id>", methods=["DELETE"])
def delete_resource(id):
    """Delete a resource."""
    pass
```

#### Response Format
```python
# Success response
{
    "status": "success",
    "data": {
        "id": 123,
        "name": "Resource Name",
        "created_at": "2024-01-01T00:00:00Z"
    },
    "message": "Resource created successfully"
}

# Error response
{
    "status": "error",
    "error": "validation_error",
    "message": "Invalid input data",
    "details": {
        "field": "required_field is required"
    }
}
```

### API Documentation

#### OpenAPI/Swagger
```python
# app/api/docs.py
from flask_restx import Api, Resource, fields

api = Api(app, title='MDraft API', version='1.0', description='Document processing API')

# Define models
resource_model = api.model('Resource', {
    'id': fields.Integer(description='Resource ID'),
    'name': fields.String(required=True, description='Resource name'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

# Document endpoints
@api.route('/api/resources')
class ResourceList(Resource):
    @api.doc('list_resources')
    @api.marshal_list_with(resource_model)
    def get(self):
        """List all resources."""
        pass
    
    @api.doc('create_resource')
    @api.expect(resource_model)
    @api.marshal_with(resource_model, code=201)
    def post(self):
        """Create a new resource."""
        pass
```

### API Testing

#### Test API Endpoints
```python
# tests/test_api.py
def test_api_endpoint(client):
    """Test API endpoint."""
    response = client.get('/api/resources')
    assert response.status_code == 200
    
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'data' in data

def test_api_error_handling(client):
    """Test API error handling."""
    response = client.get('/api/resources/999')
    assert response.status_code == 404
    
    data = response.get_json()
    assert data['status'] == 'error'
    assert data['error'] == 'not_found'
```

---

**Document Control**
- **Version**: 1.0
- **Last Updated**: December 2024
- **Next Review**: March 2025
- **Approved By**: Technical Architecture Team
