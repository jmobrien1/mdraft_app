"""
Tests for fine-grained rate limiting functionality.

This module tests the rate limiting system with different authentication
methods (user_id, API key, IP) and verifies proper 429 responses.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_login import current_user
from app import create_app, db, limiter
from app.models import User
from app.models_apikey import ApiKey
from app.utils.rate_limiting import (
    get_rate_limit_key,
    get_combined_rate_limit_key,
    get_login_rate_limit_key,
    get_upload_rate_limit_key,
    get_index_rate_limit_key,
    _get_api_key,
    _get_client_ip,
    get_rate_limit_identifier,
    validate_rate_limit_key,
    get_rate_limit_info
)


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_DISABLED'] = False
    
    # Use in-memory SQLite for testing
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def auth_user(app):
    """Create an authenticated user for testing."""
    with app.app_context():
        user = User(
            email='test@example.com',
            password_hash='dummy_hash',
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def api_key_user(app, auth_user):
    """Create an API key for testing."""
    with app.app_context():
        api_key = ApiKey(
            user_id=auth_user.id,
            key='test-api-key-12345',
            name='Test API Key',
            is_active=True,
            rate_limit='30 per minute'
        )
        db.session.add(api_key)
        db.session.commit()
        return api_key


class TestRateLimitKeyFunctions:
    """Test the rate limiting key functions."""
    
    def test_get_rate_limit_key_authenticated_user(self, app, auth_user):
        """Test rate limit key for authenticated user."""
        with app.test_request_context('/'):
            with patch('app.utils.rate_limiting.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = auth_user.id
                
                key = get_rate_limit_key()
                assert key == f"user:{auth_user.id}"
    
    def test_get_rate_limit_key_api_key(self, app):
        """Test rate limit key for API key authentication."""
        with app.test_request_context('/', headers={'X-API-Key': 'test-key'}):
            key = get_rate_limit_key()
            assert key == "apikey:test-key"
    
    def test_get_rate_limit_key_ip_fallback(self, app):
        """Test rate limit key falls back to IP address."""
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.1'}):
            key = get_rate_limit_key()
            assert key == "ip:192.168.1.1"
    
    def test_get_login_rate_limit_key(self, app):
        """Test login rate limit key combines username and IP."""
        with app.test_request_context('/', 
                                     data={'email': 'test@example.com'},
                                     environ={'REMOTE_ADDR': '192.168.1.1'}):
            key = get_login_rate_limit_key()
            assert key == "login:test@example.com:192.168.1.1"
    
    def test_get_upload_rate_limit_key_authenticated(self, app, auth_user):
        """Test upload rate limit key for authenticated user."""
        with app.test_request_context('/'):
            with patch('app.utils.rate_limiting.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = auth_user.id
                
                key = get_upload_rate_limit_key()
                assert key == f"upload:user:{auth_user.id}"
    
    def test_get_upload_rate_limit_key_api_key(self, app):
        """Test upload rate limit key for API key."""
        with app.test_request_context('/', headers={'X-API-Key': 'test-key'}):
            key = get_upload_rate_limit_key()
            assert key == "upload:apikey:test-key"
    
    def test_get_upload_rate_limit_key_anonymous(self, app):
        """Test upload rate limit key for anonymous user."""
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.1'}):
            key = get_upload_rate_limit_key()
            assert key == "upload:ip:192.168.1.1"
    
    def test_get_index_rate_limit_key(self, app):
        """Test index rate limit key uses IP only."""
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.1'}):
            key = get_index_rate_limit_key()
            assert key == "index:ip:192.168.1.1"


class TestAPIKeyExtraction:
    """Test API key extraction from different sources."""
    
    def test_get_api_key_from_headers(self, app):
        """Test API key extraction from headers."""
        with app.test_request_context('/', headers={'X-API-Key': 'header-key'}):
            key = _get_api_key()
            assert key == 'header-key'
    
    def test_get_api_key_from_args(self, app):
        """Test API key extraction from query parameters."""
        with app.test_request_context('/?api_key=arg-key'):
            key = _get_api_key()
            assert key == 'arg-key'
    
    def test_get_api_key_from_cookies(self, app):
        """Test API key extraction from cookies."""
        with app.test_request_context('/'):
            with app.test_client() as client:
                client.set_cookie('localhost', 'api_key', 'cookie-key')
                key = _get_api_key()
                assert key == 'cookie-key'
    
    def test_get_api_key_priority(self, app):
        """Test API key extraction priority (headers > args > cookies)."""
        with app.test_request_context('/?api_key=arg-key'):
            with app.test_client() as client:
                client.set_cookie('localhost', 'api_key', 'cookie-key')
                with patch('flask.request') as mock_request:
                    mock_request.headers = {'X-API-Key': 'header-key'}
                    mock_request.args = {'api_key': 'arg-key'}
                    mock_request.cookies = {'api_key': 'cookie-key'}
                    
                    key = _get_api_key()
                    assert key == 'header-key'  # Headers should take priority


class TestClientIPExtraction:
    """Test client IP address extraction."""
    
    def test_get_client_ip_forwarded_for(self, app):
        """Test IP extraction from X-Forwarded-For header."""
        with app.test_request_context('/', headers={'X-Forwarded-For': '192.168.1.1, 10.0.0.1'}):
            ip = _get_client_ip()
            assert ip == '192.168.1.1'  # Should take first IP in chain
    
    def test_get_client_ip_real_ip(self, app):
        """Test IP extraction from X-Real-IP header."""
        with app.test_request_context('/', headers={'X-Real-IP': '192.168.1.2'}):
            ip = _get_client_ip()
            assert ip == '192.168.1.2'
    
    def test_get_client_ip_remote_addr(self, app):
        """Test IP extraction from remote_addr."""
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.3'}):
            ip = _get_client_ip()
            assert ip == '192.168.1.3'
    
    def test_get_client_ip_fallback(self, app):
        """Test IP extraction fallback to 'unknown'."""
        with app.test_request_context('/'):
            ip = _get_client_ip()
            assert ip == 'unknown'


class TestRateLimitValidation:
    """Test rate limit key validation."""
    
    def test_validate_rate_limit_key_valid(self, app):
        """Test validation of valid rate limit keys."""
        valid_keys = [
            "user:123",
            "apikey:test-key",
            "ip:192.168.1.1",
            "login:user@example.com:192.168.1.1",
            "upload:user:123",
            "index:ip:192.168.1.1"
        ]
        
        for key in valid_keys:
            assert validate_rate_limit_key(key) is True
    
    def test_validate_rate_limit_key_invalid(self, app):
        """Test validation of invalid rate limit keys."""
        invalid_keys = [
            "",
            None,
            "invalid:key",
            "user",
            "123",
            "random:key:value"
        ]
        
        for key in invalid_keys:
            assert validate_rate_limit_key(key) is False


class TestRateLimitInfo:
    """Test rate limit information gathering."""
    
    def test_get_rate_limit_info_authenticated(self, app, auth_user):
        """Test rate limit info for authenticated user."""
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.1'}):
            with patch('app.utils.rate_limiting.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = auth_user.id
                
                info = get_rate_limit_info()
                
                assert info['rate_limit_key'] == f"user:{auth_user.id}"
                assert info['identifier_type'] == 'user_id'
                assert info['client_ip'] == '192.168.1.1'
                assert info['user_authenticated'] is True
                assert info['user_id'] == auth_user.id
                assert info['has_api_key'] is False
    
    def test_get_rate_limit_info_api_key(self, app):
        """Test rate limit info for API key."""
        with app.test_request_context('/', 
                                     headers={'X-API-Key': 'test-key'},
                                     environ={'REMOTE_ADDR': '192.168.1.1'}):
            info = get_rate_limit_info()
            
            assert info['rate_limit_key'].startswith('apikey:')
            assert info['identifier_type'] == 'api_key'
            assert info['client_ip'] == '192.168.1.1'
            assert info['user_authenticated'] is False
            assert info['has_api_key'] is True
            assert 'api_key_hash' in info


class TestRateLimitEndpoints:
    """Test rate limiting on actual endpoints."""
    
    def test_index_rate_limit(self, client):
        """Test rate limiting on index endpoint."""
        # Make 51 requests (over the 50 per minute limit)
        for i in range(51):
            response = client.get('/')
            if i < 50:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
                data = json.loads(response.data)
                assert 'error' in data or 'message' in data
    
    def test_login_rate_limit(self, client):
        """Test rate limiting on login endpoint."""
        # Make 11 login attempts (over the 10 per minute limit)
        for i in range(11):
            response = client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'wrongpassword'
            })
            if i < 10:
                assert response.status_code in [200, 401, 403]  # Normal responses
            else:
                assert response.status_code == 429
                data = json.loads(response.data)
                assert 'error' in data or 'message' in data
    
    def test_upload_rate_limit_authenticated(self, client, auth_user):
        """Test rate limiting on upload endpoint for authenticated user."""
        # Login first
        with client.session_transaction() as sess:
            sess['_user_id'] = auth_user.id
        
        # Make 21 upload attempts (over the 20 per minute limit)
        for i in range(21):
            response = client.post('/upload', data={
                'file': (b'test content', 'test.txt')
            })
            if i < 20:
                assert response.status_code in [202, 400, 401]  # Normal responses
            else:
                assert response.status_code == 429
                data = json.loads(response.data)
                assert 'error' in data or 'message' in data
    
    def test_upload_rate_limit_anonymous(self, client):
        """Test rate limiting on upload endpoint for anonymous user."""
        # Make 21 upload attempts (over the 20 per minute limit)
        for i in range(21):
            response = client.post('/upload', data={
                'file': (b'test content', 'test.txt')
            })
            if i < 20:
                assert response.status_code in [202, 400, 401]  # Normal responses
            else:
                assert response.status_code == 429
                data = json.loads(response.data)
                assert 'error' in data or 'message' in data
    
    def test_api_upload_rate_limit(self, client, auth_user):
        """Test rate limiting on API upload endpoint."""
        # Login first
        with client.session_transaction() as sess:
            sess['_user_id'] = auth_user.id
        
        # Make 21 API upload attempts (over the 20 per minute limit)
        for i in range(21):
            response = client.post('/api/upload', data={
                'file': (b'test content', 'test.txt')
            })
            if i < 20:
                assert response.status_code in [202, 400, 401]  # Normal responses
            else:
                assert response.status_code == 429
                data = json.loads(response.data)
                assert 'error' in data or 'message' in data


class TestRateLimitConfiguration:
    """Test rate limit configuration and customization."""
    
    def test_api_key_custom_rate_limit(self, app, api_key_user):
        """Test custom rate limits for API keys."""
        with app.test_request_context('/', headers={'X-API-Key': api_key_user.key}):
            # The API key has a custom rate limit of '30 per minute'
            # This should be respected by the rate limiting system
            key = get_rate_limit_key()
            assert key == f"apikey:{api_key_user.key}"
    
    def test_different_limits_for_different_endpoints(self, client):
        """Test that different endpoints have different rate limits."""
        # Index endpoint: 50 per minute
        # Login endpoint: 10 per minute
        # Upload endpoint: 20 per minute
        
        # Test index endpoint limit
        for i in range(51):
            response = client.get('/')
            if i == 50:
                assert response.status_code == 429
        
        # Test login endpoint limit (should be more restrictive)
        for i in range(11):
            response = client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'wrongpassword'
            })
            if i == 10:
                assert response.status_code == 429


class TestRateLimitHeaders:
    """Test rate limit headers in responses."""
    
    def test_rate_limit_headers_present(self, client):
        """Test that rate limit headers are present in responses."""
        response = client.get('/')
        assert response.status_code == 200
        
        # Check for rate limit headers
        headers = response.headers
        assert 'X-RateLimit-Limit' in headers
        assert 'X-RateLimit-Remaining' in headers
        assert 'X-RateLimit-Reset' in headers
    
    def test_rate_limit_headers_on_429(self, client):
        """Test rate limit headers on 429 responses."""
        # Exceed rate limit
        for i in range(51):
            response = client.get('/')
            if i == 50:
                assert response.status_code == 429
                
                # Check for rate limit headers on 429
                headers = response.headers
                assert 'X-RateLimit-Limit' in headers
                assert 'X-RateLimit-Remaining' in headers
                assert 'X-RateLimit-Reset' in headers
                assert 'Retry-After' in headers


class TestRateLimitSecurity:
    """Test rate limiting security aspects."""
    
    def test_rate_limit_key_isolation(self, app):
        """Test that different users have isolated rate limits."""
        # This test would require a more complex setup with multiple users
        # and rate limit storage, but the concept is that user A's rate
        # limits should not affect user B's rate limits
        
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.1'}):
            key1 = get_rate_limit_key()
        
        with app.test_request_context('/', environ={'REMOTE_ADDR': '192.168.1.2'}):
            key2 = get_rate_limit_key()
        
        assert key1 != key2  # Different IPs should have different keys
    
    def test_rate_limit_key_consistency(self, app, auth_user):
        """Test that rate limit keys are consistent for the same user."""
        with app.test_request_context('/'):
            with patch('app.utils.rate_limiting.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = auth_user.id
                
                key1 = get_rate_limit_key()
                key2 = get_rate_limit_key()
                
                assert key1 == key2  # Same user should have same key


if __name__ == '__main__':
    pytest.main([__file__])
