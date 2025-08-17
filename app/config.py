"""
Centralized configuration for mdraft application.

This module centralizes all configuration values including magic numbers,
rate limits, file size limits, and other application settings. All values
can be overridden via environment variables for deployment flexibility.
"""

import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class FileSizeLimits:
    """File size limits in bytes for different file categories."""
    PDF_MB: int = 25
    OFFICE_MB: int = 20
    TEXT_MB: int = 5
    BINARY_MB: int = 10  # Fallback for unknown types
    
    @property
    def PDF_BYTES(self) -> int:
        return self.PDF_MB * 1024 * 1024
    
    @property
    def OFFICE_BYTES(self) -> int:
        return self.OFFICE_MB * 1024 * 1024
    
    @property
    def TEXT_BYTES(self) -> int:
        return self.TEXT_MB * 1024 * 1024
    
    @property
    def BINARY_BYTES(self) -> int:
        return self.BINARY_MB * 1024 * 1024


@dataclass
class RateLimits:
    """Rate limiting configuration."""
    GLOBAL_PER_MINUTE: str = "120 per minute"
    CONVERT_PER_MINUTE: str = "20 per minute"
    AI_PER_MINUTE: str = "10 per minute"
    ANON_PER_MINUTE: str = "20"
    ANON_PER_DAY: str = "200"
    INDEX_PER_MINUTE: str = "50 per minute"
    LOGIN_PER_MINUTE: str = "10 per minute"
    UPLOAD_PER_MINUTE: str = "20 per minute"
    UPLOAD_ANON_PER_MINUTE: str = "10 per minute"


@dataclass
class BillingConfig:
    """Billing and pricing configuration."""
    ENABLED: bool = False
    PRICE_PER_PAGE_USD: str = "0.0000"
    STRIPE_PRICE_PRO: Optional[str] = None


@dataclass
class SecurityConfig:
    """Security-related configuration."""
    SESSION_LIFETIME_DAYS: int = 14
    CSRF_TIMEOUT_HOURS: int = 1
    ANON_PROPOSAL_TTL_DAYS: int = 14
    
    # Password policy configuration
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGITS: bool = True
    PASSWORD_REQUIRE_SYMBOLS: bool = True
    PASSWORD_MIN_CHARACTER_CLASSES: int = 3  # At least 3 of the 4 character classes
    
    # Authentication rate limiting and lockout
    AUTH_MAX_FAILS: int = 5  # Maximum failed attempts before lockout
    AUTH_FAIL_WINDOW_SEC: int = 900  # 15 minutes window for counting failures
    AUTH_LOCKOUT_MINUTES: int = 30  # Lockout duration in minutes
    
    # Session management
    AUTH_SINGLE_SESSION: bool = True  # Invalidate other sessions on login
    
    # Email verification
    EMAIL_VERIFICATION_REQUIRED: bool = False  # Whether email verification is required
    EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS: int = 24  # Token expiry time


@dataclass
class CSPConfig:
    """Content Security Policy configuration."""
    # Default source - controls default behavior for all resource types
    DEFAULT_SRC: str = "'self'"
    
    # Script sources - controls JavaScript execution
    SCRIPT_SRC: str = "'self'"
    
    # Style sources - controls CSS loading
    STYLE_SRC: str = "'self' 'unsafe-inline'"
    
    # Image sources - controls image loading
    IMG_SRC: str = "'self' data:"
    
    # Connect sources - controls AJAX, WebSocket, EventSource
    CONNECT_SRC: str = "'self' https:"
    
    # Frame ancestors - controls embedding in iframes
    FRAME_ANCESTORS: str = "'none'"
    
    # Report URI - for CSP violation reporting (optional)
    REPORT_URI: Optional[str] = None
    
    # Object source - controls plugin content
    OBJECT_SRC: str = "'none'"
    
    # Base URI - controls base tag behavior
    BASE_URI: str = "'self'"
    
    # Upgrade insecure requests - automatically upgrade HTTP to HTTPS
    UPGRADE_INSECURE_REQUESTS: bool = True
    
    def build_policy(self) -> str:
        """Build the complete CSP policy string."""
        directives = [
            f"default-src {self.DEFAULT_SRC}",
            f"object-src {self.OBJECT_SRC}",
            f"base-uri {self.BASE_URI}",
            f"frame-ancestors {self.FRAME_ANCESTORS}",
            f"img-src {self.IMG_SRC}",
            f"style-src {self.STYLE_SRC}",
            f"script-src {self.SCRIPT_SRC}",
            f"connect-src {self.CONNECT_SRC}",
        ]
        
        if self.UPGRADE_INSECURE_REQUESTS:
            directives.append("upgrade-insecure-requests")
        
        if self.REPORT_URI:
            directives.append(f"report-uri {self.REPORT_URI}")
        
        return "; ".join(directives)


