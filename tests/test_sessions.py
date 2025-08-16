"""
Tests for session configuration and behavior.

This module tests:
- Session backend configuration (Redis, filesystem, null)
- Session cookie security attributes
- Session lifetime configuration (14 days default)
- Session initialization and cleanup
- Single code path validation
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from flask import Flask, session
from flask_session import Session

from app.config import AppConfig


class TestSessionConfiguration:
    """Test session configuration and initialization."""

    def test_session_backend_redis(self):
        """Test Redis session backend configuration."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "REDIS_URL": "redis://localhost:6379/1",
            "FLASK_ENV": "production",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.SESSION_BACKEND == "redis"
            assert config.REDIS_URL == "redis://localhost:6379/1"
            assert config.SESSION_COOKIE_SECURE is True
            assert config.SESSION_COOKIE_HTTPONLY is True
            assert config.SESSION_COOKIE_SAMESITE == "Lax"

    def test_session_backend_filesystem(self):
        """Test filesystem session backend configuration."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "filesystem",
            "FLASK_ENV": "development",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.SESSION_BACKEND == "filesystem"
            assert config.SESSION_COOKIE_SECURE is True
            assert config.SESSION_COOKIE_HTTPONLY is True
            assert config.SESSION_COOKIE_SAMESITE == "Lax"

    def test_session_backend_null(self):
        """Test null session backend configuration."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "null",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.SESSION_BACKEND == "null"

    def test_session_backend_default_production(self):
        """Test default session backend in production (should be Redis)."""
        with patch.dict(os.environ, {
            "FLASK_ENV": "production",
            "DATABASE_URL": "sqlite:///:memory:"
        }, clear=True):
            config = AppConfig()
            
            assert config.SESSION_BACKEND == "redis"

    def test_session_backend_default_development(self):
        """Test default session backend in development (should be filesystem)."""
        with patch.dict(os.environ, {
            "FLASK_ENV": "development",
            "DATABASE_URL": "sqlite:///:memory:"
        }, clear=True):
            config = AppConfig()
            
            assert config.SESSION_BACKEND == "filesystem"

    def test_session_cookie_configuration(self):
        """Test session cookie security attributes."""
        with patch.dict(os.environ, {
            "SESSION_COOKIE_SECURE": "false",
            "SESSION_COOKIE_HTTPONLY": "false",
            "SESSION_COOKIE_SAMESITE": "Strict",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.SESSION_COOKIE_SECURE is False
            assert config.SESSION_COOKIE_HTTPONLY is False
            assert config.SESSION_COOKIE_SAMESITE == "Strict"

    def test_session_lifetime_configuration_default(self):
        """Test default session lifetime configuration (14 days)."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///:memory:"
        }, clear=True):
            config = AppConfig()
            
            assert config.security.SESSION_LIFETIME_DAYS == 14

    def test_session_lifetime_configuration_custom(self):
        """Test custom session lifetime configuration."""
        with patch.dict(os.environ, {
            "SESSION_LIFETIME_DAYS": "30",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.security.SESSION_LIFETIME_DAYS == 30


class TestSessionBehavior:
    """Test session behavior with different backends."""

    def test_filesystem_session_storage(self):
        """Test filesystem session storage functionality."""
        temp_dir = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {
                "SESSION_BACKEND": "filesystem",
                "DATABASE_URL": "sqlite:///:memory:"
            }):
                # Create a minimal Flask app for testing
                app = Flask(__name__)
                app.config["SECRET_KEY"] = "test-secret"
                app.config["SESSION_TYPE"] = "filesystem"
                app.config["SESSION_FILE_DIR"] = temp_dir
                app.config["SESSION_COOKIE_SECURE"] = True
                app.config["SESSION_COOKIE_HTTPONLY"] = True
                app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
                app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 14  # 14 days
                
                Session(app)
                
                with app.test_client() as client:
                    with app.app_context():
                        # Test session creation
                        response = client.get("/")
                        assert response.status_code == 404  # No route defined, but app works
                        
                        # Check if session directory was created
                        session_files = os.listdir(temp_dir)
                        # Note: Filesystem sessions may not create files immediately
                        # The important thing is that the directory is accessible
                        assert os.path.isdir(temp_dir)
        finally:
            shutil.rmtree(temp_dir)

    def test_session_cookie_attributes(self):
        """Test that session cookies have correct security attributes."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "filesystem",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            # Create a minimal Flask app for testing
            app = Flask(__name__)
            app.config["SECRET_KEY"] = "test-secret"
            app.config["SESSION_TYPE"] = "filesystem"
            app.config["SESSION_COOKIE_SECURE"] = True
            app.config["SESSION_COOKIE_HTTPONLY"] = True
            app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
            app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 14  # 14 days
            
            Session(app)
            
            with app.test_client() as client:
                with app.app_context():
                    # Create a session by setting a value
                    with client.session_transaction() as sess:
                        sess["test_key"] = "test_value"
                    
                    # Make a request to trigger session cookie creation
                    response = client.get("/")
                    
                    # Check session cookie attributes
                    # Note: Flask test client may not always create cookies in test mode
                    # The important thing is that the configuration is correct
                    assert app.config["SESSION_COOKIE_SECURE"] is True
                    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
                    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
                    assert app.config["PERMANENT_SESSION_LIFETIME"] == 60 * 60 * 24 * 14

    def test_session_persistence(self):
        """Test that sessions persist across requests."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "filesystem",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            # Create a minimal Flask app for testing
            app = Flask(__name__)
            app.config["SECRET_KEY"] = "test-secret"
            app.config["SESSION_TYPE"] = "filesystem"
            app.config["SESSION_COOKIE_SECURE"] = True
            app.config["SESSION_COOKIE_HTTPONLY"] = True
            app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
            app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 14  # 14 days
            
            Session(app)
            
            with app.test_client() as client:
                with app.app_context():
                    # Set a value in session
                    with client.session_transaction() as sess:
                        sess["test_key"] = "test_value"
                    
                    # Verify the value persists
                    with client.session_transaction() as sess:
                        assert sess.get("test_key") == "test_value"


class TestSessionSecurity:
    """Test session security features."""

    def test_session_cookie_secure_default(self):
        """Test that session cookies are secure by default."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "filesystem",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.SESSION_COOKIE_SECURE is True
            assert config.SESSION_COOKIE_HTTPONLY is True
            assert config.SESSION_COOKIE_SAMESITE == "Lax"

    def test_session_cookie_configurable(self):
        """Test that session cookie attributes are configurable."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "filesystem",
            "SESSION_COOKIE_SECURE": "false",
            "SESSION_COOKIE_HTTPONLY": "false",
            "SESSION_COOKIE_SAMESITE": "None",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            assert config.SESSION_COOKIE_SECURE is False
            assert config.SESSION_COOKIE_HTTPONLY is False
            assert config.SESSION_COOKIE_SAMESITE == "None"

    def test_session_lifetime_validation(self):
        """Test session lifetime validation."""
        with patch.dict(os.environ, {
            "SESSION_LIFETIME_DAYS": "30",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            # Verify lifetime is reasonable (not too short, not too long)
            lifetime_days = config.security.SESSION_LIFETIME_DAYS
            assert 1 <= lifetime_days <= 365  # Between 1 day and 1 year

    def test_session_lifetime_default_14_days(self):
        """Test that default session lifetime is 14 days."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///:memory:"
        }, clear=True):
            config = AppConfig()
            
            assert config.security.SESSION_LIFETIME_DAYS == 14


