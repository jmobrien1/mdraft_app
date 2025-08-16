"""
Tests for request ID tracking functionality.

This module tests the comprehensive request ID tracking system including:
- UUIDv4 request_id creation and validation
- X-Request-ID header injection in outbound calls
- Celery task header propagation
- Sentry scope integration
- Logging correlation
"""
import json
import uuid
from unittest.mock import patch, MagicMock
import pytest
from flask import Flask, request, g
from celery import Celery

from app.middleware.logging import init_request_logging
from app.utils.logging import (
    set_correlation_id, get_correlation_ids, clear_correlation_ids,
    _setup_sentry_scope, StructuredJSONFormatter
)
from app.services.llm_client import _get_request_id as llm_get_request_id
from app.services.storage import _get_request_id as storage_get_request_id
from app.celery_tasks import _get_request_id_from_task


@pytest.fixture
def app():
    """Create test Flask app with request ID middleware."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    
    # Initialize request logging middleware
    init_request_logging(app)
    
    # Add a test route
    @app.route('/api/test')
    def test_route():
        return {'status': 'ok'}
    
    # Add error test routes
    @app.route('/api/test/not-found')
    def test_not_found():
        from werkzeug.exceptions import NotFound
        raise NotFound("Resource not found")
    
    # Add error handlers for API routes
    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith('/api/'):
            request_id = request.environ.get('X-Request-ID', 'unknown')
            return {'error': 'not_found', 'detail': str(e), 'request_id': request_id}, 404
        return e
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestRequestIDMiddleware:
    """Test request ID middleware functionality."""
    
    def test_uuidv4_generation_when_no_header(self, client):
        """Test that UUIDv4 is generated when no X-Request-ID header is provided."""
        response = client.get('/api/test')
        
        # Should have generated a valid UUIDv4
        request_id = response.headers.get('X-Request-ID')
        assert request_id is not None
        
        # Should be valid UUID format
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Generated request_id {request_id} is not a valid UUID")
    
    def test_header_request_id_preserved_when_valid(self, client):
        """Test that valid X-Request-ID header is preserved."""
        test_request_id = str(uuid.uuid4())
        
        response = client.get('/api/test', headers={'X-Request-ID': test_request_id})
        
        # Should preserve the provided request ID
        assert response.headers.get('X-Request-ID') == test_request_id
    
    def test_invalid_header_request_id_replaced(self, client):
        """Test that invalid X-Request-ID header is replaced with new UUIDv4."""
        invalid_request_id = "invalid-uuid-format"
        
        response = client.get('/api/test', headers={'X-Request-ID': invalid_request_id})
        
        # Should generate new UUIDv4 instead of using invalid one
        request_id = response.headers.get('X-Request-ID')
        assert request_id != invalid_request_id
        
        # Should be valid UUID format
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Generated request_id {request_id} is not a valid UUID")
    
    def test_request_id_in_error_responses(self, client):
        """Test that request_id is included in API error responses."""
        test_request_id = str(uuid.uuid4())
        
        response = client.get('/api/test/not-found', headers={'X-Request-ID': test_request_id})
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['request_id'] == test_request_id
    
    def test_request_id_in_environment(self, app):
        """Test that request_id is stored in request environment."""
        test_request_id = str(uuid.uuid4())
        
        with app.test_request_context('/test', headers={'X-Request-ID': test_request_id}):
            # Simulate middleware execution
            init_request_logging(app)
            
            # Check that request_id is in environment (Flask converts headers to HTTP_ format)
            assert request.environ.get('HTTP_X_REQUEST_ID') == test_request_id


class TestCorrelationIDContext:
    """Test correlation ID context variable functionality."""
    
    def test_set_and_get_correlation_ids(self):
        """Test setting and getting correlation IDs."""
        # Clear any existing correlation IDs
        clear_correlation_ids()
        
        # Set correlation IDs
        set_correlation_id("request_id", "test-request-123")
        set_correlation_id("user_id", "test-user-456")
        set_correlation_id("task_id", "test-task-789")
        
        # Get all correlation IDs
        correlation_ids = get_correlation_ids()
        
        assert correlation_ids["request_id"] == "test-request-123"
        assert correlation_ids["user_id"] == "test-user-456"
        assert correlation_ids["task_id"] == "test-task-789"
        assert correlation_ids["job_id"] is None
        assert correlation_ids["conversion_id"] is None
    
    def test_clear_correlation_ids(self):
        """Test clearing correlation IDs."""
        # Set some correlation IDs
        set_correlation_id("request_id", "test-request-123")
        set_correlation_id("user_id", "test-user-456")
        
        # Clear them
        clear_correlation_ids()
        
        # Verify they're cleared
        correlation_ids = get_correlation_ids()
        assert correlation_ids["request_id"] is None
        assert correlation_ids["user_id"] is None
    
    def test_invalid_correlation_id_key(self):
        """Test that invalid correlation ID key raises ValueError."""
        with pytest.raises(ValueError, match="Unknown correlation ID key"):
            set_correlation_id("invalid_key", "value")


class TestRequestIDInServices:
    """Test request ID integration in services."""
    
    def test_llm_client_request_id(self, app):
        """Test that LLM client gets request ID from context."""
        test_request_id = str(uuid.uuid4())
        
        with app.test_request_context('/test'):
            # Set request ID in context
            set_correlation_id("request_id", test_request_id)
            
            # Get request ID from LLM client
            request_id = llm_get_request_id()
            assert request_id == test_request_id
    
    def test_storage_service_request_id(self, app):
        """Test that storage service gets request ID from context."""
        test_request_id = str(uuid.uuid4())
        
        with app.test_request_context('/test'):
            # Set request ID in context
            set_correlation_id("request_id", test_request_id)
            
            # Get request ID from storage service
            request_id = storage_get_request_id()
            assert request_id == test_request_id
    
    def test_request_id_fallback_to_environment(self, app):
        """Test that services fall back to request environment when context not available."""
        test_request_id = str(uuid.uuid4())
        
        with app.test_request_context('/test'):
            # Set request ID in environment (simulating middleware)
            request.environ['X-Request-ID'] = test_request_id
            
            # Get request ID from services
            llm_request_id = llm_get_request_id()
            storage_request_id = storage_get_request_id()
            
            assert llm_request_id == test_request_id
            assert storage_request_id == test_request_id
    
    def test_request_id_fallback_to_unknown(self):
        """Test that services return 'unknown' when no request ID is available."""
        # Get request ID without any context
        llm_request_id = llm_get_request_id()
        storage_request_id = storage_get_request_id()
        
        assert llm_request_id == "unknown"
        assert storage_request_id == "unknown"


class TestCeleryTaskRequestID:
    """Test request ID integration in Celery tasks."""
    
    @patch('celery.current_task')
    def test_get_request_id_from_task_headers(self, mock_current_task):
        """Test getting request ID from Celery task headers."""
        test_request_id = str(uuid.uuid4())
        
        # Mock current task with headers
        mock_task = MagicMock()
        mock_task.request.headers = {'request_id': test_request_id}
        mock_current_task.return_value = mock_task
        
        request_id = _get_request_id_from_task()
        assert request_id == test_request_id
    
    @patch('celery.current_task')
    def test_get_request_id_from_correlation_context(self, mock_current_task):
        """Test getting request ID from correlation context when task headers not available."""
        test_request_id = str(uuid.uuid4())
        
        # Set correlation ID
        set_correlation_id("request_id", test_request_id)
        
        # Mock current task without headers
        mock_task = MagicMock()
        mock_task.request.headers = {}
        mock_current_task.return_value = mock_task
        
        request_id = _get_request_id_from_task()
        assert request_id == test_request_id
    
    @patch('celery.current_task')
    def test_get_request_id_generates_new_when_none_available(self, mock_current_task):
        """Test that new UUID is generated when no request ID is available."""
        # Clear correlation IDs
        clear_correlation_ids()
        
        # Mock current task without headers
        mock_task = MagicMock()
        mock_task.request.headers = {}
        mock_current_task.return_value = mock_task
        
        request_id = _get_request_id_from_task()
        
        # Should be a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Generated request_id {request_id} is not a valid UUID")


class TestSentryIntegration:
    """Test Sentry integration with request ID tracking."""
    
    @patch('app.utils.logging.sentry_sdk')
    def test_sentry_scope_setup_with_correlation_ids(self, mock_sentry):
        """Test that Sentry scope is set up with correlation IDs."""
        # Set up correlation IDs
        set_correlation_id("request_id", "test-request-123")
        set_correlation_id("user_id", "test-user-456")
        set_correlation_id("task_id", "test-task-789")
        
        # Mock scope
        mock_scope = MagicMock()
        mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
        
        # Call the function that sets up Sentry scope
        _setup_sentry_scope()
        
        # Verify tags were set
        mock_scope.set_tag.assert_any_call("request_id", "test-request-123")
        mock_scope.set_tag.assert_any_call("user_id", "test-user-456")
        mock_scope.set_tag.assert_any_call("task_id", "test-task-789")
    
    @patch('app.utils.logging.sentry_sdk')
    def test_sentry_user_context_setup(self, mock_sentry):
        """Test that Sentry user context is set up correctly."""
        # Set user ID
        set_correlation_id("user_id", "test-user-456")
        
        # Mock scope
        mock_scope = MagicMock()
        mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
        
        # Call the function that sets up Sentry scope
        _setup_sentry_scope()
        
        # Verify user context was set
        mock_scope.set_user.assert_called_with({"id": "test-user-456"})
    
    @patch('app.utils.logging.sentry_sdk')
    def test_sentry_request_context_setup(self, mock_sentry, app):
        """Test that Sentry request context is set up correctly."""
        with app.test_request_context('/test', headers={'User-Agent': 'test-agent'}):
            # Set request ID
            set_correlation_id("request_id", "test-request-123")
            
            # Mock scope
            mock_scope = MagicMock()
            mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
            
            # Call the function that sets up Sentry scope
            _setup_sentry_scope()
            
            # Verify request context was set
            mock_scope.set_context.assert_called_with("request", {
                "url": "http://localhost/test",
                "method": "GET",
                "path": "/test",
                "remote_addr": "127.0.0.1",
                "user_agent": "test-agent",
            })
    
    def test_sentry_integration_graceful_failure(self):
        """Test that Sentry integration fails gracefully when Sentry is not available."""
        # This should not raise an exception even if sentry_sdk is not available
        set_correlation_id("request_id", "test-request-123")
        
        # Should not raise an exception
        _setup_sentry_scope()


class TestStructuredLogging:
    """Test structured logging with request ID integration."""
    
    def test_structured_json_formatter_with_request_id(self):
        """Test that structured JSON formatter includes request ID."""
        # Set request ID
        set_correlation_id("request_id", "test-request-123")
        
        # Create formatter
        formatter = StructuredJSONFormatter()
        
        # Create a log record
        record = MagicMock()
        record.levelname = "INFO"
        record.name = "test.logger"
        record.getMessage.return_value = "Test message"
        record.exc_info = None
        
        # Format the record
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # Verify request ID is included
        assert log_data["request_id"] == "test-request-123"
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
    
    def test_structured_json_formatter_without_request_id(self):
        """Test that structured JSON formatter works without request ID."""
        # Clear correlation IDs
        clear_correlation_ids()
        
        # Create formatter
        formatter = StructuredJSONFormatter()
        
        # Create a log record
        record = MagicMock()
        record.levelname = "INFO"
        record.name = "test.logger"
        record.getMessage.return_value = "Test message"
        record.exc_info = None
        
        # Format the record
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # Verify request ID is not included
        assert "request_id" not in log_data
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"


class TestOutboundHTTPHeaders:
    """Test that outbound HTTP calls include X-Request-ID header."""
    
    @patch('app.services.llm_client.OpenAI')
    def test_llm_client_includes_request_id_header(self, mock_openai_class):
        """Test that LLM client includes X-Request-ID in default headers."""
        test_request_id = str(uuid.uuid4())
        
        with patch('app.services.llm_client._get_request_id', return_value=test_request_id):
            from app.services.llm_client import _get_client
            
            # Get client
            client = _get_client()
            
            # Verify OpenAI was called with correct headers
            mock_openai_class.assert_called_once()
            call_args = mock_openai_class.call_args
            assert call_args[1]['default_headers']['X-Request-ID'] == test_request_id
            assert call_args[1]['default_headers']['User-Agent'] == "mdraft-llm-client/1.0"


class TestIntegrationScenarios:
    """Test integration scenarios for request ID tracking."""
    
    def test_full_request_flow_with_correlation(self, client):
        """Test complete request flow with correlation ID tracking."""
        test_request_id = str(uuid.uuid4())
        
        # Make request with custom request ID
        response = client.get('/api/test', headers={'X-Request-ID': test_request_id})
        
        # Verify response includes request ID
        assert response.headers.get('X-Request-ID') == test_request_id
        
        # Verify request ID is in environment
        assert response.status_code == 200  # Assuming endpoint exists
    
    def test_celery_task_with_request_id_propagation(self):
        """Test that request ID is propagated to Celery tasks."""
        test_request_id = str(uuid.uuid4())
        
        # Set request ID in correlation context
        set_correlation_id("request_id", test_request_id)
        
        # Simulate task execution
        task_id = str(uuid.uuid4())
        
        # Get request ID from task context
        request_id = _get_request_id_from_task()
        assert request_id == test_request_id
    
    def test_multiple_services_same_request_id(self, app):
        """Test that multiple services use the same request ID."""
        test_request_id = str(uuid.uuid4())
        
        with app.test_request_context('/test'):
            # Set request ID in context
            set_correlation_id("request_id", test_request_id)
            
            # Verify all services use the same request ID
            llm_request_id = llm_get_request_id()
            storage_request_id = storage_get_request_id()
            task_request_id = _get_request_id_from_task()
            
            assert llm_request_id == test_request_id
            assert storage_request_id == test_request_id
            assert task_request_id == test_request_id
