"""
Tests for unified error handling system.

Tests cover:
- Safe JSON error responses (no tracebacks)
- Request ID inclusion
- Structured logging
- Sentry integration
- HTTP status code mapping
- User context extraction
"""
import json
import logging
import os
from unittest.mock import patch, MagicMock, ANY
import pytest
from flask import Flask, request
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError, Unauthorized, Forbidden
from app.api.errors import errors, _get_request_id, _get_user_id, _map_exception_to_error


@pytest.fixture
def app():
    """Create test Flask app with error handlers."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    
    # Add request ID middleware (same as in __init__.py)
    @app.before_request
    def _set_request_id():
        """Set request ID for logging and tracing."""
        import uuid
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.environ['X-Request-ID'] = request_id
        request.environ['HTTP_X_REQUEST_ID'] = request_id
    
    # Register the errors blueprint
    app.register_blueprint(errors)
    
    # Add a test route that raises exceptions
    @app.route('/api/test/bad-request')
    def test_bad_request():
        raise BadRequest("Invalid input")
    
    @app.route('/api/test/not-found')
    def test_not_found():
        raise NotFound("Resource not found")
    
    @app.route('/api/test/server-error')
    def test_server_error():
        raise InternalServerError("Something went wrong")
    
    @app.route('/api/test/unauthorized')
    def test_unauthorized():
        raise Unauthorized("Login required")
    
    @app.route('/api/test/forbidden')
    def test_forbidden():
        raise Forbidden("Access denied")
    
    @app.route('/api/test/exception')
    def test_exception():
        raise ValueError("Test exception")
    
    @app.route('/api/test/rate-limit')
    def test_rate_limit():
        from werkzeug.exceptions import TooManyRequests
        raise TooManyRequests("Rate limit exceeded")
    
    @app.route('/api/test/payload-too-large')
    def test_payload_too_large():
        from werkzeug.exceptions import RequestEntityTooLarge
        raise RequestEntityTooLarge("File too large")
    
    @app.route('/ui/test/not-found')
    def test_ui_not_found():
        raise NotFound("Page not found")
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestErrorHandling:
    """Test error handling functionality."""
    
    def test_400_bad_request(self, client):
        """Test 400 Bad Request error handling."""
        response = client.get('/api/test/bad-request')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert data['error'] == 'bad_request'
        assert 'Invalid input' in data['message']
        assert 'request_id' in data
        assert data['request_id'] != 'unknown'
    
    def test_404_not_found(self, client):
        """Test 404 Not Found error handling."""
        response = client.get('/api/test/not-found')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert data['error'] == 'not_found'
        assert 'Resource not found' in data['message']
        assert 'request_id' in data
    
    def test_500_internal_server_error(self, client):
        """Test 500 Internal Server Error handling."""
        response = client.get('/api/test/server-error')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert data['error'] == 'internal_error'
        assert 'Something went wrong' in data['message']
        assert 'request_id' in data
    
    def test_401_unauthorized(self, client):
        """Test 401 Unauthorized error handling."""
        response = client.get('/api/test/unauthorized')
        data = json.loads(response.data)
        
        assert response.status_code == 401
        assert data['error'] == 'unauthorized'
        assert 'Login required' in data['message']
        assert 'request_id' in data
    
    def test_403_forbidden(self, client):
        """Test 403 Forbidden error handling."""
        response = client.get('/api/test/forbidden')
        data = json.loads(response.data)
        
        assert response.status_code == 403
        assert data['error'] == 'forbidden'
        assert 'Access denied' in data['message']
        assert 'request_id' in data
    
    def test_429_rate_limited(self, client):
        """Test 429 Too Many Requests error handling."""
        response = client.get('/api/test/rate-limit')
        data = json.loads(response.data)
        
        assert response.status_code == 429
        assert data['error'] == 'rate_limited'
        assert 'Rate limit exceeded' in data['message']
        assert 'request_id' in data
    
    def test_413_payload_too_large(self, client):
        """Test 413 Payload Too Large error handling."""
        response = client.get('/api/test/payload-too-large')
        data = json.loads(response.data)
        
        assert response.status_code == 413
        assert data['error'] == 'payload_too_large'
        assert 'File too large' in data['message']
        assert 'request_id' in data
    
    def test_generic_exception(self, client):
        """Test generic exception handling."""
        response = client.get('/api/test/exception')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert data['error'] == 'internal_error'
        assert 'Internal server error' in data['message']
        assert 'request_id' in data
    
    def test_ui_routes_not_affected(self, client):
        """Test that UI routes still use default Flask error handling."""
        response = client.get('/ui/test/not-found')
        
        # Should not be JSON for UI routes
        assert response.status_code == 404
        assert response.content_type != 'application/json'
    
    def test_request_id_preserved(self, client):
        """Test that request ID is preserved across error handling."""
        # Set a custom request ID
        headers = {'X-Request-ID': 'test-request-123'}
        
        response = client.get('/api/test/bad-request', headers=headers)
        data = json.loads(response.data)
        
        assert data['request_id'] == 'test-request-123'
    
    def test_no_traceback_in_response(self, client):
        """Test that no traceback information is exposed in responses."""
        response = client.get('/api/test/exception')
        data = json.loads(response.data)
        
        # Should not contain traceback information
        assert 'traceback' not in data
        assert 'Traceback' not in data['message']
        assert 'File "' not in data['message']
        assert 'line ' not in data['message']


class TestHelperFunctions:
    """Test helper functions in the errors module."""
    
    def test_get_request_id_with_header(self, app):
        """Test request ID extraction with header."""
        with app.test_request_context('/test', headers={'X-Request-ID': 'test-123'}):
            # Manually set the request ID in environment (simulating middleware)
            request.environ['X-Request-ID'] = 'test-123'
            request.environ['HTTP_X_REQUEST_ID'] = 'test-123'
            request_id = _get_request_id()
            assert request_id == 'test-123'
    
    def test_get_request_id_without_header(self, app):
        """Test request ID extraction without header."""
        with app.test_request_context('/test'):
            request_id = _get_request_id()
            # Should generate new UUID instead of returning 'unknown'
            assert len(request_id) == 36  # UUID length
            assert request_id != 'unknown'
    
    def test_get_user_id_authenticated(self, app):
        """Test user ID extraction for authenticated user."""
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = 123
        
        with patch('flask_login.current_user', mock_user):
            with app.test_request_context('/test'):
                user_id = _get_user_id()
                assert user_id == '123'
    
    def test_get_user_id_unauthenticated(self, app):
        """Test user ID extraction for unauthenticated user."""
        mock_user = MagicMock()
        mock_user.is_authenticated = False
        
        with patch('flask_login.current_user', mock_user):
            with app.test_request_context('/test'):
                user_id = _get_user_id()
                assert user_id is None
    
    def test_map_exception_to_error_http_exception(self):
        """Test exception mapping for HTTPException."""
        exception = BadRequest("Invalid input")
        error_name, detail, status = _map_exception_to_error(exception)
        
        assert error_name == 'bad_request'
        assert 'Invalid input' in detail
        assert status == 400
    
    def test_map_exception_to_error_generic(self):
        """Test exception mapping for generic exceptions."""
        exception = ValueError("Test error")
        error_name, detail, status = _map_exception_to_error(exception)
        
        assert error_name == 'internal_error'
        assert detail == 'Internal server error'
        assert status == 500


class TestSentryIntegration:
    """Test Sentry integration functionality."""
    
    @patch.dict(os.environ, {'SENTRY_DSN': 'https://test@sentry.io/123'})
    @patch('sentry_sdk.capture_exception')
    @patch('sentry_sdk.configure_scope')
    def test_sentry_capture_with_dsn(self, mock_configure_scope, mock_capture_exception, client):
        """Test that exceptions are captured in Sentry when DSN is set."""
        mock_scope = MagicMock()
        mock_configure_scope.return_value.__enter__.return_value = mock_scope
        
        response = client.get('/api/test/exception')
        
        # Verify Sentry was called
        mock_configure_scope.assert_called_once()
        mock_capture_exception.assert_called_once()
        
        # Verify scope was configured with request context
        mock_scope.set_tag.assert_called_with('request_id', ANY)
        mock_scope.set_context.assert_called_with('request', ANY)
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('sentry_sdk.capture_exception')
    def test_sentry_no_capture_without_dsn(self, mock_capture_exception, client):
        """Test that exceptions are not captured when DSN is not set."""
        response = client.get('/api/test/exception')
        
        # Verify Sentry was not called
        mock_capture_exception.assert_not_called()
    
    @patch.dict(os.environ, {'SENTRY_DSN': 'https://test@sentry.io/123'})
    @patch('sentry_sdk.capture_exception')
    @patch('sentry_sdk.configure_scope')
    def test_sentry_capture_with_user_context(self, mock_configure_scope, mock_capture_exception, client, app):
        """Test that user context is included in Sentry capture."""
        mock_scope = MagicMock()
        mock_configure_scope.return_value.__enter__.return_value = mock_scope
        
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = 456
        
        with patch('flask_login.current_user', mock_user):
            response = client.get('/api/test/exception')
            
            # Verify user context was set
            mock_scope.set_user.assert_called_with({'id': '456'})


class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_error_logging_structure(self, client, caplog):
        """Test that errors are logged with structured data."""
        with caplog.at_level(logging.ERROR):
            response = client.get('/api/test/bad-request')
        
        # Verify log message was recorded
        assert len(caplog.records) > 0
        
        # Find the error log record
        error_record = None
        for record in caplog.records:
            if record.levelno == logging.ERROR and 'Error occurred' in record.getMessage():
                error_record = record
                break
        
        assert error_record is not None
        
        # Verify structured data is present
        assert hasattr(error_record, 'path')
        assert hasattr(error_record, 'status')
        assert hasattr(error_record, 'request_id')
        assert hasattr(error_record, 'user_id')
        assert hasattr(error_record, 'error')
        assert hasattr(error_record, 'detail')
        
        # Verify values
        assert error_record.path == '/api/test/bad-request'
        assert error_record.status == 400
        assert error_record.error == 'bad_request'
        assert 'Invalid input' in error_record.detail
        assert error_record.user_id == 'anonymous'  # No user logged in


class TestErrorResponseFormat:
    """Test error response format consistency."""
    
    def test_error_response_structure(self, client):
        """Test that all error responses have consistent structure."""
        test_cases = [
            ('/api/test/bad-request', 400),
            ('/api/test/not-found', 404),
            ('/api/test/server-error', 500),
            ('/api/test/unauthorized', 401),
            ('/api/test/forbidden', 403),
        ]
        
        for endpoint, expected_status in test_cases:
            response = client.get(endpoint)
            data = json.loads(response.data)
            
            # Verify consistent structure
            assert 'error' in data
            assert 'message' in data  # Changed from 'detail' to 'message'
            assert 'request_id' in data
            
            # Verify status code
            assert response.status_code == expected_status
            
            # Verify content type
            assert response.content_type == 'application/json'
    
    def test_error_codes_consistency(self, client):
        """Test that error codes are consistent and follow naming convention."""
        response = client.get('/api/test/bad-request')
        data = json.loads(response.data)
        
        # Error codes should be snake_case
        assert '_' in data['error'] or data['error'].islower()
        assert ' ' not in data['error']
        assert data['error'].isalpha() or '_' in data['error']


if __name__ == '__main__':
    pytest.main([__file__])
