"""
Application factory for the mdraft service.

This module defines `create_app`, which constructs and configures the Flask
application.  Extensions such as the database, migrations, rate limiter,
and logging are initialised here.  Blueprints containing route
definitions are registered within this function.  Using a factory
function makes it easy to create multiple instances of the app with
different configurations, which is useful for testing and asynchronous
workers.
"""
from __future__ import annotations

import os as _os
ENV = _os.environ

import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Flask, has_request_context, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from sqlalchemy import text

# Import centralized configuration
from .config import get_config, ConfigurationError

# Import structured logging
from .utils.logging import setup_logging, StructuredJSONFormatter

# Initialise extensions without an application context.  They will be
# bound to the app inside create_app().
db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
bcrypt: Bcrypt = Bcrypt()
login_manager: LoginManager = LoginManager()
csrf: CSRFProtect = CSRFProtect()
# Note: session will be initialized after configuration is set
session: Optional[Session] = None

# GLOBAL limiter (exported as app.limiter so routes can import it)
# Initialize with safe defaults - will be configured during app creation
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"],
)

# Global flag to track if limiter is properly initialized
_limiter_initialized = False

# Register models with SQLAlchemy metadata so Alembic can see them
from .models_conversion import Conversion  # noqa: F401
from .models_apikey import ApiKey  # noqa: F401

# Helper function for conditional rate limiting
def conditional_limit(limit_string: str):
    """Apply rate limit only if limiter is enabled."""
    try:
        if _limiter_initialized and limiter and limiter.default_limits:
            return limiter.limit(limit_string)
    except Exception:
        # If limiter.limit() fails, fall back to no-op
        pass
    return lambda f: f  # No-op decorator

# Export conditional_limit for use in other modules
__all__ = ['limiter', 'conditional_limit', 'db', 'migrate', 'bcrypt', 'login_manager', 'csrf', 'session']


