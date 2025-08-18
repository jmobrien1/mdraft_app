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

# Flask-Login configuration
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"


class AnonymousUser(AnonymousUserMixin):
    """Custom anonymous user class with safe defaults for templates."""
    
    @property
    def name(self) -> str | None:
        """Return None for anonymous users."""
        return None
    
    @property
    def is_admin(self) -> bool:
        """Anonymous users are never admin."""
        return False
    
    @property
    def email(self) -> str | None:
        """Return None for anonymous users."""
        return None
    
    @property
    def id(self) -> None:
        """Return None for anonymous users."""
        return None
    
    def __repr__(self) -> str:
        return "<AnonymousUser>"


# Set the anonymous user class
login_manager.anonymous_user = AnonymousUser


def init_extensions(app):
    """Initialize all Flask extensions with the application."""
    # Initialize database extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize authentication extensions
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Initialize rate limiting
    global _limiter_initialized
    try:
        limiter.init_app(app)
        _limiter_initialized = True
    except Exception:
        # Rate limiting will be disabled if initialization fails
        _limiter_initialized = False
    
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
