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
        
        # Initialize database FIRST
        try:
            db.init_app(app)
            migrate.init_app(app, db)
            logger.info("Database extensions initialized")
            
            # Test database connection
            with app.app_context():
                db.session.execute(text("SELECT 1"))
                logger.info("Database connection verified")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        
        # Initialize Redis with complete fallback
        redis_client = None
        try:
            redis_url = ENV.get("REDIS_URL") or ENV.get("SESSION_REDIS_URL")
            if redis_url:
                # Ensure correct scheme
                if redis_url.startswith("rediss://"):
                    logger.warning("Converting rediss:// to redis://")
                    redis_url = redis_url.replace("rediss://", "redis://")
                
                import redis
                redis_client = redis.from_url(redis_url, socket_connect_timeout=5)
                redis_client.ping()
                logger.info("Redis connection established")
            else:
                logger.warning("No Redis URL configured")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            redis_client = None
        
        # Session configuration with fallback
        try:
            if redis_client:
                app.config.update(
                    SESSION_TYPE='redis',
                    SESSION_REDIS=redis_client,
                    SESSION_USE_SIGNER=True,
                    SESSION_KEY_PREFIX='mdraft:sess:',
                    SESSION_PERMANENT=False
                )
                logger.info("Using Redis for sessions")
            else:
                app.config.update(
                    SESSION_TYPE='filesystem',
                    SESSION_USE_SIGNER=True,
                    SESSION_PERMANENT=False
                )
                logger.info("Using filesystem for sessions")
            
            from flask_session import Session
            Session(app)
            logger.info("Flask-Session initialized")
        except Exception as e:
            logger.error(f"Session initialization failed: {e}")
            # Continue without sessions
        
        # Rate limiting with fallback
        try:
            limiter_storage = redis_url if redis_client else "memory://"
            limiter.init_app(app)
            logger.info(f"Rate limiting initialized with {limiter_storage}")
        except Exception as e:
            logger.warning(f"Rate limiting initialization failed: {e}")
        
        # Initialize other extensions
        try:
            bcrypt.init_app(app)
            login_manager.init_app(app)
            logger.info("Authentication extensions initialized")
        except Exception as e:
            logger.error(f"Auth extension initialization failed: {e}")
            raise
        
        # Register blueprints with error handling
        blueprint_errors = []
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
        
        logger.info("=== Flask App Factory Completed Successfully ===")
        return app
        
    except Exception as e:
        logger.error("=== Flask App Factory FAILED ===")
        logger.error(f"Error: {type(e).__name__}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise