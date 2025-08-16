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
from typing import Any, Dict

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
session: Session = Session()

# GLOBAL limiter (exported as app.limiter so routes can import it)
# Note: Limiter is initialized before config is available, so we use ENV directly
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=ENV.get("FLASK_LIMITER_STORAGE_URI"),
    default_limits=[ENV.get("GLOBAL_RATE_LIMIT", "120 per minute")],
)

# Register models with SQLAlchemy metadata so Alembic can see them
from .models_conversion import Conversion  # noqa: F401
from .models_apikey import ApiKey  # noqa: F401


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

    # Get centralized configuration
    config = get_config()
    
    # Validate configuration and fail fast if invalid
    try:
        config.validate()
        app.logger.info("Configuration validation passed")
    except ConfigurationError as e:
        app.logger.error(f"Configuration validation failed: {e}")
        raise
    
    # Apply non-sensitive configuration to Flask app
    app.config.update(config.to_dict())
    
    # Securely apply secrets to Flask app (prevents logging exposure)
    config.apply_secrets_to_app(app)
    
    # Database configuration
    from .utils.db_url import normalize_db_url
    db_url = normalize_db_url(config.DATABASE_URL)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.logger.info("DB driver normalized to psycopg v3")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # SQLAlchemy engine pooling configuration for Render
    # Optimized for PaaS environment with connection stability
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,      # Validate connections before use
        "pool_size": 5,             # Maintain 5 persistent connections
        "max_overflow": 5,          # Allow 5 additional connections when pool is full
        "pool_recycle": 1800,       # Recycle connections after 30 minutes
        "pool_timeout": 30,         # Wait up to 30 seconds for available connection
        "echo": False,              # Disable SQL echo in production
    }
    app.logger.info("SQLAlchemy engine pooling configured for Render deployment")
    
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

    # Initialize the global limiter on the app
    limiter.init_app(app)

    # Exempt health checks (keep Render happy)
    try:
        from .health import bp as _health_bp
        limiter.exempt(_health_bp)
    except Exception:
        pass

    # Optional allowlist: comma-separated IPs in RATE_ALLOWLIST
    from flask import request, jsonify
    @limiter.request_filter
    def _allowlist():
        ips = {ip.strip() for ip in config.RATE_ALLOWLIST.split(",") if ip.strip()}
        return request.remote_addr in ips

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
    setup_logging(app, log_level=level)
    
    # Initialize request logging middleware
    from .middleware.logging import init_request_logging
    init_request_logging(app)

    # Initialise extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # --- Session Configuration ---
    # Single code path for session configuration with hardened security
    if config.SESSION_BACKEND == "redis":
        # Redis session configuration for production
        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = config.REDIS_URL
        app.logger.info(f"Using Redis session backend: {config.REDIS_URL}")
    elif config.SESSION_BACKEND == "null":
        # Disable sessions entirely (for testing or minimal deployments)
        app.config["SESSION_TYPE"] = "null"
        app.logger.info("Sessions disabled (null backend)")
    else:
        # Filesystem session configuration (default for development)
        app.config["SESSION_TYPE"] = "filesystem"
        app.logger.info("Using filesystem session backend")
    
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
    
    # Initialize session extension
    session.init_app(app)
    
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
    from .auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from .ui import bp as ui_bp
    app.register_blueprint(ui_bp)

    from .health import bp as health_bp
    app.register_blueprint(health_bp)

    from .beta import bp as beta_bp
    app.register_blueprint(beta_bp)

    from .api_convert import bp as api_bp
    app.register_blueprint(api_bp)

    from .api_queue import bp as queue_bp
    app.register_blueprint(queue_bp)

    from .api_usage import bp as usage_api_bp
    app.register_blueprint(usage_api_bp)

    from .api_estimate import bp as estimate_api_bp
    app.register_blueprint(estimate_api_bp)

    from .view import bp as view_bp
    app.register_blueprint(view_bp)

    from .routes import bp as main_blueprint  # type: ignore
    app.register_blueprint(main_blueprint)
    
    from .admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    
    from .billing import bp as billing_bp
    app.register_blueprint(billing_bp)
    
    from .api.agents import bp as agents_bp
    app.register_blueprint(agents_bp)
    
    from .api.ops import bp as ops_bp
    app.register_blueprint(ops_bp)
    
    from .api.errors import errors
    app.register_blueprint(errors)
    
    from .cli import register_cli
    register_cli(app)
    
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

    # Error handling is now managed by the errors blueprint
    # which provides unified JSON error responses with Sentry integration

    return app