# Legacy JSONFormatter kept for backward compatibility
class JSONFormatter(logging.Formatter):
    """Format log records as JSON with optional correlation ID support."""

    def format(self, record: logging.LogRecord) -> str:
        # Build a base payload.  Use isoformat() for a human-readable time
        # representation that still sorts lexicographically.
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # When handling a request, include the correlation ID if available.
        if has_request_context():
            request_id = request.environ.get("HTTP_X_REQUEST_ID") or request.environ.get("X-Request-ID")
            corr_id = request_id or "N/A"
            # Add request-specific context
            log_data["request_id"] = request_id or "N/A"
            log_data["task_name"] = request.headers.get("X-Cloud-Tasks-TaskName", "N/A")
            log_data["queue_name"] = request.headers.get("X-Cloud-Tasks-QueueName", "N/A")
            log_data["job_id"] = request.environ.get("X-Job-ID", "N/A")
            log_data["conversion_id"] = request.environ.get("X-Conversion-ID", "N/A")
        else:
            corr_id = "N/A"
        log_data["correlation_id"] = corr_id
        # Include the name of the logger to aid in filtering.
        log_data["logger"] = record.name
        # Append any extra context stored in the record.
        if record.args:
            log_data["args"] = record.args
        return json.dumps(log_data, default=str)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Add startup logging
    app.logger.info("=== Starting mdraft application initialization ===")
    app.logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    app.logger.info(f"Python version: {os.sys.version}")
    app.logger.info(f"Working directory: {os.getcwd()}")

    # Get centralized configuration
    try:
        app.logger.info("Loading configuration...")
        config = get_config()
        app.logger.info("Configuration loaded successfully")
    except Exception as e:
        app.logger.error(f"Failed to load configuration: {e}")
        app.logger.error(f"Configuration error type: {type(e).__name__}")
        app.logger.error(f"Configuration error details: {str(e)}")
        raise
    
    # Validate configuration and fail fast if invalid
    try:
        app.logger.info("Validating configuration...")
        config.validate()
        app.logger.info("Configuration validation passed")
    except ConfigurationError as e:
        app.logger.error(f"Configuration validation failed: {e}")
        app.logger.error(f"Configuration validation error type: {type(e).__name__}")
        app.logger.error(f"Configuration validation error details: {str(e)}")
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error during configuration validation: {e}")
        app.logger.error(f"Unexpected error type: {type(e).__name__}")
        app.logger.error(f"Unexpected error details: {str(e)}")
        raise
    
    # Apply non-sensitive configuration to Flask app
    try:
        app.logger.info("Applying configuration to Flask app...")
        app.config.update(config.to_dict())
        app.logger.info("Configuration applied successfully")
    except Exception as e:
        app.logger.error(f"Failed to apply configuration: {e}")
        app.logger.error(f"Configuration application error type: {type(e).__name__}")
        app.logger.error(f"Configuration application error details: {str(e)}")
        raise
    
    # Securely apply secrets to Flask app (prevents logging exposure)
    try:
        app.logger.info("Applying secrets to Flask app...")
        config.apply_secrets_to_app(app)
        app.logger.info("Secrets applied successfully")
    except Exception as e:
        app.logger.error(f"Failed to apply secrets: {e}")
        app.logger.error(f"Secrets application error type: {type(e).__name__}")
        app.logger.error(f"Secrets application error details: {str(e)}")
        raise
    
    # Database configuration
    try:
        app.logger.info("Configuring database...")
        from .utils.db_url import normalize_db_url
        db_url = normalize_db_url(config.DATABASE_URL)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        app.logger.info("DB driver normalized to psycopg v3")
        app.logger.info(f"Database URL type: {type(db_url)}")
        app.logger.info(f"Database URL length: {len(db_url) if db_url else 0}")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        
        # SQLAlchemy engine pooling configuration - database-specific
        if "postgresql" in db_url.lower():
            # PostgreSQL pooling configuration for Render
            # Optimized for PaaS environment with connection stability
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "pool_pre_ping": True,      # Validate connections before use
                "pool_size": 5,             # Maintain 5 persistent connections
                "max_overflow": 5,          # Allow 5 additional connections when pool is full
                "pool_recycle": 1800,       # Recycle connections after 30 minutes
                "pool_timeout": 30,         # Wait up to 30 seconds for available connection
                "echo": False,              # Disable SQL echo in production
            }
            app.logger.info("SQLAlchemy PostgreSQL pooling configured for Render deployment")
        elif "sqlite" in db_url.lower():
            # SQLite configuration (for testing/development)
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "pool_pre_ping": True,      # Validate connections before use
                "echo": False,              # Disable SQL echo in production
            }
            app.logger.info("SQLAlchemy SQLite configuration applied")
        else:
            # Default configuration for other databases
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "pool_pre_ping": True,      # Validate connections before use
                "echo": False,              # Disable SQL echo in production
            }
            app.logger.info("SQLAlchemy default configuration applied")
    except Exception as e:
        app.logger.error(f"Failed to configure database: {e}")
        app.logger.error(f"Database configuration error type: {type(e).__name__}")
        app.logger.error(f"Database configuration error details: {str(e)}")
        raise
    
    # Sentry configuration
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    if config.SENTRY_DSN:
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            integrations=[FlaskIntegration()],
            environment=config.SENTRY_ENVIRONMENT,
            release=config.SENTRY_RELEASE,
            traces_sample_rate=0.10,   # adjust later
        )

    # Add CORS for APIs only
    from flask_cors import CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)

    # Flask-Limiter configuration
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)

    # Configure limiter with environment settings - BULLETPROOF APPROACH
    # Always configure the limiter first, then handle any errors
    storage_uri = ENV.get("FLASK_LIMITER_STORAGE_URI", "memory://")
    default_limits = [ENV.get("GLOBAL_RATE_LIMIT", "120 per minute")]
    
    # Configure the global limiter instance with Redis URL cleaning
    if storage_uri and storage_uri != "memory://":
        # Clean the Redis URL to remove any trailing whitespace
        clean_storage_uri = storage_uri.strip()
        limiter.storage_uri = clean_storage_uri
        app.logger.info(f"Flask-Limiter using Redis storage: {clean_storage_uri[:20]}...")
    else:
        limiter.storage_uri = "memory://"
        app.logger.info("Flask-Limiter using memory storage")
    
    limiter.default_limits = default_limits
    
    # Try to initialize with the app
    try:
        limiter.init_app(app)
        _limiter_initialized = True
        app.logger.info("Flask-Limiter initialized successfully")
    except Exception as e:
        app.logger.error(f"Flask-Limiter initialization failed: {e}")
        app.logger.error(f"Limiter error type: {type(e).__name__}")
        app.logger.error(f"Limiter error details: {str(e)}")
        
        # In production, continue without rate limiting instead of crashing
        if os.getenv("FLASK_ENV") == "production":
            app.logger.warning("Flask-Limiter disabled due to initialization failure - continuing without rate limiting")
            # Fall back to memory storage
            limiter.storage_uri = "memory://"
            limiter.default_limits = []
            _limiter_initialized = False
        else:
            app.logger.warning("Flask-Limiter disabled due to initialization failure")
            # Disable by clearing limits - limiter object still exists
            limiter.default_limits = []
            _limiter_initialized = False

    # Exempt health checks (keep Render happy)
    try:
        from .health import bp as _health_bp
        if _limiter_initialized and limiter and limiter.default_limits:
            limiter.exempt(_health_bp)
    except Exception:
        pass

    # Optional allowlist: comma-separated IPs in RATE_ALLOWLIST
    from flask import request, jsonify
    if _limiter_initialized and limiter and limiter.default_limits:
        @limiter.request_filter
        def _allowlist():
            try:
                allowlist_str = getattr(config, 'RATE_ALLOWLIST', '')
                if not allowlist_str:
                    return False
                ips = {ip.strip() for ip in allowlist_str.split(",") if ip.strip()}
                return request.remote_addr in ips
            except Exception:
                return False

    # Request ID middleware is now handled by structured logging

    # Add comprehensive security headers with CSP
    @app.after_request
    def _set_secure_headers(resp):
        # Determine if this is an HTML response that needs CSP
        is_html_response = (
            resp.mimetype == 'text/html' or 
            request.path.endswith('.html') or
            (resp.mimetype and 'html' in resp.mimetype)
        )
        
        # Determine if this is an API response (JSON)
        is_api_response = (
            request.path.startswith('/api/') or
            resp.mimetype == 'application/json' or
            (resp.mimetype and 'json' in resp.mimetype)
        )
        
        # Always set basic security headers
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()")
        
        # HSTS (ok behind Render's TLS)
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains; preload")
        
        # Add CSP only for HTML responses
        if is_html_response:
            csp_policy = config.csp.build_policy()
            resp.headers.setdefault("Content-Security-Policy", csp_policy)
            app.logger.debug(f"Applied CSP policy to HTML response: {csp_policy}")
        
        # For API responses, keep minimal headers (no CSP)
        if is_api_response:
            app.logger.debug("API response - minimal security headers applied")
        
        return resp
    
    # Configure logging level
    level = (os.getenv("LOG_LEVEL") or "INFO").upper()
    
    # Database connection pool monitoring
    @app.after_request
    def _log_pool_stats(resp):
        """Log connection pool statistics for monitoring."""
        try:
            if hasattr(db.engine, 'pool'):
                pool = db.engine.pool
                app.logger.debug(
                    "DB Pool Stats",
                    extra={
                        "pool_size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                        "invalid": pool.invalid()
                    }
                )
        except Exception as e:
            app.logger.debug(f"Could not log pool stats: {e}")
        return resp

    # Initialize structured logging
    try:
        app.logger.info("Initializing structured logging...")
        setup_logging(app, log_level=level)
        app.logger.info("Structured logging initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize structured logging: {e}")
        app.logger.error(f"Logging initialization error type: {type(e).__name__}")
        app.logger.error(f"Logging initialization error details: {str(e)}")
        raise
    
    # Initialize request logging middleware
    try:
        app.logger.info("Initializing request logging middleware...")
        from .middleware.logging import init_request_logging
        init_request_logging(app)
        app.logger.info("Request logging middleware initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize request logging middleware: {e}")
        app.logger.error(f"Request logging error type: {type(e).__name__}")
        app.logger.error(f"Request logging error details: {str(e)}")
        raise

    # Initialise extensions
    try:
        app.logger.info("Initializing Flask extensions...")
        db.init_app(app)
        app.logger.info("SQLAlchemy initialized")
        
        migrate.init_app(app, db)
        app.logger.info("Flask-Migrate initialized")
        
        bcrypt.init_app(app)
        app.logger.info("Flask-Bcrypt initialized")
        
        login_manager.init_app(app)
        app.logger.info("Flask-Login initialized")
        
        csrf.init_app(app)
        app.logger.info("Flask-WTF CSRF initialized")
        
        app.logger.info("All Flask extensions initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize Flask extensions: {e}")
        app.logger.error(f"Extension initialization error type: {type(e).__name__}")
        app.logger.error(f"Extension initialization error details: {str(e)}")
        raise
    
    # --- Session Configuration ---
    # Single code path for session configuration with hardened security
    redis_client = None  # Will hold the Redis client for session storage
    
    if config.SESSION_BACKEND == "redis":
        try:
            app.logger.info("Configuring Redis session backend...")
            
            # Clean Redis URLs to remove any trailing whitespace
            if config.SESSION_REDIS_URL:
                clean_redis_url = config.SESSION_REDIS_URL.strip()
                app.config["SESSION_REDIS_URL"] = clean_redis_url
                app.logger.info(f"Using SESSION_REDIS_URL for session storage: {clean_redis_url[:20]}...")
            elif config.REDIS_URL:
                clean_redis_url = config.REDIS_URL.strip()
                app.config["SESSION_REDIS_URL"] = clean_redis_url
                app.logger.info(f"Using REDIS_URL for session storage: {clean_redis_url[:20]}...")
            else:
                app.logger.warning("No Redis URL configured, falling back to filesystem sessions")
                app.config["SESSION_TYPE"] = "filesystem"
                app.logger.info("Using filesystem session backend (fallback)")
                
            # Test Redis connection and create client for session storage
            if app.config.get("SESSION_REDIS_URL"):
                import redis
                import ssl
                
                # Configure Redis client with SSL support for Render
                redis_url = app.config["SESSION_REDIS_URL"]
                app.logger.info(f"Creating Redis client for URL: {redis_url[:20]}...")
                
                # Check if URL uses SSL (rediss://)
                use_ssl = redis_url.startswith('rediss://')
                app.logger.info(f"Redis SSL enabled: {use_ssl}")
                
                redis_client = redis.from_url(
                    redis_url,
                    decode_responses=False,  # Flask-Session handles encoding/decoding
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                    ssl=use_ssl,
                    ssl_cert_reqs=None if use_ssl else None,  # Don't verify SSL cert for Render
                    ssl_ca_certs=None if use_ssl else None    # Don't verify SSL cert for Render
                )
                redis_client.ping()
                app.logger.info("Redis session connection successful")
                # Set SESSION_TYPE to redis only after successful connection
                app.config["SESSION_TYPE"] = "redis"
                
        except Exception as e:
            if os.getenv("FLASK_ENV") == "production":
                app.logger.error(f"Failed to initialize Redis session backend: {e}")
                app.logger.error(f"Redis error type: {type(e).__name__}")
                app.logger.error(f"Redis error details: {str(e)}")
                # In production, fall back to filesystem sessions instead of crashing
                app.logger.warning("Falling back to filesystem sessions due to Redis failure")
                app.config["SESSION_TYPE"] = "filesystem"
                app.logger.info("Using filesystem session backend (fallback)")
                redis_client = None  # Ensure redis_client is None on failure
            else:
                app.logger.warning(f"Redis session backend failed, falling back to filesystem: {e}")
                app.config["SESSION_TYPE"] = "filesystem"
                app.logger.info("Using filesystem session backend (fallback)")
                redis_client = None  # Ensure redis_client is None on failure
    elif config.SESSION_BACKEND == "null":
        # Disable sessions entirely (for testing or minimal deployments)
        # Use filesystem with minimal settings instead of "null"
        app.config["SESSION_TYPE"] = "filesystem"
        app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"
        app.config["SESSION_FILE_THRESHOLD"] = 0  # Don't create files
        app.logger.info("Sessions disabled (using minimal filesystem backend)")
        redis_client = None  # Ensure redis_client is None
    else:
        # Filesystem session configuration (default for development)
        app.config["SESSION_TYPE"] = "filesystem"
        app.logger.info("Using filesystem session backend")
        redis_client = None  # Ensure redis_client is None
    
    # Hardened session cookie configuration
    app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE
    app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
    
    # Session lifetime configuration (in seconds)
    session_lifetime_seconds = 60 * 60 * 24 * config.security.SESSION_LIFETIME_DAYS
    app.config["PERMANENT_SESSION_LIFETIME"] = session_lifetime_seconds
    app.config["SESSION_COOKIE_MAX_AGE"] = session_lifetime_seconds
    
    app.logger.info(f"Session lifetime: {config.security.SESSION_LIFETIME_DAYS} days ({session_lifetime_seconds} seconds)")
    app.logger.info(f"Session cookies: Secure={config.SESSION_COOKIE_SECURE}, HttpOnly={config.SESSION_COOKIE_HTTPONLY}, SameSite={config.SESSION_COOKIE_SAMESITE}")
    
    # Initialize session extension after configuration is set
    global session
    session = Session()
    
    # If we have a Redis client, initialize Flask-Session with it directly
    app.logger.info(f"Session configuration - SESSION_TYPE: {app.config.get('SESSION_TYPE')}, redis_client: {redis_client is not None}")
    
    if redis_client and app.config.get("SESSION_TYPE") == "redis":
        app.logger.info("Initializing Flask-Session with Redis client")
        session.init_app(app, redis_client)
    else:
        app.logger.info("Initializing Flask-Session with default configuration")
        session.init_app(app)
    
    # Test Redis connectivity for all Redis URLs during startup
    try:
        import redis
        redis_urls_to_test = []
        
        if config.SESSION_REDIS_URL:
            redis_urls_to_test.append(("SESSION_REDIS_URL", config.SESSION_REDIS_URL))
        if config.REDIS_URL:
            redis_urls_to_test.append(("REDIS_URL", config.REDIS_URL))
        if config.FLASK_LIMITER_STORAGE_URI:
            redis_urls_to_test.append(("FLASK_LIMITER_STORAGE_URI", config.FLASK_LIMITER_STORAGE_URI))
        
        for name, url in redis_urls_to_test:
            try:
                clean_url = url.strip()
                # Check if URL uses SSL (rediss://)
                use_ssl = clean_url.startswith('rediss://')
                app.logger.info(f"Testing Redis connection for {name} (SSL: {use_ssl})")
                
                client = redis.from_url(
                    clean_url, 
                    decode_responses=True, 
                    socket_connect_timeout=5, 
                    socket_timeout=5,
                    ssl=use_ssl,
                    ssl_cert_reqs=None if use_ssl else None,  # Don't verify SSL cert for Render
                    ssl_ca_certs=None if use_ssl else None    # Don't verify SSL cert for Render
                )
                client.ping()
                app.logger.info(f"Redis connection test successful for {name}")
            except Exception as e:
                app.logger.error(f"Redis connection test failed for {name}: {e}")
                if os.getenv("FLASK_ENV") == "production":
                    app.logger.error(f"Redis connection failure for {name} in production - this may cause issues")
                
    except ImportError:
        app.logger.warning("redis package not available - skipping Redis connection tests")
    except Exception as e:
        app.logger.error(f"Unexpected error during Redis connection testing: {e}")
    
    # CSRF Configuration
    app.config.setdefault("WTF_CSRF_ENABLED", True)
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", 60 * 60 * config.security.CSRF_TIMEOUT_HOURS)
    
    # CSRF exemption logic is now handled by the @csrf_exempt_api decorator
    # which uses the is_api_request() helper for explicit allowlist validation
    
    # CSRF exemption for API routes using the new is_api_request helper
    @app.before_request
    def _csrf_exempt_api_routes():
        """Exempt API routes from CSRF when using the is_api_request() helper."""
        from app.utils.csrf import is_api_request
        if is_api_request(request):
            csrf.exempt(request)

    # --- Authentication Configuration ---
    # Respect environment variable for login enforcement
    app.config.setdefault("LOGIN_DISABLED", config.LOGIN_DISABLED)
    
    # Visitor session configuration
    app.config.setdefault("VISITOR_SESSION_TTL_DAYS", config.security.SESSION_LIFETIME_DAYS)
    
    # Flask-Login cookie security configuration (overridden by Flask-Session above)
    app.config.setdefault("REMEMBER_COOKIE_SECURE", True)  # Always Secure
    app.config.setdefault("REMEMBER_COOKIE_HTTPONLY", True)  # Always HttpOnly
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")  # SameSite=Lax
    app.config.setdefault("REMEMBER_COOKIE_MAX_AGE", 60 * 60 * 24 * config.security.SESSION_LIFETIME_DAYS)
    
    # Configure login manager
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "error"
    
    # Custom unauthorized handler for API routes
    @login_manager.unauthorized_handler
    def unauthorized():
        """Handle unauthorized access - redirect for UI, JSON for API."""
        from flask import request, jsonify
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized", "detail": "Login required"}), 401
        # For non-API routes, redirect to login (default behavior)
        from flask import redirect, url_for
        return redirect(url_for("auth.login", next=request.url))
    
    # Only disable login if explicitly configured
    if config.LOGIN_DISABLED:
        try:
            # If a LoginManager was attached, give it a no-op user_loader.
            lm = getattr(app, "login_manager", None)
            if lm is not None and getattr(lm, "user_callback", None) is None and getattr(lm, "request_callback", None) is None:
                @lm.user_loader
                def _noop_user_loader(_):
                    return None
        except Exception:
            pass
    else:
        # Set up proper user loader when login is enabled
        @login_manager.user_loader
        def load_user(user_id):
            """Load user by ID for Flask-Login."""
            from .models import User
            return User.query.get(int(user_id))
    # --- end auth configuration ---

    # Ensure upload and processed directories exist.  These directories
    # simulate storage buckets in production.  They should be ignored by
    # version control (see .gitignore).
    base_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.dirname(base_dir)
    uploads_path = os.path.join(project_root, "uploads")
    processed_path = os.path.join(project_root, "processed")
    os.makedirs(uploads_path, exist_ok=True)
    os.makedirs(processed_path, exist_ok=True)

    # Register blueprints containing route definitions
    try:
        app.logger.info("Registering blueprints...")
        
        from .auth.routes import bp as auth_bp
        app.register_blueprint(auth_bp)
        app.logger.info("Auth blueprint registered")
        
        from .ui import bp as ui_bp
        app.register_blueprint(ui_bp)
        app.logger.info("UI blueprint registered")
        
        from .health import bp as health_bp
        app.register_blueprint(health_bp)
        app.logger.info("Health blueprint registered")
        
        from .beta import bp as beta_bp
        app.register_blueprint(beta_bp)
        app.logger.info("Beta blueprint registered")
        
        from .api_convert import bp as api_bp
        app.register_blueprint(api_bp)
        app.logger.info("API convert blueprint registered")
        
        from .api_queue import bp as queue_bp
        app.register_blueprint(queue_bp)
        app.logger.info("API queue blueprint registered")
        
        from .api_usage import bp as usage_api_bp
        app.register_blueprint(usage_api_bp)
        app.logger.info("API usage blueprint registered")
        
        from .api_estimate import bp as estimate_api_bp
        app.register_blueprint(estimate_api_bp)
        app.logger.info("API estimate blueprint registered")
        
        from .view import bp as view_bp
        app.register_blueprint(view_bp)
        app.logger.info("View blueprint registered")
        
        from .routes import bp as main_blueprint  # type: ignore
        app.register_blueprint(main_blueprint)
        app.logger.info("Main blueprint registered")
        
        from .admin import bp as admin_bp
        app.register_blueprint(admin_bp)
        app.logger.info("Admin blueprint registered")
        
        from .billing import bp as billing_bp
        app.register_blueprint(billing_bp)
        app.logger.info("Billing blueprint registered")
        
        from .api.agents import bp as agents_bp
        app.register_blueprint(agents_bp)
        app.logger.info("API agents blueprint registered")
        
        from .api.ops import bp as ops_bp
        app.register_blueprint(ops_bp)
        app.logger.info("API ops blueprint registered")
        
        from .api.errors import errors
        app.register_blueprint(errors)
        app.logger.info("API errors blueprint registered")
        
        from .cli import register_cli
        register_cli(app)
        app.logger.info("CLI commands registered")
        
        app.logger.info("All blueprints registered successfully")
        
    except Exception as e:
        app.logger.error(f"Failed to register blueprints: {e}")
        app.logger.error(f"Blueprint registration error type: {type(e).__name__}")
        app.logger.error(f"Blueprint registration error details: {str(e)}")
        app.logger.error(f"Blueprint registration error traceback: {e.__traceback__}")
        raise
    
    # Register worker blueprint if running as worker service
    if ENV.get("WORKER_SERVICE", "false").lower() == "true":
        from .worker_routes import worker_bp as worker_blueprint  # type: ignore
        app.register_blueprint(worker_blueprint)
        
        # Initialize Cloud Tasks queue if needed
        from .tasks import create_queue_if_not_exists
        with app.app_context():
            create_queue_if_not_exists()

    # Add fail-fast schema check in non-test environments
    if not app.config.get("TESTING", False):
        try:
            with app.app_context():
                # Database-agnostic schema check
                db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
                if "sqlite" in db_url.lower():
                    # SQLite-specific check
                    res = db.session.execute(text("""
                        SELECT COUNT(*) FROM pragma_table_info('proposals')
                        WHERE name='visitor_session_id'
                    """)).scalar()
                else:
                    # PostgreSQL/MySQL-specific check
                    res = db.session.execute(text("""
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name='proposals' AND column_name='visitor_session_id'
                    """)).scalar()
                
                if res != 1:
                    app.logger.error("DB not migrated: proposals.visitor_session_id missing")
                    app.logger.error("Migration doctor should have run at startup")
        except Exception as e:
            app.logger.error(f"DB probe error: {e}")

    # Add comprehensive error handler for unhandled exceptions
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle any unhandled exceptions with detailed logging."""
        app.logger.error(f"Unhandled exception: {error}")
        app.logger.error(f"Exception type: {type(error).__name__}")
        app.logger.error(f"Exception details: {str(error)}")
        
        # Log request context if available
        if has_request_context():
            app.logger.error(f"Request URL: {request.url}")
            app.logger.error(f"Request method: {request.method}")
            app.logger.error(f"Request headers: {dict(request.headers)}")
            app.logger.error(f"Request remote addr: {request.remote_addr}")
        
        # Log full traceback for debugging
        import traceback
        app.logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Return a generic error response
        return {"error": "Internal server error", "detail": "An unexpected error occurred"}, 500

    # Add specific 500 error handler for better debugging
    @app.errorhandler(500)
    def handle_500_error(error):
        """Handle 500 errors with detailed logging."""
        app.logger.error(f"500 Internal Server Error: {error}")
        app.logger.error(f"Error type: {type(error).__name__}")
        app.logger.error(f"Error details: {str(error)}")
        
        # Log request context
        if has_request_context():
            app.logger.error(f"Request URL: {request.url}")
            app.logger.error(f"Request method: {request.method}")
            app.logger.error(f"Request remote addr: {request.remote_addr}")
            app.logger.error(f"Request user agent: {request.headers.get('User-Agent', 'Unknown')}")
        
        # Log full traceback
        import traceback
        app.logger.error(f"500 error traceback: {traceback.format_exc()}")
        
        # Return a simple error response
        return "<h1>500 Internal Server Error</h1><p>An error occurred while processing your request.</p>", 500

    # Add startup validation
    try:
        app.logger.info("Performing startup validation...")
        
        # Check if critical routes are registered
        root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
        app.logger.info(f"Root routes registered: {len(root_routes)}")
        for route in root_routes:
            app.logger.info(f"  - {route.endpoint}")
        
        # Check if health endpoint is available
        health_routes = [r for r in app.url_map.iter_rules() if "health" in r.rule]
        app.logger.info(f"Health routes registered: {len(health_routes)}")
        for route in health_routes:
            app.logger.info(f"  - {route.rule} -> {route.endpoint}")
        
        # Log total number of routes
        total_routes = len(list(app.url_map.iter_rules()))
        app.logger.info(f"Total routes registered: {total_routes}")
        
        app.logger.info("Startup validation completed successfully")
        
    except Exception as e:
        app.logger.error(f"Startup validation failed: {e}")
        app.logger.error(f"Validation error type: {type(e).__name__}")
        app.logger.error(f"Validation error details: {str(e)}")
        # Don't raise here, just log the error

    app.logger.info("=== mdraft application initialization completed successfully ===")
    return app