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
from sqlalchemy import text

# Import middleware
from .middleware.logging import init_request_logging

# Initialise extensions without an application context.  They will be
# bound to the app inside create_app().
db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
bcrypt: Bcrypt = Bcrypt()
login_manager: LoginManager = LoginManager()

# GLOBAL limiter (exported as app.limiter so routes can import it)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=ENV.get("FLASK_LIMITER_STORAGE_URI"),
    default_limits=[ENV.get("GLOBAL_RATE_LIMIT", "120 per minute")],
)

# Register models with SQLAlchemy metadata so Alembic can see them
from .models_conversion import Conversion  # noqa: F401
from .models_apikey import ApiKey  # noqa: F401


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

    # Application configuration
    app.config["SECRET_KEY"] = ENV.get("SECRET_KEY", "changeme")
    app.config.setdefault("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)  # 25 MB hard cap
    
    # Database configuration
    from .utils.db_url import normalize_db_url
    db_url = normalize_db_url(ENV.get("DATABASE_URL", ""))
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.logger.info("DB driver normalized to psycopg v3")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Google Cloud Storage configuration
    app.config["GCS_BUCKET_NAME"] = ENV.get("GCS_BUCKET_NAME")
    app.config["GCS_PROCESSED_BUCKET_NAME"] = ENV.get("GCS_PROCESSED_BUCKET_NAME")
    
    # Google Cloud Tasks configuration
    app.config["CLOUD_TASKS_QUEUE_ID"] = ENV.get("CLOUD_TASKS_QUEUE_ID")
    app.config["CLOUD_TASKS_LOCATION"] = ENV.get("CLOUD_TASKS_LOCATION", "us-central1")
    
    # Celery configuration
    app.config["CELERY_BROKER_URL"] = ENV.get("CELERY_BROKER_URL")
    app.config["CELERY_RESULT_BACKEND"] = ENV.get("CELERY_RESULT_BACKEND")
    app.config["QUEUE_MODE"] = ENV.get("QUEUE_MODE", "celery")
    
    # Rate limiting configuration
    app.config["CONVERT_RATE_LIMIT_DEFAULT"] = ENV.get("CONVERT_RATE_LIMIT_DEFAULT", "20 per minute")
    
    # Billing configuration
    app.config["BILLING_ENABLED"] = ENV.get("BILLING_ENABLED", "0") == "1"
    app.config["STRIPE_SECRET_KEY"] = ENV.get("STRIPE_SECRET_KEY")
    app.config["STRIPE_PRICE_PRO"] = ENV.get("STRIPE_PRICE_PRO")
    app.config["STRIPE_WEBHOOK_SECRET"] = ENV.get("STRIPE_WEBHOOK_SECRET")
    
    # Document AI configuration
    app.config["DOCAI_PROCESSOR_ID"] = ENV.get("DOCAI_PROCESSOR_ID")
    app.config["DOCAI_LOCATION"] = ENV.get("DOCAI_LOCATION", "us")
    
    # Anonymous proposal configuration
    app.config["FREE_TOOLS_REQUIRE_AUTH"] = ENV.get("FREE_TOOLS_REQUIRE_AUTH", "false").lower() == "true"
    app.config["ANON_PROPOSAL_TTL_DAYS"] = int(ENV.get("ANON_PROPOSAL_TTL_DAYS", "14"))
    app.config["ANON_RATE_LIMIT_PER_MINUTE"] = ENV.get("ANON_RATE_LIMIT_PER_MINUTE", "20")
    app.config["ANON_RATE_LIMIT_PER_DAY"] = ENV.get("ANON_RATE_LIMIT_PER_DAY", "200")
    
    # Sentry configuration
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_dsn = ENV.get("SENTRY_DSN")
    sentry_env = ENV.get("SENTRY_ENVIRONMENT", "production")
    sentry_release = ENV.get("SENTRY_RELEASE")  # optional

    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            environment=sentry_env,
            release=sentry_release,
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
        ips = {ip.strip() for ip in ENV.get("RATE_ALLOWLIST","").split(",") if ip.strip()}
        return request.remote_addr in ips

    # Add request ID middleware
    @app.before_request
    def _set_request_id():
        """Set request ID for logging and tracing."""
        import uuid
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.environ['X-Request-ID'] = request_id
        request.environ['HTTP_X_REQUEST_ID'] = request_id

    # Add basic security headers
    @app.after_request
    def _set_secure_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # HSTS (ok behind Render's TLS)
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains; preload")
        return resp

    # Initialize request logging middleware
    init_request_logging(app)

    # Initialise extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # --- Authentication Configuration ---
    # Respect environment variable for login enforcement
    login_disabled = ENV.get("LOGIN_DISABLED", "false").lower() in {"true", "1", "yes", "on"}
    app.config.setdefault("LOGIN_DISABLED", login_disabled)
    
    # Cookie security configuration for production
    app.config.setdefault("SESSION_COOKIE_SECURE", ENV.get("SESSION_COOKIE_SECURE", "true").lower() in {"true", "1", "yes", "on"})
    app.config.setdefault("SESSION_COOKIE_SAMESITE", ENV.get("SESSION_COOKIE_SAMESITE", "Lax"))
    app.config.setdefault("REMEMBER_COOKIE_SECURE", ENV.get("REMEMBER_COOKIE_SECURE", "true").lower() in {"true", "1", "yes", "on"})
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", ENV.get("REMEMBER_COOKIE_SAMESITE", "Lax"))
    
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
    if login_disabled:
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

    # Configure logging with stdout stream handler (avoid duplicates)
    level = (os.getenv("LOG_LEVEL") or "INFO").upper()
    app.logger.setLevel(level)

    has_stream = any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers)
    if not has_stream:
        sh = logging.StreamHandler()   # stdout on Render
        sh.setLevel(level)
        fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
        sh.setFormatter(fmt)
        app.logger.addHandler(sh)

    # optional: avoid duplicate propagation to root
    app.logger.propagate = False

    # Set up structured logging when not in debug mode.  In debug mode
    # Flask's built-in debugger provides human-readable logs.
    if not app.debug:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

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
    
    from .api.ops import ops as ops_bp
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
                res = db.session.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name='proposals' AND column_name='visitor_session_id'
                """)).scalar()
                if res != 1:
                    app.logger.error("DB not migrated: proposals.visitor_session_id missing")
                    app.logger.error("Migration doctor should have run at startup")
        except Exception as e:
            app.logger.error(f"DB probe error: {e}")

    # Add global error handler for comprehensive logging
    from flask import request, jsonify, render_template
    import traceback, uuid
    log = logging.getLogger(__name__)

    @app.errorhandler(Exception)
    def _json_errors(e):
        cid = str(uuid.uuid4())[:8]
        path = getattr(request, "path", "?")
        log.exception("EXC %s %s %s", cid, path, e)
        code = getattr(e, "code", 500)
        # Map common errors
        default = "server_error"
        name = getattr(e, "name", default) or default
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return jsonify({"error": name, "cid": cid, "request_id": request_id}), code

    # Add friendly error handlers (JSON for /api, HTML for UI)
    def _wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(400)
    def _bad_request(e):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return (jsonify(error="bad_request", detail=str(e), request_id=request_id), 400) if _wants_json() \
               else (render_template("errors/400.html"), 400)

    @app.errorhandler(404)
    def _not_found(e):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return (jsonify(error="not_found", request_id=request_id), 404) if _wants_json() \
               else (render_template("errors/404.html"), 404)

    @app.errorhandler(413)  # payload too large
    def _too_large(e):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return (jsonify(error="payload_too_large", request_id=request_id), 413) if _wants_json() \
               else (render_template("errors/413.html"), 413)

    @app.errorhandler(429)
    def _too_many(e):
        # Keep your existing limiter 429 handler if defined; otherwise:
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return (jsonify(error="rate_limited", detail=str(e.description), request_id=request_id), 429) if _wants_json() \
               else ("Rate limit exceeded. Try again shortly.", 429)

    @app.errorhandler(500)
    def _server_error(e):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return (jsonify(error="server_error", request_id=request_id), 500) if _wants_json() \
               else (render_template("errors/500.html"), 500)

    return app