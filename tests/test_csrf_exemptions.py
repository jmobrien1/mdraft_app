"""
Tests for refactored CSRF exemption logic.

Tests cover the new @csrf_exempt_api decorator and is_api_request() helper
function that provide explicit allowlist validation for CSRF exemptions.
"""

import pytest
from flask import Flask, request, jsonify
from flask_wtf.csrf import CSRFProtect
from unittest.mock import patch, MagicMock
import logging


class TestIsApiRequestHelper:
    """Test the is_api_request() helper function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config.update({
            'SECRET_KEY': 'test-secret-key',
            'WTF_CSRF_ENABLED': True,
            'TESTING': True
        })
        
        # Import the helper function
        from app.utils.csrf import is_api_request
        self.is_api_request = is_api_request
    
    def test_json_content_type_exempt(self):
        """Test that requests with JSON content type are exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Content-Type': 'application/json'}
        ):
            assert self.is_api_request(request) is True
    
    def test_json_content_type_with_charset_exempt(self):
        """Test that requests with JSON content type and charset are exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Content-Type': 'application/json; charset=utf-8'}
        ):
            assert self.is_api_request(request) is True
    
    def test_bearer_token_exempt(self):
        """Test that requests with Bearer token are exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Authorization': 'Bearer valid-token'}
        ):
            assert self.is_api_request(request) is True
    
    def test_api_key_exempt(self):
        """Test that requests with API key are exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'X-API-Key': 'valid-api-key'}
        ):
            assert self.is_api_request(request) is True
    
    def test_form_content_type_not_exempt(self):
        """Test that form requests are not exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        ):
            assert self.is_api_request(request) is False
    
    def test_no_content_type_not_exempt(self):
        """Test that requests without content type are not exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={}
        ):
            assert self.is_api_request(request) is False
    
    def test_multiple_auth_methods_exempt(self):
        """Test that requests with multiple auth methods are exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer valid-token',
                'X-API-Key': 'valid-api-key'
            }
        ):
            assert self.is_api_request(request) is True
    
    def test_case_insensitive_content_type(self):
        """Test that content type matching is case insensitive."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Content-Type': 'APPLICATION/JSON'}
        ):
            assert self.is_api_request(request) is True
    
    def test_partial_content_type_match(self):
        """Test that partial content type matches work."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Content-Type': 'application/json; version=2'}
        ):
            assert self.is_api_request(request) is True


class TestLegacyCompatibility:
    """Test backward compatibility with legacy functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config.update({
            'SECRET_KEY': 'test-secret-key',
            'WTF_CSRF_ENABLED': True,
            'TESTING': True
        })
        
        # Import legacy functions
        from app.utils.csrf import should_exempt_csrf, exempt_csrf_for_request
        
        self.should_exempt_csrf = should_exempt_csrf
        self.exempt_csrf_for_request = exempt_csrf_for_request
    
    def test_legacy_should_exempt_csrf_function(self):
        """Test that legacy should_exempt_csrf function still works."""
        with pytest.warns(DeprecationWarning):
            with self.app.test_request_context(
                '/api/test',
                method='POST',
                headers={'Authorization': 'Bearer valid-token'}
            ):
                assert self.should_exempt_csrf() is True
    
    def test_legacy_exempt_csrf_for_request_function(self):
        """Test that legacy exempt_csrf_for_request function still works."""
        with pytest.warns(DeprecationWarning):
            with self.app.app_context():
                # This function should not raise an exception
                self.exempt_csrf_for_request()


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config.update({
            'SECRET_KEY': 'test-secret-key',
            'WTF_CSRF_ENABLED': True,
            'TESTING': True
        })
        
        # Import the helper function
        from app.utils.csrf import is_api_request
        self.is_api_request = is_api_request
    
    def test_empty_bearer_token_not_exempt(self):
        """Test that empty Bearer token is not exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Authorization': 'Bearer '}
        ):
            assert self.is_api_request(request) is False
    
    def test_malformed_bearer_token_not_exempt(self):
        """Test that malformed Bearer token is not exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Authorization': 'BearerToken'}
        ):
            assert self.is_api_request(request) is False
    
    def test_empty_api_key_not_exempt(self):
        """Test that empty API key is not exempt."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'X-API-Key': ''}
        ):
            assert self.is_api_request(request) is False
    
    def test_mixed_case_content_type(self):
        """Test that mixed case content type is handled correctly."""
        with self.app.test_request_context(
            '/api/test',
            method='POST',
            headers={'Content-Type': 'Application/Json'}
        ):
            assert self.is_api_request(request) is True


if __name__ == "__main__":
    pytest.main([__file__])