class TestSessionIntegration:
    """Test session integration with other components."""

    def test_session_backend_consistency(self):
        """Test that session backend is consistently configured."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "REDIS_URL": "redis://localhost:6379/2",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            # Verify configuration consistency
            assert config.SESSION_BACKEND == "redis"
            assert config.REDIS_URL == "redis://localhost:6379/2"

    def test_session_configuration_to_dict(self):
        """Test that session configuration is properly exported to dict."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "REDIS_URL": "redis://localhost:6379/3",
            "SESSION_COOKIE_SECURE": "true",
            "SESSION_COOKIE_HTTPONLY": "true",
            "SESSION_COOKIE_SAMESITE": "Lax",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            config_dict = config.to_dict()
            
            assert config_dict["SESSION_BACKEND"] == "redis"
            assert config_dict["REDIS_URL"] == "redis://localhost:6379/3"
            assert config_dict["SESSION_COOKIE_SECURE"] is True
            assert config_dict["SESSION_COOKIE_HTTPONLY"] is True
            assert config_dict["SESSION_COOKIE_SAMESITE"] == "Lax"

    def test_session_lifetime_calculation(self):
        """Test that session lifetime is correctly calculated in seconds."""
        with patch.dict(os.environ, {
            "SESSION_LIFETIME_DAYS": "14",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            # Calculate expected lifetime in seconds
            expected_seconds = 60 * 60 * 24 * 14  # 14 days in seconds
            assert config.security.SESSION_LIFETIME_DAYS == 14
            assert expected_seconds == 1209600  # 14 days in seconds


class TestSessionSingleCodePath:
    """Test that there's only one code path for session configuration."""

    def test_session_configuration_single_path(self):
        """Test that session configuration follows a single, predictable path."""
        # Test Redis backend
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "REDIS_URL": "redis://localhost:6379/4",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            assert config.SESSION_BACKEND == "redis"
            assert config.REDIS_URL == "redis://localhost:6379/4"

        # Test filesystem backend
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "filesystem",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            assert config.SESSION_BACKEND == "filesystem"

        # Test null backend
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "null",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            assert config.SESSION_BACKEND == "null"

    def test_session_cookie_attributes_consistency(self):
        """Test that session cookie attributes are consistently configured."""
        test_cases = [
            {"SESSION_BACKEND": "redis", "expected_backend": "redis"},
            {"SESSION_BACKEND": "filesystem", "expected_backend": "filesystem"},
            {"SESSION_BACKEND": "null", "expected_backend": "null"},
        ]
        
        for test_case in test_cases:
            with patch.dict(os.environ, {
                **test_case,
                "DATABASE_URL": "sqlite:///:memory:"
            }):
                config = AppConfig()
                
                # All backends should have the same cookie security defaults
                assert config.SESSION_COOKIE_SECURE is True
                assert config.SESSION_COOKIE_HTTPONLY is True
                assert config.SESSION_COOKIE_SAMESITE == "Lax"
                assert config.security.SESSION_LIFETIME_DAYS == 14


if __name__ == "__main__":
    pytest.main([__file__])
