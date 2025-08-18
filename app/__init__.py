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
from sqlalchemy import text

# Import centralized configuration
from .config import get_config, ConfigurationError

# Import structured logging
from .utils.logging import setup_logging, StructuredJSONFormatter

# Import extensions
from .extensions import (
    db, migrate, bcrypt, login_manager, csrf, session,
    limiter, conditional_limit, init_extensions
)

# Import models for user loader
from .models import User
import uuid

# Register models with SQLAlchemy metadata so Alembic can see them
from .models_conversion import Conversion  # noqa: F401
from .models_apikey import ApiKey  # noqa: F401

# Export extensions for use in other modules
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
    """Create Flask application with detailed startup logging."""
    import logging
    import traceback
    
    # Set up logger for create_app
    logger = logging.getLogger(__name__)
    logger.info("=== Flask App Factory Started ===")
    
    try:
        app = Flask(__name__)
        logger.info("Flask instance created")
        
        # Load configuration with error handling
        try:
            app.config["SECRET_KEY"] = ENV.get("SECRET_KEY", "changeme")
            app.config.setdefault("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)
            logger.info("Basic configuration loaded")
        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            raise
        
        # Database configuration with validation
        try:
            from .utils.db_url import normalize_db_url
            db_url = normalize_db_url(ENV.get("DATABASE_URL", ""))
            if not db_url:
                raise ValueError("DATABASE_URL is required but not provided")
            
            app.config["SQLALCHEMY_DATABASE_URI"] = db_url
            app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
            logger.info("Database configuration loaded")
        except Exception as e:
            logger.error(f"Database configuration failed: {e}")
            raise
        
        # Initialize extensions FIRST
        try:
            init_extensions(app)
            logger.info("Extensions initialized")
            
            # Test database connection
            with app.app_context():
                db.session.execute(text("SELECT 1"))
                logger.info("Database connection verified")
        except Exception as e:
            logger.error(f"Extension initialization failed: {e}")
            raise
        
        # Harden session initialization - Redis misconfig never crashes startup
        from redis import Redis
        import os
        
        url = os.getenv("SESSION_REDIS_URL") or os.getenv("REDIS_URL")
        if url:
            try:
                app.config["SESSION_TYPE"] = "redis"
                app.config["SESSION_REDIS"] = Redis.from_url(url)
                # Non-fatal probe
                try:
                    app.config["SESSION_REDIS"].ping()
                    logger.info("Redis session store configured and reachable")
                except Exception:
                    logger.warning("Session Redis unreachable; falling back to filesystem")
                    app.config["SESSION_TYPE"] = "filesystem"
            except Exception:
                logger.exception("Failed to init Redis session; falling back to filesystem")
                app.config["SESSION_TYPE"] = "filesystem"
        else:
            app.config["SESSION_TYPE"] = "filesystem"
            logger.info("No Redis URL configured; using filesystem sessions")
        
        # Set additional session configuration
        app.config.update(
            SESSION_USE_SIGNER=True,
            SESSION_KEY_PREFIX='mdraft:sess:',
            SESSION_PERMANENT=False
        )
        
        # Initialize Flask-Session
        try:
            from flask_session import Session
            Session(app)
            logger.info("Flask-Session initialized successfully")
        except Exception as e:
            logger.error(f"Flask-Session initialization failed: {e}")
            # Continue without sessions - app will still work
        
        # Rate limiting is now handled by init_extensions()
        logger.info("Rate limiting configured during extension initialization")
        
        # Register blueprints with error handling
        blueprint_errors = []
        try:
            from .auth.routes import bp as auth_bp
            app.register_blueprint(auth_bp)
            logger.info("Auth blueprint registered")
        except Exception as e:
            blueprint_errors.append(f"Auth blueprint: {e}")
        
        try:
            from .ui import bp as ui_bp
            app.register_blueprint(ui_bp)
            logger.info("UI blueprint registered")
        except Exception as e:
            blueprint_errors.append(f"UI blueprint: {e}")
        
        try:
            from .health import bp as health_bp
            app.register_blueprint(health_bp)
            logger.info("Health blueprint registered")
        except Exception as e:
            blueprint_errors.append(f"Health blueprint: {e}")
        
        try:
            from .beta import bp as beta_bp
            app.register_blueprint(beta_bp)
            logger.info("Beta blueprint registered")
        except Exception as e:
            blueprint_errors.append(f"Beta blueprint: {e}")
        
        # Add essential endpoints directly if blueprints fail
        if blueprint_errors:
            logger.warning(f"Blueprint errors: {blueprint_errors}")
            
            @app.route('/health')
            def fallback_health():
                return {"status": "degraded", "blueprint_errors": blueprint_errors}
            
            @app.route('/')
            def fallback_root():
                return {"status": "running", "note": "degraded mode"}
        
        # Initialize Flask-Login user loader
        @login_manager.user_loader
        def load_user(user_id: str):
            """Resilient user loader that supports UUID or int PKs."""
            if not user_id:
                return None
            
            # Try integer PK first (since User model uses int primary key)
            try:
                key = int(user_id)
                # SQLAlchemy 2.x preferred, with fallback
                try:
                    obj = db.session.get(User, key)
                    if obj is None:
                        # Fallback to legacy query
                        obj = User.query.get(key)
                except Exception:
                    try:
                        obj = User.query.get(key)  # legacy
                    except Exception:
                        obj = None
                return obj
            except ValueError:
                # Try UUID as fallback (for future models that might use UUID)
                try:
                    key = uuid.UUID(user_id)
                    # SQLAlchemy 2.x preferred, with fallback
                    try:
                        obj = db.session.get(User, key)
                        if obj is None:
                            # Fallback to legacy query
                            obj = User.query.get(key)
                    except Exception:
                        try:
                            obj = User.query.get(key)  # legacy
                        except Exception:
                            obj = None
                    return obj
                except ValueError:
                    return None
        
        logger.info("=== Flask App Factory Completed Successfully ===")
        return app
        
    except Exception as e:
        logger.error("=== Flask App Factory FAILED ===")
        logger.error(f"Error: {type(e).__name__}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise