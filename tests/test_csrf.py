"""
Tests for CSRF protection implementation.

Tests cover CSRF token validation for HTML forms and exemption for API routes
with proper authentication (Bearer tokens, API keys).
"""

import pytest
from flask import Flask, request
from flask_wtf.csrf import CSRFProtect
from unittest.mock import patch, MagicMock


class TestCSRFProtection:
    """Test CSRF protection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config.update({
            'SECRET_KEY': 'test-secret-key',
            'WTF_CSRF_ENABLED': True,
            'WTF_CSRF_TIME_LIMIT': 3600,
            'TESTING': True
        })
        
        # Initialize CSRF protection
        self.csrf = CSRFProtect()
        self.csrf.init_app(self.app)
        
        # Register test routes
        @self.app.route('/form', methods=['GET', 'POST'])
        def test_form():
            if request.method == 'POST':
                return {'status': 'success'}, 200
            from flask import render_template_string
            template = '''
            <form method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button type="submit">Submit</button>
            </form>
            '''
            return render_template_string(template), 200
        
        @self.app.route('/api/test', methods=['POST'])
        def test_api():
            return {'status': 'success'}, 200
        
        self.client = self.app.test_client()
    
    def test_csrf_token_generation(self):
        """Test that CSRF tokens are generated correctly."""
        with self.app.app_context():
            # Get a CSRF token
            response = self.client.get('/form')
            assert response.status_code == 200
            assert b'csrf_token' in response.data
    
    def test_form_without_csrf_token_rejected(self):
        """Test that forms without CSRF tokens are rejected."""
        response = self.client.post('/form')
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data.lower()
    
    def test_form_with_valid_csrf_token_accepted(self):
        """Test that forms with valid CSRF tokens are accepted."""
        # First get the form to get a CSRF token
        get_response = self.client.get('/form')
        assert get_response.status_code == 200
        
        # Extract CSRF token from the form
        import re
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', get_response.data.decode())
        assert csrf_match is not None
        csrf_token = csrf_match.group(1)
        
        # Submit form with CSRF token
        post_response = self.client.post('/form', data={'csrf_token': csrf_token})
        assert post_response.status_code == 200
        assert b'success' in post_response.data
    
    def test_form_with_invalid_csrf_token_rejected(self):
        """Test that forms with invalid CSRF tokens are rejected."""
        response = self.client.post('/form', data={'csrf_token': 'invalid-token'})
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data.lower()
    
    def test_api_without_auth_not_exempt(self):
        """Test that API routes without authentication are not exempt from CSRF."""
        response = self.client.post('/api/test')
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data.lower()


class TestCSRFExemptionDecorators:
    """Test CSRF exemption decorators."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config.update({
            'SECRET_KEY': 'test-secret-key',
            'WTF_CSRF_ENABLED': True,
            'TESTING': True
        })
        
        # Initialize CSRF protection
        self.csrf = CSRFProtect()
        self.csrf.init_app(self.app)
        
        # Import and test decorators
        from app.utils.csrf import csrf_exempt, csrf_exempt_for_api
        
        @self.app.route('/exempt', methods=['POST'])
        @csrf_exempt
        def test_exempt():
            return {'status': 'exempt'}, 200
        
        @self.app.route('/api/exempt', methods=['POST'])
        @csrf_exempt_for_api
        def test_api_exempt():
            return {'status': 'api_exempt'}, 200
        
        self.client = self.app.test_client()
    
    def test_csrf_exempt_decorator(self):
        """Test that @csrf_exempt decorator works."""
        response = self.client.post('/exempt')
        assert response.status_code == 200
        assert b'exempt' in response.data
    
    def test_csrf_exempt_for_api_without_auth(self):
        """Test that @csrf_exempt_for_api requires authentication."""
        response = self.client.post('/api/exempt')
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data.lower()
    
    def test_csrf_exempt_for_api_with_bearer_token(self):
        """Test that @csrf_exempt_for_api works with Bearer token."""
        response = self.client.post('/api/exempt', headers={'Authorization': 'Bearer valid-token'})
        assert response.status_code == 200
        assert b'api_exempt' in response.data
    
    def test_csrf_exempt_for_api_with_api_key(self):
        """Test that @csrf_exempt_for_api works with API key."""
        response = self.client.post('/api/exempt', headers={'X-API-Key': 'valid-api-key'})
        assert response.status_code == 200
        assert b'api_exempt' in response.data


class TestCSRFConfiguration:
    """Test CSRF configuration and settings."""
    
    def test_csrf_exemption_logic(self):
        """Test CSRF exemption logic."""
        from app.utils.csrf import should_exempt_csrf
        
        # Create a mock request context
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        with app.test_request_context('/api/test', headers={'Authorization': 'Bearer valid-token'}):
            assert should_exempt_csrf() is True
        
        with app.test_request_context('/api/test', headers={'X-API-Key': 'valid-api-key'}):
            assert should_exempt_csrf() is True
        
        with app.test_request_context('/api/test', headers={}):
            assert should_exempt_csrf() is False
        
        with app.test_request_context('/form', headers={'Authorization': 'Bearer valid-token'}):
            assert should_exempt_csrf() is False


class TestCSRFIntegration:
    """Test CSRF protection integration with the actual application."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal app for testing
        self.app = Flask(__name__)
        self.app.config.update({
            'SECRET_KEY': 'test-secret-key',
            'WTF_CSRF_ENABLED': True,
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False
        })
        
        # Initialize CSRF protection
        from flask_wtf.csrf import CSRFProtect
        csrf = CSRFProtect()
        csrf.init_app(self.app)
        
        # Register test routes
        @self.app.route('/auth/login', methods=['POST'])
        def test_login():
            return {'status': 'login_success'}, 200
        
        @self.app.route('/api/convert', methods=['POST'])
        def test_api_convert():
            # Manually exempt this route for testing
            from app.utils.csrf import exempt_csrf_for_request
            exempt_csrf_for_request()
            return {'status': 'convert_success'}, 200
        
        self.client = self.app.test_client()
    
    def test_auth_login_form_requires_csrf(self):
        """Test that login form requires CSRF token."""
        response = self.client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123'
        })
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data.lower()
    
    def test_api_convert_without_auth_not_exempt(self):
        """Test that /api/convert without auth is not exempt from CSRF."""
        response = self.client.post('/api/convert')
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data.lower()
    
    def test_api_convert_with_bearer_token_exempt(self):
        """Test that /api/convert with Bearer token is exempt from CSRF."""
        response = self.client.post('/api/convert', headers={'Authorization': 'Bearer valid-token'})
        assert response.status_code == 200
        assert b'convert_success' in response.data
    
    def test_api_convert_with_api_key_exempt(self):
        """Test that /api/convert with API key is exempt from CSRF."""
        response = self.client.post('/api/convert', headers={'X-API-Key': 'valid-api-key'})
        assert response.status_code == 200
        assert b'convert_success' in response.data


if __name__ == "__main__":
    pytest.main([__file__])
