"""
Flask extensions for the mdraft application.

This module centralizes the initialization and configuration of Flask
extensions, providing a clean separation of concerns and making it
easier to manage extension dependencies.
"""
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, AnonymousUserMixin
from flask_wtf.csrf import CSRFProtect
from flask_session import Session

# Initialize extensions without an application context
db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
bcrypt: Bcrypt = Bcrypt()
csrf: CSRFProtect = CSRFProtect()
# Note: session will be initialized after configuration is set
session: Session | None = None

# Global limiter (exported as app.limiter so routes can import it)
# Initialize with safe defaults - will be configured during app creation
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"],
)

# Global flag to track if limiter is properly initialized
_limiter_initialized = False

login_manager = LoginManager()
login_manager.login_view = "auth.login"      # change if your login route differs
login_manager.session_protection = "strong"

class _Anonymous(AnonymousUserMixin):
    # Keep templates from blowing up when current_user is anonymous
    @property
    def name(self): return None
    @property
    def is_admin(self): return False

login_manager.anonymous_user = _Anonymous

@login_manager.unauthorized_handler
def _api_unauthorized():
    """Handle unauthorized access - return JSON for API calls, redirect for web."""
    from flask import request, jsonify, redirect, url_for
    
    # if it's an API call, don't redirect — return 401 JSON
    if request.path.startswith("/api/"):
        return jsonify(error="unauthorized"), 401
    # otherwise do the normal redirect
    return redirect(url_for("auth.login"))


def init_extensions(app):
    """Initialize all Flask extensions with the application."""
    # Initialize database extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize authentication extensions
    bcrypt.init_app(app)
    csrf.init_app(app)
    
    # Initialize rate limiting with Redis storage configuration
    global _limiter_initialized
    try:
        # Configure the global limiter instance with Redis storage
        import os
        storage_uri = os.getenv("FLASK_LIMITER_STORAGE_URI", "memory://")
        if storage_uri and storage_uri != "memory://":
            limiter.storage_uri = storage_uri
            app.logger.info(f"Flask-Limiter configured with Redis storage: {storage_uri}")
        else:
            app.logger.warning("Flask-Limiter using in-memory storage (set FLASK_LIMITER_STORAGE_URI for Redis)")
        
        # Set default limits from environment
        default_limit = os.getenv("GLOBAL_RATE_LIMIT", "120 per minute")
        limiter.default_limits = [default_limit]
        
        limiter.init_app(app)
        _limiter_initialized = True
        app.logger.info("Flask-Limiter initialized successfully")
    except Exception as e:
        # Don't reassign limiter - just disable it by setting storage to memory
        limiter.storage_uri = "memory://"
        limiter.default_limits = []  # No limits when disabled
        _limiter_initialized = False
        app.logger.warning(f"Flask-Limiter initialization failed, using memory storage: {e}")
    
    # Initialize session (will be configured in create_app)
    # Session initialization is handled separately due to Redis dependency


def conditional_limit(limit_string: str):
    """Apply rate limit only if limiter is enabled."""
    try:
        if _limiter_initialized and limiter and limiter.default_limits:
            return limiter.limit(limit_string)
    except Exception:
        # If limiter.limit() fails, fall back to no-op
        pass
    return lambda f: f  # No-op decorator


# Export all extensions for use in other modules
__all__ = [
    'db', 'migrate', 'bcrypt', 'login_manager', 'csrf', 'session',
    'limiter', 'conditional_limit', 'init_extensions'
]
