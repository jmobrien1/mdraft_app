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
limiter: Limiter = Limiter(key_func=get_remote_address)
bcrypt: Bcrypt = Bcrypt()
login_manager: LoginManager = LoginManager()


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
    
    # Configure rate limiting defaults.  Additional per-route limits can be
    # applied via decorators on view functions.
    app.config.setdefault("RATELIMIT_DEFAULT", "200 per day")

    # Initialise extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

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
    from .routes import bp as main_blueprint  # type: ignore

    app.register_blueprint(main_blueprint)

    return app