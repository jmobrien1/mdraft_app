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

# Initialise extensions without an application context.  They will be
# bound to the app inside create_app().
db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
limiter: Limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("FLASK_LIMITER_STORAGE_URI") or os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL"),
    default_limits=["120 per minute"],  # adjust later
)
bcrypt: Bcrypt = Bcrypt()
login_manager: LoginManager = LoginManager()

# Register models with SQLAlchemy metadata so Alembic can see them
from .models_conversion import Conversion  # noqa: F401


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
            corr_id = request.environ.get("HTTP_X_REQUEST_ID", "N/A")
            # Add request-specific context
            log_data["request_id"] = corr_id
            log_data["task_name"] = request.headers.get("X-Cloud-Tasks-TaskName", "N/A")
            log_data["queue_name"] = request.headers.get("X-Cloud-Tasks-QueueName", "N/A")
            log_data["job_id"] = request.headers.get("X-Job-ID", "N/A")
        else:
            corr_id = "N/A"
        log_data["correlation_id"] = corr_id
        # Include the name of the logger to aid in filtering.
        log_data["logger"] = record.name
        # Append any extra context stored in the record.
        if record.args:
            log_data["args"] = record.args
        return json.dumps(log_data)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Application configuration
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "changeme")
    app.config.setdefault("MAX_CONTENT_LENGTH", 20 * 1024 * 1024)  # 20 MB
    
    # Database configuration
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mdraft_local.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Google Cloud Storage configuration
    app.config["GCS_BUCKET_NAME"] = os.environ.get("GCS_BUCKET_NAME")
    app.config["GCS_PROCESSED_BUCKET_NAME"] = os.environ.get("GCS_PROCESSED_BUCKET_NAME")
    
    # Google Cloud Tasks configuration
    app.config["CLOUD_TASKS_QUEUE_ID"] = os.environ.get("CLOUD_TASKS_QUEUE_ID")
    app.config["CLOUD_TASKS_LOCATION"] = os.environ.get("CLOUD_TASKS_LOCATION", "us-central1")
    
    # Document AI configuration
    app.config["DOCAI_PROCESSOR_ID"] = os.environ.get("DOCAI_PROCESSOR_ID")
    app.config["DOCAI_LOCATION"] = os.environ.get("DOCAI_LOCATION", "us")
    
    # Sentry configuration
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[
                    FlaskIntegration(),
                    SqlalchemyIntegration(),
                ],
                traces_sample_rate=0.1,
                environment=os.environ.get("FLASK_ENV", "production"),
            )
            app.logger.info("Sentry initialized successfully")
        except ImportError:
            app.logger.warning("Sentry SDK not available, skipping Sentry initialization")
        except Exception as e:
            app.logger.error(f"Failed to initialize Sentry: {e}")
    
    # Rate limiting is configured at the module level with Redis storage

    # Initialise extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # --- Demo-safe auth disable (Flask-Login) ---
    # We don't need authentication for the beta UI. Prevent Flask-Login
    # from raising "Missing user_loader or request_loader".
    app.config.setdefault("LOGIN_DISABLED", True)
    try:
        # If a LoginManager was attached, give it a no-op user_loader.
        lm = getattr(app, "login_manager", None)
        if lm is not None and getattr(lm, "user_callback", None) is None and getattr(lm, "request_callback", None) is None:
            @lm.user_loader
            def _noop_user_loader(_):
                return None
    except Exception:
        pass
    # --- end auth disable ---

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

    from .routes import bp as main_blueprint  # type: ignore
    app.register_blueprint(main_blueprint)
    
    # Register worker blueprint if running as worker service
    if os.environ.get("WORKER_SERVICE", "false").lower() == "true":
        from .worker_routes import worker_bp as worker_blueprint  # type: ignore
        app.register_blueprint(worker_blueprint)
        
        # Initialize Cloud Tasks queue if needed
        from .tasks import create_queue_if_not_exists
        with app.app_context():
            create_queue_if_not_exists()

    return app