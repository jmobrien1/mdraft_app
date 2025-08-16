"""
Tests for configuration validation functionality.

This module tests the comprehensive configuration validation that ensures
all environment variables are properly validated at startup with clear
error messages and no silent defaults.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.config import AppConfig, ConfigurationError


class TestConfigurationValidation:
    """Test configuration validation functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear any existing environment variables that might interfere
        self.env_vars_to_clear = [
            'FLASK_ENV', 'SECRET_KEY', 'DATABASE_URL', 'GCS_BUCKET_NAME',
            'GCS_PROCESSED_BUCKET_NAME', 'BILLING_ENABLED', 'STRIPE_SECRET_KEY',
            'STRIPE_WEBHOOK_SECRET', 'ANTIVIRUS_MODE', 'SESSION_BACKEND',
            'QUEUE_MODE', 'SESSION_COOKIE_SAMESITE', 'REDIS_URL', 'SENTRY_DSN',
            'MAX_UPLOAD_PDF_MB', 'SESSION_LIFETIME_DAYS', 'PASSWORD_MIN_LENGTH',
            'AUTH_MAX_FAILS', 'AV_TIMEOUT_MS', 'CLAMD_PORT', 'FLASK_DEBUG',
            'SESSION_COOKIE_SECURE', 'PRICING_DOC_OCR_PER_PAGE_USD',
            'ANTIVIRUS_REQUIRED', 'CLAMD_SOCKET', 'CLAMD_HOST', 'AV_HTTP_ENDPOINT'
        ]
        
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
    
    def teardown_method(self):
        """Clean up test environment."""
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
    
    def test_valid_configuration_passes_validation(self):
        """Test that valid configuration passes validation."""
        config = AppConfig()
        # Should not raise any exception
        config.validate()
    
    def test_production_required_secrets(self):
        """Test that production environment requires essential secrets."""
        os.environ['FLASK_ENV'] = 'production'
        
        config = AppConfig()
        
        # Should fail without required secrets
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value)
        assert "SECRET_KEY is required in production" in error_msg
        assert "DATABASE_URL is required in production" in error_msg
        assert "GCS_BUCKET_NAME is required in production" in error_msg
        assert "GCS_PROCESSED_BUCKET_NAME is required in production" in error_msg
    
    def test_production_with_valid_secrets_passes(self):
        """Test that production with valid secrets passes validation."""
        os.environ['FLASK_ENV'] = 'production'
        os.environ['SECRET_KEY'] = 'valid-secret-key-123'
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
        os.environ['GCS_BUCKET_NAME'] = 'valid-bucket-name'
        os.environ['GCS_PROCESSED_BUCKET_NAME'] = 'valid-processed-bucket'
        
        config = AppConfig()
        # Should pass validation
        config.validate()
    
    def test_production_billing_requires_stripe_keys(self):
        """Test that billing enabled in production requires Stripe keys."""
        os.environ['FLASK_ENV'] = 'production'
        os.environ['SECRET_KEY'] = 'valid-secret-key-123'
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
        os.environ['GCS_BUCKET_NAME'] = 'valid-bucket-name'
        os.environ['GCS_PROCESSED_BUCKET_NAME'] = 'valid-processed-bucket'
        os.environ['BILLING_ENABLED'] = '1'
        
        config = AppConfig()
        
        # Should fail without Stripe keys
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value)
        assert "STRIPE_SECRET_KEY is required when billing is enabled" in error_msg
        assert "STRIPE_WEBHOOK_SECRET is required when billing is enabled" in error_msg
    
    def test_file_size_limits_validation(self):
        """Test file size limit validation."""
        # Test PDF size limits
        os.environ['MAX_UPLOAD_PDF_MB'] = '0'  # Too small
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "MAX_UPLOAD_PDF_MB must be between 1 and 100" in str(exc_info.value)
        
        # Test PDF size too large
        os.environ['MAX_UPLOAD_PDF_MB'] = '150'  # Too large
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "MAX_UPLOAD_PDF_MB must be between 1 and 100" in str(exc_info.value)
        
        # Test valid PDF size
        os.environ['MAX_UPLOAD_PDF_MB'] = '50'  # Valid
        config = AppConfig()
        config.validate()  # Should pass
    
    def test_security_timeout_validation(self):
        """Test security timeout validation."""
        # Test session lifetime too short
        os.environ['SESSION_LIFETIME_DAYS'] = '0'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SESSION_LIFETIME_DAYS must be between 1 and 365" in str(exc_info.value)
        
        # Test session lifetime too long
        os.environ['SESSION_LIFETIME_DAYS'] = '400'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SESSION_LIFETIME_DAYS must be between 1 and 365" in str(exc_info.value)
        
        # Test valid session lifetime
        os.environ['SESSION_LIFETIME_DAYS'] = '30'
        config = AppConfig()
        config.validate()  # Should pass
    
    def test_password_policy_validation(self):
        """Test password policy validation."""
        # Test password length too short
        os.environ['PASSWORD_MIN_LENGTH'] = '5'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "PASSWORD_MIN_LENGTH must be between 8 and 128" in str(exc_info.value)
        
        # Test password length too long
        os.environ['PASSWORD_MIN_LENGTH'] = '200'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "PASSWORD_MIN_LENGTH must be between 8 and 128" in str(exc_info.value)
        
        # Test valid password length
        os.environ['PASSWORD_MIN_LENGTH'] = '12'
        config = AppConfig()
        config.validate()  # Should pass
    
    def test_antivirus_mode_validation(self):
        """Test antivirus mode validation."""
        # Test invalid antivirus mode
        os.environ['ANTIVIRUS_MODE'] = 'invalid_mode'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "ANTIVIRUS_MODE must be one of" in str(exc_info.value)
        assert "off" in str(exc_info.value)
        assert "clamd" in str(exc_info.value)
        assert "http" in str(exc_info.value)
        
        # Clear invalid mode
        del os.environ['ANTIVIRUS_MODE']
        
        # Test valid antivirus modes
        for mode in ['off', 'clamd', 'http']:
            os.environ['ANTIVIRUS_MODE'] = mode
            # For http mode, we need to provide an endpoint to avoid cross-field validation
            if mode == 'http':
                os.environ['AV_HTTP_ENDPOINT'] = 'http://example.com/scan'
            elif mode == 'clamd':
                os.environ['CLAMD_HOST'] = 'localhost'
            
            config = AppConfig()
            config.validate()  # Should pass
            
            # Clean up
            if mode == 'http':
                del os.environ['AV_HTTP_ENDPOINT']
            elif mode == 'clamd':
                del os.environ['CLAMD_HOST']
            del os.environ['ANTIVIRUS_MODE']
    
    def test_session_backend_validation(self):
        """Test session backend validation."""
        # Test invalid session backend
        os.environ['SESSION_BACKEND'] = 'invalid_backend'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SESSION_BACKEND must be one of" in str(exc_info.value)
        assert "redis" in str(exc_info.value)
        assert "filesystem" in str(exc_info.value)
        assert "null" in str(exc_info.value)
        
        # Test valid session backends
        for backend in ['redis', 'filesystem', 'null']:
            os.environ['SESSION_BACKEND'] = backend
            config = AppConfig()
            config.validate()  # Should pass
    
    def test_queue_mode_validation(self):
        """Test queue mode validation."""
        # Test invalid queue mode
        os.environ['QUEUE_MODE'] = 'invalid_mode'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "QUEUE_MODE must be one of" in str(exc_info.value)
        assert "celery" in str(exc_info.value)
        assert "cloud_tasks" in str(exc_info.value)
        assert "sync" in str(exc_info.value)
        
        # Test valid queue modes
        for mode in ['celery', 'cloud_tasks', 'sync']:
            os.environ['QUEUE_MODE'] = mode
            config = AppConfig()
            config.validate()  # Should pass
    
    def test_session_cookie_samesite_validation(self):
        """Test session cookie SameSite validation."""
        # Test invalid SameSite value
        os.environ['SESSION_COOKIE_SAMESITE'] = 'Invalid'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SESSION_COOKIE_SAMESITE must be one of" in str(exc_info.value)
        assert "Lax" in str(exc_info.value)
        assert "Strict" in str(exc_info.value)
        assert "None" in str(exc_info.value)
        
        # Test valid SameSite values
        for samesite in ['Lax', 'Strict', 'None']:
            os.environ['SESSION_COOKIE_SAMESITE'] = samesite
            config = AppConfig()
            config.validate()  # Should pass
    
    def test_url_format_validation(self):
        """Test URL format validation."""
        # Test invalid database URL
        os.environ['DATABASE_URL'] = 'invalid-url'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "DATABASE_URL must be a valid URL" in str(exc_info.value)
        
        # Test valid database URL
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
        config = AppConfig()
        config.validate()  # Should pass
        
        # Test invalid Redis URL
        os.environ['SESSION_BACKEND'] = 'redis'
        os.environ['REDIS_URL'] = 'http://localhost:6379'  # Wrong scheme
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "REDIS_URL must use 'redis://' scheme" in str(exc_info.value)
        
        # Test valid Redis URL
        os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
        config = AppConfig()
        config.validate()  # Should pass
    
    def test_gcs_bucket_name_validation(self):
        """Test GCS bucket name validation."""
        # Test invalid bucket name (uppercase)
        os.environ['GCS_BUCKET_NAME'] = 'Invalid-Bucket-Name'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "GCS_BUCKET_NAME must be a valid GCS bucket name" in str(exc_info.value)
        
        # Test invalid bucket name (starts with dash)
        os.environ['GCS_BUCKET_NAME'] = '-invalid-bucket'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "GCS_BUCKET_NAME must be a valid GCS bucket name" in str(exc_info.value)
        
        # Test valid bucket name
        os.environ['GCS_BUCKET_NAME'] = 'valid-bucket-name-123'
        config = AppConfig()
        config.validate()  # Should pass
    
    def test_boolean_parsing_validation(self):
        """Test boolean parsing validation."""
        # Test invalid boolean values
        invalid_booleans = [
            ('BILLING_ENABLED', 'maybe'),
            ('PASSWORD_REQUIRE_UPPERCASE', 'invalid'),
            ('FLASK_DEBUG', 'maybe'),
        ]
        
        for env_var, value in invalid_booleans:
            os.environ[env_var] = value
            config = AppConfig()
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert f"{env_var} must be a valid boolean value" in str(exc_info.value)
            # Clean up
            del os.environ[env_var]
        
        # Test valid boolean values
        valid_booleans = [
            ('BILLING_ENABLED', '1'),
            ('PASSWORD_REQUIRE_UPPERCASE', 'true'),
            ('FLASK_DEBUG', '0'),
            ('SESSION_COOKIE_SECURE', 'false'),
        ]
        
        for env_var, value in valid_booleans:
            os.environ[env_var] = value
            config = AppConfig()
            config.validate()  # Should pass
            # Clean up
            del os.environ[env_var]
    
    def test_cross_field_validation(self):
        """Test cross-field validation rules."""
        # Test antivirus required but mode is off
        os.environ['ANTIVIRUS_REQUIRED'] = 'true'
        os.environ['ANTIVIRUS_MODE'] = 'off'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "ANTIVIRUS_REQUIRED cannot be true when ANTIVIRUS_MODE is 'off'" in str(exc_info.value)
        
        # Clear environment for next test
        del os.environ['ANTIVIRUS_REQUIRED']
        del os.environ['ANTIVIRUS_MODE']
        
        # Test antivirus clamd mode without socket or host
        os.environ['ANTIVIRUS_MODE'] = 'clamd'
        os.environ['CLAMD_SOCKET'] = ''
        os.environ['CLAMD_HOST'] = ''
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "CLAMD_SOCKET or CLAMD_HOST must be provided when ANTIVIRUS_MODE is 'clamd'" in str(exc_info.value)
        
        # Clear environment for next test
        del os.environ['ANTIVIRUS_MODE']
        del os.environ['CLAMD_SOCKET']
        del os.environ['CLAMD_HOST']
        
        # Test antivirus http mode without endpoint
        os.environ['ANTIVIRUS_MODE'] = 'http'
        os.environ['AV_HTTP_ENDPOINT'] = ''
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "AV_HTTP_ENDPOINT must be provided when ANTIVIRUS_MODE is 'http'" in str(exc_info.value)
        
        # Clear environment for next test
        del os.environ['ANTIVIRUS_MODE']
        del os.environ['AV_HTTP_ENDPOINT']
        
        # Test billing enabled with invalid price
        os.environ['BILLING_ENABLED'] = '1'
        os.environ['PRICING_DOC_OCR_PER_PAGE_USD'] = 'not-a-number'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "PRICING_DOC_OCR_PER_PAGE_USD must be a valid decimal number" in str(exc_info.value)
        
        # Clear environment for next test
        del os.environ['BILLING_ENABLED']
        del os.environ['PRICING_DOC_OCR_PER_PAGE_USD']
        
        # Test negative price
        os.environ['BILLING_ENABLED'] = '1'
        os.environ['PRICING_DOC_OCR_PER_PAGE_USD'] = '-0.01'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "PRICING_DOC_OCR_PER_PAGE_USD must be non-negative" in str(exc_info.value)
        
        # Clear environment for next test
        del os.environ['BILLING_ENABLED']
        del os.environ['PRICING_DOC_OCR_PER_PAGE_USD']
        
        # Test SameSite None without Secure
        os.environ['SESSION_COOKIE_SAMESITE'] = 'None'
        os.environ['SESSION_COOKIE_SECURE'] = 'false'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SESSION_COOKIE_SECURE must be true when SESSION_COOKIE_SAMESITE is 'None'" in str(exc_info.value)
    
    def test_production_specific_validation(self):
        """Test production-specific validation rules."""
        # Set up valid production environment
        os.environ['FLASK_ENV'] = 'production'
        os.environ['SECRET_KEY'] = 'valid-secret-key-123'
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
        os.environ['GCS_BUCKET_NAME'] = 'valid-bucket-name'
        os.environ['GCS_PROCESSED_BUCKET_NAME'] = 'valid-processed-bucket'
        
        # Test debug mode in production
        os.environ['FLASK_DEBUG'] = '1'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "FLASK_DEBUG must be false in production" in str(exc_info.value)
        
        # Clear debug flag for next test
        del os.environ['FLASK_DEBUG']
        
        # Test non-secure cookies in production
        os.environ['SESSION_COOKIE_SECURE'] = 'false'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SESSION_COOKIE_SECURE must be true in production" in str(exc_info.value)
        
        # Clear secure flag for next test
        del os.environ['SESSION_COOKIE_SECURE']
        
        # Test default secret key in production
        os.environ['SECRET_KEY'] = 'changeme'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SECRET_KEY must not be 'changeme' in production" in str(exc_info.value)
        
        # Clean up
        del os.environ['FLASK_ENV']
        del os.environ['SECRET_KEY']
        del os.environ['DATABASE_URL']
        del os.environ['GCS_BUCKET_NAME']
        del os.environ['GCS_PROCESSED_BUCKET_NAME']
    
    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are reported together."""
        os.environ['FLASK_ENV'] = 'production'
        os.environ['MAX_UPLOAD_PDF_MB'] = '150'  # Too large
        os.environ['ANTIVIRUS_MODE'] = 'invalid_mode'
        os.environ['SESSION_COOKIE_SAMESITE'] = 'Invalid'
        
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value)
        assert "SECRET_KEY is required in production" in error_msg
        assert "MAX_UPLOAD_PDF_MB must be between 1 and 100" in error_msg
        assert "ANTIVIRUS_MODE must be one of" in error_msg
        assert "SESSION_COOKIE_SAMESITE must be one of" in error_msg
    
    def test_development_environment_validation(self):
        """Test that development environment has relaxed validation."""
        os.environ['FLASK_ENV'] = 'development'
        os.environ['FLASK_DEBUG'] = 'true'
        os.environ['SESSION_COOKIE_SECURE'] = 'false'
        os.environ['SECRET_KEY'] = 'changeme'
        
        config = AppConfig()
        # Should pass validation in development
        config.validate()
    
    def test_integer_range_validation_edge_cases(self):
        """Test integer range validation edge cases."""
        # Test auth rate limiting ranges
        os.environ['AUTH_MAX_FAILS'] = '0'  # Too small
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "AUTH_MAX_FAILS must be between 1 and 20" in str(exc_info.value)
        
        os.environ['AUTH_MAX_FAILS'] = '25'  # Too large
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "AUTH_MAX_FAILS must be between 1 and 20" in str(exc_info.value)
        
        # Test valid auth max fails
        os.environ['AUTH_MAX_FAILS'] = '10'
        config = AppConfig()
        config.validate()  # Should pass
        
        # Test ClamAV port range
        os.environ['CLAMD_PORT'] = '0'  # Too small
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "CLAMD_PORT must be between 1 and 65535" in str(exc_info.value)
        
        os.environ['CLAMD_PORT'] = '70000'  # Too large
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "CLAMD_PORT must be between 1 and 65535" in str(exc_info.value)
        
        # Test valid ClamAV port
        os.environ['CLAMD_PORT'] = '3310'
        config = AppConfig()
        config.validate()  # Should pass
    
    def test_sentry_dsn_validation(self):
        """Test Sentry DSN validation."""
        # Test invalid Sentry DSN
        os.environ['SENTRY_DSN'] = 'invalid-dsn'
        config = AppConfig()
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        assert "SENTRY_DSN must be a valid URL" in str(exc_info.value)
        
        # Test valid Sentry DSN
        os.environ['SENTRY_DSN'] = 'https://sentry.io/project'
        config = AppConfig()
        config.validate()  # Should pass
        
        # Test empty Sentry DSN (should be allowed)
        os.environ['SENTRY_DSN'] = ''
        config = AppConfig()
        config.validate()  # Should pass


class TestConfigurationError:
    """Test the ConfigurationError exception."""
    
    def test_configuration_error_message_format(self):
        """Test that ConfigurationError provides clear, actionable messages."""
        error = ConfigurationError("Test error message")
        assert str(error) == "Test error message"
        
        # Test with multiple errors
        errors = [
            "SECRET_KEY is required in production",
            "DATABASE_URL is required in production",
            "GCS_BUCKET_NAME is required in production"
        ]
        error = ConfigurationError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
        assert "Configuration validation failed:" in str(error)
        assert "  - SECRET_KEY is required in production" in str(error)
        assert "  - DATABASE_URL is required in production" in str(error)
        assert "  - GCS_BUCKET_NAME is required in production" in str(error)