@dataclass
class AntivirusConfig:
    """Antivirus scanning configuration."""
    MODE: str = "off"  # off, clamd, http
    CLAMD_SOCKET: Optional[str] = None  # Unix socket path
    CLAMD_HOST: str = "localhost"
    CLAMD_PORT: int = 3310
    AV_HTTP_ENDPOINT: Optional[str] = None
    AV_TIMEOUT_MS: int = 30000  # 30 seconds
    AV_REQUIRED: bool = False  # Fail closed on scanner errors


@dataclass
class ReliabilityConfig:
    """Reliability engineering configuration for external calls."""
    HTTP_TIMEOUT_SEC: int = 30  # Default timeout for HTTP calls
    HTTP_RETRIES: int = 3  # Number of retries for transient failures
    HTTP_BACKOFF_BASE_MS: int = 1000  # Base backoff in milliseconds
    CB_FAIL_THRESHOLD: int = 5  # Circuit breaker failure threshold
    CB_RESET_SEC: int = 60  # Circuit breaker reset timeout in seconds


@dataclass
class AppConfig:
    """Main application configuration."""
    
    def __init__(self):
        # File size limits
        self.file_sizes = FileSizeLimits(
            PDF_MB=int(os.getenv("MAX_UPLOAD_PDF_MB", "25")),
            OFFICE_MB=int(os.getenv("MAX_UPLOAD_OFFICE_MB", "20")),
            TEXT_MB=int(os.getenv("MAX_UPLOAD_TEXT_MB", "5")),
            BINARY_MB=int(os.getenv("MAX_UPLOAD_BINARY_MB", "10"))
        )
        
        # Rate limits
        self.rate_limits = RateLimits(
            GLOBAL_PER_MINUTE=os.getenv("GLOBAL_RATE_LIMIT", "120 per minute"),
            CONVERT_PER_MINUTE=os.getenv("CONVERT_RATE_LIMIT_DEFAULT", "20 per minute"),
            AI_PER_MINUTE=os.getenv("AI_RATE_LIMIT_DEFAULT", "10 per minute"),
            ANON_PER_MINUTE=os.getenv("ANON_RATE_LIMIT_PER_MINUTE", "20"),
            ANON_PER_DAY=os.getenv("ANON_RATE_LIMIT_PER_DAY", "200"),
            INDEX_PER_MINUTE=os.getenv("INDEX_RATE_LIMIT", "50 per minute"),
            LOGIN_PER_MINUTE=os.getenv("LOGIN_RATE_LIMIT", "10 per minute"),
            UPLOAD_PER_MINUTE=os.getenv("UPLOAD_RATE_LIMIT", "20 per minute"),
            UPLOAD_ANON_PER_MINUTE=os.getenv("UPLOAD_ANON_RATE_LIMIT", "10 per minute")
        )
        
        # Billing configuration
        self.billing = BillingConfig(
            ENABLED=os.getenv("BILLING_ENABLED", "0") == "1",
            PRICE_PER_PAGE_USD=os.getenv("PRICING_DOC_OCR_PER_PAGE_USD", "0.0000"),
            STRIPE_PRICE_PRO=os.getenv("STRIPE_PRICE_PRO")
        )
        
        # Security configuration
        self.security = SecurityConfig(
            SESSION_LIFETIME_DAYS=int(os.getenv("SESSION_LIFETIME_DAYS", "14")),
            CSRF_TIMEOUT_HOURS=int(os.getenv("CSRF_TIMEOUT_HOURS", "1")),
            ANON_PROPOSAL_TTL_DAYS=int(os.getenv("ANON_PROPOSAL_TTL_DAYS", "14")),
            PASSWORD_MIN_LENGTH=int(os.getenv("PASSWORD_MIN_LENGTH", "12")),
            PASSWORD_REQUIRE_UPPERCASE=os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true",
            PASSWORD_REQUIRE_LOWERCASE=os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true",
            PASSWORD_REQUIRE_DIGITS=os.getenv("PASSWORD_REQUIRE_DIGITS", "true").lower() == "true",
            PASSWORD_REQUIRE_SYMBOLS=os.getenv("PASSWORD_REQUIRE_SYMBOLS", "true").lower() == "true",
            PASSWORD_MIN_CHARACTER_CLASSES=int(os.getenv("PASSWORD_MIN_CHARACTER_CLASSES", "3")),
            AUTH_MAX_FAILS=int(os.getenv("AUTH_MAX_FAILS", "5")),
            AUTH_FAIL_WINDOW_SEC=int(os.getenv("AUTH_FAIL_WINDOW_SEC", "900")),
            AUTH_LOCKOUT_MINUTES=int(os.getenv("AUTH_LOCKOUT_MINUTES", "30")),
            AUTH_SINGLE_SESSION=os.getenv("AUTH_SINGLE_SESSION", "true").lower() == "true",
            EMAIL_VERIFICATION_REQUIRED=os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").lower() == "true",
            EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS=int(os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS", "24"))
        )
        
        # CSP configuration
        self.csp = CSPConfig(
            DEFAULT_SRC=os.getenv("CSP_DEFAULT_SRC", "'self'"),
            SCRIPT_SRC=os.getenv("CSP_SCRIPT_SRC", "'self'"),
            STYLE_SRC=os.getenv("CSP_STYLE_SRC", "'self' 'unsafe-inline'"),
            IMG_SRC=os.getenv("CSP_IMG_SRC", "'self' data:"),
            CONNECT_SRC=os.getenv("CSP_CONNECT_SRC", "'self' https:"),
            FRAME_ANCESTORS=os.getenv("CSP_FRAME_ANCESTORS", "'none'"),
            REPORT_URI=os.getenv("CSP_REPORT_URI"),
            OBJECT_SRC=os.getenv("CSP_OBJECT_SRC", "'none'"),
            BASE_URI=os.getenv("CSP_BASE_URI", "'self'"),
            UPGRADE_INSECURE_REQUESTS=os.getenv("CSP_UPGRADE_INSECURE_REQUESTS", "true").lower() == "true"
        )
        
        # Antivirus configuration
        self.antivirus = AntivirusConfig(
            MODE=os.getenv("ANTIVIRUS_MODE", "off").lower(),
            CLAMD_SOCKET=os.getenv("CLAMD_SOCKET"),
            CLAMD_HOST=os.getenv("CLAMD_HOST", "localhost"),
            CLAMD_PORT=int(os.getenv("CLAMD_PORT", "3310")),
            AV_HTTP_ENDPOINT=os.getenv("AV_HTTP_ENDPOINT"),
            AV_TIMEOUT_MS=int(os.getenv("AV_TIMEOUT_MS", "30000")),
            AV_REQUIRED=os.getenv("ANTIVIRUS_REQUIRED", "false").lower() == "true"
        )
        
        # Reliability configuration
        self.reliability = ReliabilityConfig(
            HTTP_TIMEOUT_SEC=int(os.getenv("HTTP_TIMEOUT_SEC", "30")),
            HTTP_RETRIES=int(os.getenv("HTTP_RETRIES", "3")),
            HTTP_BACKOFF_BASE_MS=int(os.getenv("HTTP_BACKOFF_BASE_MS", "1000")),
            CB_FAIL_THRESHOLD=int(os.getenv("CB_FAIL_THRESHOLD", "5")),
            CB_RESET_SEC=int(os.getenv("CB_RESET_SEC", "60"))
        )
        
        # Flask configuration
        self.FLASK_SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
        self.FLASK_MAX_CONTENT_LENGTH = self.file_sizes.PDF_BYTES  # Use largest limit as hard cap
        
        # Database configuration
        self.DATABASE_URL = os.getenv("DATABASE_URL", "")
        
        # Google Cloud Storage configuration
        self.GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
        self.GCS_PROCESSED_BUCKET_NAME = os.getenv("GCS_PROCESSED_BUCKET_NAME")
        
        # Google Cloud Tasks configuration
        self.CLOUD_TASKS_QUEUE_ID = os.getenv("CLOUD_TASKS_QUEUE_ID")
        self.CLOUD_TASKS_LOCATION = os.getenv("CLOUD_TASKS_LOCATION", "us-central1")
        
        # Celery configuration
        self.CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
        self.CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
        self.QUEUE_MODE = os.getenv("QUEUE_MODE", "celery")
        
        # Document AI configuration
        self.DOCAI_PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")
        self.DOCAI_LOCATION = os.getenv("DOCAI_LOCATION", "us")
        
        # Authentication configuration
        self.FREE_TOOLS_REQUIRE_AUTH = os.getenv("FREE_TOOLS_REQUIRE_AUTH", "false").lower() == "true"
        self.LOGIN_DISABLED = os.getenv("LOGIN_DISABLED", "false").lower() == "true"
        self.MDRAFT_PUBLIC_MODE = os.getenv("MDRAFT_PUBLIC_MODE", "0") == "1"
        
        # Session configuration
        # Default to Redis in production, filesystem in development
        default_session_backend = "redis" if os.getenv("FLASK_ENV") == "production" else "filesystem"
        self.SESSION_BACKEND = os.getenv("SESSION_BACKEND", default_session_backend).lower()
        
        # Redis URL configuration - SESSION_REDIS_URL takes precedence for sessions
        self.SESSION_REDIS_URL = os.getenv("SESSION_REDIS_URL")
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Use SESSION_REDIS_URL for sessions if available, otherwise fall back to REDIS_URL
        self.SESSION_REDIS_URL_FINAL = self.SESSION_REDIS_URL or self.REDIS_URL
        
        # Session cookie configuration
        self.SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
        self.SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
        self.SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
        
        # Rate limiting storage
        self.FLASK_LIMITER_STORAGE_URI = os.getenv("FLASK_LIMITER_STORAGE_URI")
        self.RATE_ALLOWLIST = os.getenv("RATE_ALLOWLIST", "")
        
        # Stripe configuration
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        # Sentry configuration
        self.SENTRY_DSN = os.getenv("SENTRY_DSN")
        self.SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "production")
        self.SENTRY_RELEASE = os.getenv("SENTRY_RELEASE")
        
        # Development configuration
        self.FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
        self.MDRAFT_DEV_STUB = os.getenv("MDRAFT_DEV_STUB", "").strip()
        
        # Allowlist configuration
        self.ALLOWLIST = os.getenv("ALLOWLIST", "")
        
        # OpenAI configuration (secret)
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Admin configuration (secret)
        self.ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
        
        # Webhook configuration (secret)
        self.WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
    
    def validate(self) -> None:
        """
        Validate configuration and fail fast with clear error messages.
        
        Raises:
            ConfigurationError: If any configuration validation fails
        """
        errors = []
        
        # Check if we're in production mode
        is_production = os.getenv("FLASK_ENV") == "production"
        
        # 1. Required secrets for production
        if is_production:
            if not self.FLASK_SECRET_KEY or self.FLASK_SECRET_KEY == "changeme":
                errors.append("SECRET_KEY is required in production and must not be 'changeme'")
            
            if not self.DATABASE_URL:
                errors.append("DATABASE_URL is required in production")
            
            if not self.GCS_BUCKET_NAME:
                errors.append("GCS_BUCKET_NAME is required in production. Set this environment variable to your GCS bucket name for uploaded files (e.g., 'mdraft-uploads-1974')")
            
            if not self.GCS_PROCESSED_BUCKET_NAME:
                errors.append("GCS_PROCESSED_BUCKET_NAME is required in production. Set this environment variable to your GCS bucket name for processed files (e.g., 'mdraft-processed-1974' or use the same bucket as GCS_BUCKET_NAME)")
            
            if self.billing.ENABLED:
                if not self.STRIPE_SECRET_KEY:
                    errors.append("STRIPE_SECRET_KEY is required when billing is enabled")
                if not self.STRIPE_WEBHOOK_SECRET:
                    errors.append("STRIPE_WEBHOOK_SECRET is required when billing is enabled")
        
        # 2. Integer range validation
        # File size limits (1MB to 100MB)
        if not (1 <= self.file_sizes.PDF_MB <= 100):
            errors.append(f"MAX_UPLOAD_PDF_MB must be between 1 and 100, got {self.file_sizes.PDF_MB}")
        if not (1 <= self.file_sizes.OFFICE_MB <= 100):
            errors.append(f"MAX_UPLOAD_OFFICE_MB must be between 1 and 100, got {self.file_sizes.OFFICE_MB}")
        if not (1 <= self.file_sizes.TEXT_MB <= 50):
            errors.append(f"MAX_UPLOAD_TEXT_MB must be between 1 and 50, got {self.file_sizes.TEXT_MB}")
        if not (1 <= self.file_sizes.BINARY_MB <= 100):
            errors.append(f"MAX_UPLOAD_BINARY_MB must be between 1 and 100, got {self.file_sizes.BINARY_MB}")
        
        # Security timeouts
        if not (1 <= self.security.SESSION_LIFETIME_DAYS <= 365):
            errors.append(f"SESSION_LIFETIME_DAYS must be between 1 and 365, got {self.security.SESSION_LIFETIME_DAYS}")
        if not (1 <= self.security.CSRF_TIMEOUT_HOURS <= 24):
            errors.append(f"CSRF_TIMEOUT_HOURS must be between 1 and 24, got {self.security.CSRF_TIMEOUT_HOURS}")
        if not (1 <= self.security.ANON_PROPOSAL_TTL_DAYS <= 90):
            errors.append(f"ANON_PROPOSAL_TTL_DAYS must be between 1 and 90, got {self.security.ANON_PROPOSAL_TTL_DAYS}")
        
        # Password policy
        if not (8 <= self.security.PASSWORD_MIN_LENGTH <= 128):
            errors.append(f"PASSWORD_MIN_LENGTH must be between 8 and 128, got {self.security.PASSWORD_MIN_LENGTH}")
        if not (1 <= self.security.PASSWORD_MIN_CHARACTER_CLASSES <= 4):
            errors.append(f"PASSWORD_MIN_CHARACTER_CLASSES must be between 1 and 4, got {self.security.PASSWORD_MIN_CHARACTER_CLASSES}")
        
        # Auth rate limiting
        if not (1 <= self.security.AUTH_MAX_FAILS <= 20):
            errors.append(f"AUTH_MAX_FAILS must be between 1 and 20, got {self.security.AUTH_MAX_FAILS}")
        if not (60 <= self.security.AUTH_FAIL_WINDOW_SEC <= 3600):
            errors.append(f"AUTH_FAIL_WINDOW_SEC must be between 60 and 3600, got {self.security.AUTH_FAIL_WINDOW_SEC}")
        if not (5 <= self.security.AUTH_LOCKOUT_MINUTES <= 1440):
            errors.append(f"AUTH_LOCKOUT_MINUTES must be between 5 and 1440, got {self.security.AUTH_LOCKOUT_MINUTES}")
        
        # Email verification
        if not (1 <= self.security.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS <= 168):
            errors.append(f"EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS must be between 1 and 168, got {self.security.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS}")
        
        # Antivirus timeout
        if not (1000 <= self.antivirus.AV_TIMEOUT_MS <= 120000):
            errors.append(f"AV_TIMEOUT_MS must be between 1000 and 120000, got {self.antivirus.AV_TIMEOUT_MS}")
        
        # ClamAV port
        if not (1 <= self.antivirus.CLAMD_PORT <= 65535):
            errors.append(f"CLAMD_PORT must be between 1 and 65535, got {self.antivirus.CLAMD_PORT}")
        
        # Reliability configuration validation
        if not (1 <= self.reliability.HTTP_TIMEOUT_SEC <= 300):
            errors.append(f"HTTP_TIMEOUT_SEC must be between 1 and 300, got {self.reliability.HTTP_TIMEOUT_SEC}")
        
        if not (0 <= self.reliability.HTTP_RETRIES <= 10):
            errors.append(f"HTTP_RETRIES must be between 0 and 10, got {self.reliability.HTTP_RETRIES}")
        
        if not (100 <= self.reliability.HTTP_BACKOFF_BASE_MS <= 10000):
            errors.append(f"HTTP_BACKOFF_BASE_MS must be between 100 and 10000, got {self.reliability.HTTP_BACKOFF_BASE_MS}")
        
        if not (1 <= self.reliability.CB_FAIL_THRESHOLD <= 50):
            errors.append(f"CB_FAIL_THRESHOLD must be between 1 and 50, got {self.reliability.CB_FAIL_THRESHOLD}")
        
        if not (10 <= self.reliability.CB_RESET_SEC <= 3600):
            errors.append(f"CB_RESET_SEC must be between 10 and 3600, got {self.reliability.CB_RESET_SEC}")
        
        # 3. Allowed enum validation
        # Antivirus mode
        allowed_av_modes = {"off", "clamd", "http"}
        if self.antivirus.MODE not in allowed_av_modes:
            errors.append(f"ANTIVIRUS_MODE must be one of {allowed_av_modes}, got '{self.antivirus.MODE}'")
        
        # Session backend
        allowed_session_backends = {"redis", "filesystem", "null"}
        if self.SESSION_BACKEND not in allowed_session_backends:
            errors.append(f"SESSION_BACKEND must be one of {allowed_session_backends}, got '{self.SESSION_BACKEND}'")
        
        # Queue mode
        allowed_queue_modes = {"celery", "cloud_tasks", "sync"}
        if self.QUEUE_MODE not in allowed_queue_modes:
            errors.append(f"QUEUE_MODE must be one of {allowed_queue_modes}, got '{self.QUEUE_MODE}'")
        
        # Session cookie SameSite
        allowed_samesite = {"Lax", "Strict", "None"}
        if self.SESSION_COOKIE_SAMESITE not in allowed_samesite:
            errors.append(f"SESSION_COOKIE_SAMESITE must be one of {allowed_samesite}, got '{self.SESSION_COOKIE_SAMESITE}'")
        
        # 4. URL format validation
        # Database URL
        if self.DATABASE_URL:
            try:
                parsed = urlparse(self.DATABASE_URL)
                if not parsed.scheme:
                    errors.append("DATABASE_URL must be a valid URL with scheme")
                # For SQLite, netloc can be empty (file:///path or sqlite:///path)
                # For other databases, netloc is required
                if parsed.scheme not in ['sqlite', 'file'] and not parsed.netloc:
                    errors.append("DATABASE_URL must be a valid URL with scheme and host")
            except Exception:
                errors.append("DATABASE_URL must be a valid URL")
        
        # Redis URL
        if self.SESSION_BACKEND == "redis":
            try:
                parsed = urlparse(self.SESSION_REDIS_URL_FINAL)
                if parsed.scheme != "redis":
                    errors.append("SESSION_REDIS_URL_FINAL must use 'redis://' scheme")
                if not parsed.netloc:
                    errors.append("SESSION_REDIS_URL_FINAL must have a valid host")
            except Exception:
                errors.append("SESSION_REDIS_URL_FINAL must be a valid URL")
        
        # GCS bucket names (simple validation)
        if self.GCS_BUCKET_NAME:
            if not re.match(r'^[a-z0-9][a-z0-9\-_\.]*[a-z0-9]$', self.GCS_BUCKET_NAME):
                errors.append("GCS_BUCKET_NAME must be a valid GCS bucket name (lowercase, hyphens, underscores, dots)")
        
        if self.GCS_PROCESSED_BUCKET_NAME:
            if not re.match(r'^[a-z0-9][a-z0-9\-_\.]*[a-z0-9]$', self.GCS_PROCESSED_BUCKET_NAME):
                errors.append("GCS_PROCESSED_BUCKET_NAME must be a valid GCS bucket name (lowercase, hyphens, underscores, dots)")
        
        # Sentry DSN (if provided)
        if self.SENTRY_DSN:
            try:
                parsed = urlparse(self.SENTRY_DSN)
                if not parsed.scheme or not parsed.netloc:
                    errors.append("SENTRY_DSN must be a valid URL")
            except Exception:
                errors.append("SENTRY_DSN must be a valid URL")
        
        # 5. Boolean parsing validation
        # Check that boolean environment variables have valid values
        boolean_env_vars = [
            "BILLING_ENABLED",
            "PASSWORD_REQUIRE_UPPERCASE", 
            "PASSWORD_REQUIRE_LOWERCASE",
            "PASSWORD_REQUIRE_DIGITS",
            "PASSWORD_REQUIRE_SYMBOLS",
            "AUTH_SINGLE_SESSION",
            "EMAIL_VERIFICATION_REQUIRED",
            "CSP_UPGRADE_INSECURE_REQUESTS",
            "ANTIVIRUS_REQUIRED",
            "FREE_TOOLS_REQUIRE_AUTH",
            "LOGIN_DISABLED",
            "MDRAFT_PUBLIC_MODE",
            "SESSION_COOKIE_SECURE",
            "SESSION_COOKIE_HTTPONLY",
            "FLASK_DEBUG",
        ]
        
        for env_var in boolean_env_vars:
            value = os.getenv(env_var)
            if value is not None:  # Only validate if the variable is set
                valid_values = {"true", "false", "1", "0", "yes", "no", "on", "off"}
                if value.lower() not in valid_values:
                    errors.append(f"{env_var} must be a valid boolean value (true/false, 1/0, yes/no, on/off), got '{value}'")
        
        # 6. Cross-field validation
        # If antivirus is required, mode must not be "off"
        if self.antivirus.AV_REQUIRED and self.antivirus.MODE == "off":
            errors.append("ANTIVIRUS_REQUIRED cannot be true when ANTIVIRUS_MODE is 'off'")
        
        # If antivirus mode is "clamd", socket or host/port must be provided
        if self.antivirus.MODE == "clamd":
            if not self.antivirus.CLAMD_SOCKET and not self.antivirus.CLAMD_HOST:
                errors.append("CLAMD_SOCKET or CLAMD_HOST must be provided when ANTIVIRUS_MODE is 'clamd'")
        
        # If antivirus mode is "http", endpoint must be provided
        if self.antivirus.MODE == "http" and not self.antivirus.AV_HTTP_ENDPOINT:
            errors.append("AV_HTTP_ENDPOINT must be provided when ANTIVIRUS_MODE is 'http'")
        
        # If billing is enabled, price must be valid
        if self.billing.ENABLED:
            try:
                price = float(self.billing.PRICE_PER_PAGE_USD)
                if price < 0:
                    errors.append("PRICING_DOC_OCR_PER_PAGE_USD must be non-negative")
            except ValueError:
                errors.append("PRICING_DOC_OCR_PER_PAGE_USD must be a valid decimal number")
        
        # If SameSite is "None", Secure must be true
        if self.SESSION_COOKIE_SAMESITE == "None" and not self.SESSION_COOKIE_SECURE:
            errors.append("SESSION_COOKIE_SECURE must be true when SESSION_COOKIE_SAMESITE is 'None'")
        
        # 7. Development vs Production validation
        if is_production:
            if self.FLASK_DEBUG:
                errors.append("FLASK_DEBUG must be false in production")
            
            if not self.SESSION_COOKIE_SECURE:
                errors.append("SESSION_COOKIE_SECURE must be true in production")
            
            if self.FLASK_SECRET_KEY == "changeme":
                errors.append("SECRET_KEY must not be 'changeme' in production")
        
        # Raise error if any validation failed
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ConfigurationError(error_msg)
    
    def get_file_size_limit(self, category: str) -> int:
        """Get file size limit for a specific category."""
        size_map = {
            "pdf": self.file_sizes.PDF_BYTES,
            "office": self.file_sizes.OFFICE_BYTES,
            "text": self.file_sizes.TEXT_BYTES,
            "doc": self.file_sizes.OFFICE_BYTES,  # Alias for office
        }
        return size_map.get(category, self.file_sizes.BINARY_BYTES)
    
    def get_rate_limit(self, limit_type: str) -> str:
        """Get rate limit for a specific type."""
        limit_map = {
            "global": self.rate_limits.GLOBAL_PER_MINUTE,
            "convert": self.rate_limits.CONVERT_PER_MINUTE,
            "ai": self.rate_limits.AI_PER_MINUTE,
            "anon_minute": self.rate_limits.ANON_PER_MINUTE,
            "anon_day": self.rate_limits.ANON_PER_DAY,
            "index": self.rate_limits.INDEX_PER_MINUTE,
            "login": self.rate_limits.LOGIN_PER_MINUTE,
            "upload": self.rate_limits.UPLOAD_PER_MINUTE,
            "upload_anon": self.rate_limits.UPLOAD_ANON_PER_MINUTE,
        }
        return limit_map.get(limit_type, self.rate_limits.GLOBAL_PER_MINUTE)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for Flask app.config."""
        return {
            # File size limits
            "MAX_UPLOAD_PDF_MB": self.file_sizes.PDF_MB,
            "MAX_UPLOAD_OFFICE_MB": self.file_sizes.OFFICE_MB,
            "MAX_UPLOAD_TEXT_MB": self.file_sizes.TEXT_MB,
            "MAX_UPLOAD_BINARY_MB": self.file_sizes.BINARY_MB,
            "MAX_CONTENT_LENGTH": self.FLASK_MAX_CONTENT_LENGTH,
            
            # Rate limits
            "GLOBAL_RATE_LIMIT": self.rate_limits.GLOBAL_PER_MINUTE,
            "CONVERT_RATE_LIMIT_DEFAULT": self.rate_limits.CONVERT_PER_MINUTE,
            "AI_RATE_LIMIT_DEFAULT": self.rate_limits.AI_PER_MINUTE,
            "ANON_RATE_LIMIT_PER_MINUTE": self.rate_limits.ANON_PER_MINUTE,
            "ANON_RATE_LIMIT_PER_DAY": self.rate_limits.ANON_PER_DAY,
            "INDEX_RATE_LIMIT": self.rate_limits.INDEX_PER_MINUTE,
            "LOGIN_RATE_LIMIT": self.rate_limits.LOGIN_PER_MINUTE,
            "UPLOAD_RATE_LIMIT": self.rate_limits.UPLOAD_PER_MINUTE,
            "UPLOAD_ANON_RATE_LIMIT": self.rate_limits.UPLOAD_ANON_PER_MINUTE,
            
            # Billing (non-sensitive)
            "BILLING_ENABLED": self.billing.ENABLED,
            "PRICING_DOC_OCR_PER_PAGE_USD": self.billing.PRICE_PER_PAGE_USD,
            "STRIPE_PRICE_PRO": self.billing.STRIPE_PRICE_PRO,
            # Note: STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET are handled separately
            # to prevent exposure in logs and configuration dumps
            
            # Security
            "SESSION_LIFETIME_DAYS": self.security.SESSION_LIFETIME_DAYS,
            "CSRF_TIMEOUT_HOURS": self.security.CSRF_TIMEOUT_HOURS,
            "ANON_PROPOSAL_TTL_DAYS": self.security.ANON_PROPOSAL_TTL_DAYS,
            "PASSWORD_MIN_LENGTH": self.security.PASSWORD_MIN_LENGTH,
            "PASSWORD_REQUIRE_UPPERCASE": self.security.PASSWORD_REQUIRE_UPPERCASE,
            "PASSWORD_REQUIRE_LOWERCASE": self.security.PASSWORD_REQUIRE_LOWERCASE,
            "PASSWORD_REQUIRE_DIGITS": self.security.PASSWORD_REQUIRE_DIGITS,
            "PASSWORD_REQUIRE_SYMBOLS": self.security.PASSWORD_REQUIRE_SYMBOLS,
            "PASSWORD_MIN_CHARACTER_CLASSES": self.security.PASSWORD_MIN_CHARACTER_CLASSES,
            "AUTH_MAX_FAILS": self.security.AUTH_MAX_FAILS,
            "AUTH_FAIL_WINDOW_SEC": self.security.AUTH_FAIL_WINDOW_SEC,
            "AUTH_LOCKOUT_MINUTES": self.security.AUTH_LOCKOUT_MINUTES,
            "AUTH_SINGLE_SESSION": self.security.AUTH_SINGLE_SESSION,
            "EMAIL_VERIFICATION_REQUIRED": self.security.EMAIL_VERIFICATION_REQUIRED,
            "EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS": self.security.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS,
            
            # CSP
            "CSP_DEFAULT_SRC": self.csp.DEFAULT_SRC,
            "CSP_SCRIPT_SRC": self.csp.SCRIPT_SRC,
            "CSP_STYLE_SRC": self.csp.STYLE_SRC,
            "CSP_IMG_SRC": self.csp.IMG_SRC,
            "CSP_CONNECT_SRC": self.csp.CONNECT_SRC,
            "CSP_FRAME_ANCESTORS": self.csp.FRAME_ANCESTORS,
            "CSP_REPORT_URI": self.csp.REPORT_URI,
            "CSP_OBJECT_SRC": self.csp.OBJECT_SRC,
            "CSP_BASE_URI": self.csp.BASE_URI,
            "CSP_UPGRADE_INSECURE_REQUESTS": self.csp.UPGRADE_INSECURE_REQUESTS,
            
            # Antivirus
            "ANTIVIRUS_MODE": self.antivirus.MODE,
            "CLAMD_SOCKET": self.antivirus.CLAMD_SOCKET,
            "CLAMD_HOST": self.antivirus.CLAMD_HOST,
            "CLAMD_PORT": self.antivirus.CLAMD_PORT,
            "AV_HTTP_ENDPOINT": self.antivirus.AV_HTTP_ENDPOINT,
            "AV_TIMEOUT_MS": self.antivirus.AV_TIMEOUT_MS,
            "ANTIVIRUS_REQUIRED": self.antivirus.AV_REQUIRED,
            
            # Reliability
            "HTTP_TIMEOUT_SEC": self.reliability.HTTP_TIMEOUT_SEC,
            "HTTP_RETRIES": self.reliability.HTTP_RETRIES,
            "HTTP_BACKOFF_BASE_MS": self.reliability.HTTP_BACKOFF_BASE_MS,
            "CB_FAIL_THRESHOLD": self.reliability.CB_FAIL_THRESHOLD,
            "CB_RESET_SEC": self.reliability.CB_RESET_SEC,
            
            # Flask (non-sensitive)
            "FLASK_DEBUG": self.FLASK_DEBUG,
            # Note: SECRET_KEY is handled separately to prevent exposure in logs
            
            # Database
            "DATABASE_URL": self.DATABASE_URL,
            
            # Google Cloud
            "GCS_BUCKET_NAME": self.GCS_BUCKET_NAME,
            "GCS_PROCESSED_BUCKET_NAME": self.GCS_PROCESSED_BUCKET_NAME,
            "CLOUD_TASKS_QUEUE_ID": self.CLOUD_TASKS_QUEUE_ID,
            "CLOUD_TASKS_LOCATION": self.CLOUD_TASKS_LOCATION,
            "DOCAI_PROCESSOR_ID": self.DOCAI_PROCESSOR_ID,
            "DOCAI_LOCATION": self.DOCAI_LOCATION,
            
            # Celery
            "CELERY_BROKER_URL": self.CELERY_BROKER_URL,
            "CELERY_RESULT_BACKEND": self.CELERY_RESULT_BACKEND,
            "QUEUE_MODE": self.QUEUE_MODE,
            
            # Authentication
            "FREE_TOOLS_REQUIRE_AUTH": self.FREE_TOOLS_REQUIRE_AUTH,
            "LOGIN_DISABLED": self.LOGIN_DISABLED,
            "MDRAFT_PUBLIC_MODE": self.MDRAFT_PUBLIC_MODE,
            "ALLOWLIST": self.ALLOWLIST,
            
            # Session
            "SESSION_BACKEND": self.SESSION_BACKEND,
            "SESSION_REDIS_URL": self.SESSION_REDIS_URL,
            "REDIS_URL": self.REDIS_URL,
            "SESSION_REDIS_URL_FINAL": self.SESSION_REDIS_URL_FINAL,
            "SESSION_COOKIE_SECURE": self.SESSION_COOKIE_SECURE,
            "SESSION_COOKIE_HTTPONLY": self.SESSION_COOKIE_HTTPONLY,
            "SESSION_COOKIE_SAMESITE": self.SESSION_COOKIE_SAMESITE,
            
            # Rate limiting
            "FLASK_LIMITER_STORAGE_URI": self.FLASK_LIMITER_STORAGE_URI,
            "RATE_ALLOWLIST": self.RATE_ALLOWLIST,
            
            # Sentry
            "SENTRY_DSN": self.SENTRY_DSN,
            "SENTRY_ENVIRONMENT": self.SENTRY_ENVIRONMENT,
            "SENTRY_RELEASE": self.SENTRY_RELEASE,
            
            # Development
            "MDRAFT_DEV_STUB": self.MDRAFT_DEV_STUB,
        }
    
    def apply_secrets_to_app(self, app) -> None:
        """Securely apply secrets to Flask app configuration without logging them."""
        # Apply secrets directly to app config to avoid exposure in logs
        app.config["SECRET_KEY"] = self.FLASK_SECRET_KEY
        app.config["STRIPE_SECRET_KEY"] = self.STRIPE_SECRET_KEY
        app.config["STRIPE_WEBHOOK_SECRET"] = self.STRIPE_WEBHOOK_SECRET
        app.config["OPENAI_API_KEY"] = self.OPENAI_API_KEY
        app.config["ADMIN_TOKEN"] = self.ADMIN_TOKEN
        app.config["WEBHOOK_SECRET"] = self.WEBHOOK_SECRET


# Global configuration instance
config = AppConfig()


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    return config


def get_file_size_limit(category: str) -> int:
    """Get file size limit for a specific category."""
    return config.get_file_size_limit(category)


def get_rate_limit(limit_type: str) -> str:
    """Get rate limit for a specific type."""
    return config.get_rate_limit(limit_type)
