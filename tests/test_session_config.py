"""
Tests for Flask-Session configuration with Redis.

This module tests:
- Redis client creation from SESSION_REDIS_URL and REDIS_URL
- Production validation (no localhost fallback)
- Session initialization with proper Redis client
- Error handling for missing Redis URLs
- RuntimeWarning prevention during app initialization
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse

from flask import Flask
from flask_session import Session

from app.config import AppConfig, ConfigurationError


class TestSessionRedisConfiguration:
    """Test Redis session configuration and client creation."""

    @pytest.mark.parametrize("session_redis_url,redis_url,expected_url", [
        # SESSION_REDIS_URL takes precedence
        ("redis://upstash-redis:6379/1", "redis://localhost:6379/0", "redis://upstash-redis:6379/1"),
        ("rediss://upstash-redis:6379/1", "redis://localhost:6379/0", "rediss://upstash-redis:6379/1"),
        # Fallback to REDIS_URL when SESSION_REDIS_URL not set
        (None, "redis://upstash-redis:6379/2", "redis://upstash-redis:6379/2"),
        (None, "rediss://upstash-redis:6379/2", "rediss://upstash-redis:6379/2"),
    ])
    def test_session_redis_url_precedence(self, session_redis_url, redis_url, expected_url):
        """Test that SESSION_REDIS_URL takes precedence over REDIS_URL."""
        env_vars = {
            "SESSION_BACKEND": "redis",
            "DATABASE_URL": "sqlite:///:memory:"
        }
        
        if session_redis_url:
            env_vars["SESSION_REDIS_URL"] = session_redis_url
        if redis_url:
            env_vars["REDIS_URL"] = redis_url
            
        with patch.dict(os.environ, env_vars):
            config = AppConfig()
            assert config.SESSION_REDIS_URL_FINAL == expected_url

    def test_redis_client_creation(self):
        """Test Redis client creation from URL."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://upstash-redis:6379/1",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            # Mock redis module
            with patch('builtins.__import__') as mock_import:
                mock_redis = MagicMock()
                mock_client = MagicMock()
                mock_redis.from_url.return_value = mock_client
                mock_import.return_value = mock_redis
                
                redis_client = config.create_session_redis_client()
                
                # Verify redis.from_url was called with correct parameters
                mock_redis.from_url.assert_called_once_with(
                    "redis://upstash-redis:6379/1",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                assert redis_client == mock_client

    def test_redis_client_creation_no_url(self):
        """Test Redis client creation fails when no URL is available."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            with pytest.raises(ConfigurationError, match="No Redis URL available for session storage"):
                config.create_session_redis_client()

    def test_redis_client_creation_import_error(self):
        """Test Redis client creation fails when redis package is not available."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://upstash-redis:6379/1",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            with patch('builtins.__import__', side_effect=ImportError("No module named 'redis'")):
                with pytest.raises(ConfigurationError, match="redis package is required for Redis session backend"):
                    config.create_session_redis_client()

    @pytest.mark.parametrize("redis_url,is_production,should_fail", [
        # Production validation
        ("redis://localhost:6379/0", True, True),
        ("redis://127.0.0.1:6379/0", True, True),
        ("redis://upstash-redis:6379/1", True, False),
        ("rediss://upstash-redis:6379/1", True, False),
        # Development allows localhost
        ("redis://localhost:6379/0", False, False),
        ("redis://127.0.0.1:6379/0", False, False),
    ])
    def test_production_localhost_validation(self, redis_url, is_production, should_fail):
        """Test that localhost Redis URLs are rejected in production."""
        env_vars = {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": redis_url,
            "DATABASE_URL": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }
        
        if is_production:
            env_vars["FLASK_ENV"] = "production"
            
        with patch.dict(os.environ, env_vars):
            config = AppConfig()
            
            if should_fail:
                with pytest.raises(ConfigurationError, match="cannot point to localhost in production"):
                    config.validate()
            else:
                # Should not raise an error
                config.validate()

    @pytest.mark.parametrize("redis_url,is_production,should_fail", [
        # Missing Redis URL in production
        (None, True, True),
        # Missing Redis URL in development
        (None, False, True),
        # Valid Redis URL
        ("redis://upstash-redis:6379/1", True, False),
        ("rediss://upstash-redis:6379/1", True, False),
    ])
    def test_redis_url_required_validation(self, redis_url, is_production, should_fail):
        """Test that Redis URL is required when SESSION_BACKEND is redis."""
        env_vars = {
            "SESSION_BACKEND": "redis",
            "DATABASE_URL": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }
        
        if redis_url:
            env_vars["SESSION_REDIS_URL"] = redis_url
            
        if is_production:
            env_vars["FLASK_ENV"] = "production"
            
        with patch.dict(os.environ, env_vars):
            config = AppConfig()
            
            if should_fail:
                with pytest.raises(ConfigurationError, match="requires SESSION_REDIS_URL or REDIS_URL"):
                    config.validate()
            else:
                # Should not raise an error
                config.validate()

    @pytest.mark.parametrize("redis_url,expected_scheme", [
        ("redis://upstash-redis:6379/1", "redis"),
        ("rediss://upstash-redis:6379/1", "rediss"),
    ])
    def test_redis_url_scheme_validation(self, redis_url, expected_scheme):
        """Test that Redis URLs use valid schemes."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": redis_url,
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            parsed = urlparse(config.SESSION_REDIS_URL_FINAL)
            assert parsed.scheme == expected_scheme

    def test_invalid_redis_url_scheme(self):
        """Test that invalid Redis URL schemes are rejected."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "http://upstash-redis:6379/1",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            config = AppConfig()
            
            with pytest.raises(ConfigurationError, match="must use 'redis://' or 'rediss://' scheme"):
                config.validate()


class TestFlaskSessionInitialization:
    """Test Flask-Session initialization with Redis client."""

    def test_session_initialization_with_redis_client(self):
        """Test that Flask-Session is initialized with a Redis client."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://upstash-redis:6379/1",
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Mock redis module more specifically
            with patch('app.config.redis') as mock_redis:
                mock_client = MagicMock()
                mock_redis.from_url.return_value = mock_client
                
                # Create Flask app
                from app import create_app
                app = create_app()
                
                # Verify SESSION_REDIS is set to a Redis client
                assert app.config["SESSION_TYPE"] == "redis"
                assert app.config["SESSION_REDIS"] == mock_client
                assert not isinstance(app.config["SESSION_REDIS"], str)

    def test_session_initialization_without_redis_url(self):
        """Test that Flask-Session falls back to filesystem when no Redis URL is available."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Create Flask app
            from app import create_app
            app = create_app()
            
            # Should fall back to filesystem
            assert app.config["SESSION_TYPE"] == "filesystem"

    def test_session_initialization_production_failure(self):
        """Test that production fails when Redis initialization fails."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://invalid-host:6379/1",
            "SECRET_KEY": "test-secret",
            "FLASK_ENV": "production",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Mock redis module to raise an exception
            with patch('app.config.redis') as mock_redis:
                mock_redis.from_url.side_effect = Exception("Connection failed")
                
                # Create Flask app should fail in production
                from app import create_app
                with pytest.raises(RuntimeError, match="Redis session backend initialization failed"):
                    create_app()

    def test_session_initialization_development_fallback(self):
        """Test that development falls back to filesystem when Redis fails."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://invalid-host:6379/1",
            "SECRET_KEY": "test-secret",
            "FLASK_ENV": "development",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Mock redis module to raise an exception
            with patch('app.config.redis') as mock_redis:
                mock_redis.from_url.side_effect = Exception("Connection failed")
                
                # Create Flask app should fall back to filesystem in development
                from app import create_app
                app = create_app()
                
                assert app.config["SESSION_TYPE"] == "filesystem"

    def test_no_runtime_warning_during_initialization(self):
        """Test that no RuntimeWarning is emitted during Flask-Session initialization."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://upstash-redis:6379/1",
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Mock redis module
            with patch('app.config.redis') as mock_redis:
                mock_client = MagicMock()
                mock_redis.from_url.return_value = mock_client
                
                # Capture warnings
                import warnings
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    
                    # Create Flask app
                    from app import create_app
                    app = create_app()
                    
                    # Check that no RuntimeWarning was emitted
                    runtime_warnings = [warning for warning in w if warning.category == RuntimeWarning]
                    assert len(runtime_warnings) == 0, f"RuntimeWarning emitted: {runtime_warnings}"


class TestSessionConfigurationIntegration:
    """Integration tests for session configuration."""

    def test_session_configuration_with_session_redis_url(self):
        """Test complete session configuration with SESSION_REDIS_URL."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "SESSION_REDIS_URL": "redis://upstash-redis:6379/1",
            "SESSION_TYPE": "redis",
            "SESSION_USE_SIGNER": "true",
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Mock redis module
            with patch('app.config.redis') as mock_redis:
                mock_client = MagicMock()
                mock_redis.from_url.return_value = mock_client
                
                # Create Flask app
                from app import create_app
                app = create_app()
                
                # Verify session configuration
                assert app.config["SESSION_TYPE"] == "redis"
                assert app.config["SESSION_REDIS"] == mock_client
                assert app.config["SESSION_COOKIE_SECURE"] is True
                assert app.config["SESSION_COOKIE_HTTPONLY"] is True
                assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
                assert app.config["PERMANENT_SESSION_LIFETIME"].days == 14

    def test_session_configuration_with_redis_url_fallback(self):
        """Test complete session configuration with REDIS_URL fallback."""
        with patch.dict(os.environ, {
            "SESSION_BACKEND": "redis",
            "REDIS_URL": "redis://upstash-redis:6379/2",
            "SESSION_TYPE": "redis",
            "SESSION_USE_SIGNER": "true",
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "GCS_BUCKET_NAME": "test-bucket",
            "GCS_PROCESSED_BUCKET_NAME": "test-processed-bucket"
        }):
            # Mock redis module
            with patch('app.config.redis') as mock_redis:
                mock_client = MagicMock()
                mock_redis.from_url.return_value = mock_client
                
                # Create Flask app
                from app import create_app
                app = create_app()
                
                # Verify session configuration
                assert app.config["SESSION_TYPE"] == "redis"
                assert app.config["SESSION_REDIS"] == mock_client
                assert not isinstance(app.config["SESSION_REDIS"], str)
