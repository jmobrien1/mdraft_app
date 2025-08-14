"""
Authentication utilities for handling anonymous and authenticated users.
"""
from typing import Optional
from flask_login import current_user


def get_request_user_id_or_none() -> Optional[int]:
    """
    Safely get the current user ID, returning None for anonymous users.
    
    This prevents crashes when current_user.id is accessed on anonymous users.
    Use this instead of direct current_user.id access in endpoints that should
    work for both authenticated and anonymous users.
    
    Returns:
        User ID if authenticated, None if anonymous
    """
    try:
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "id", None)
    except Exception:
        # Handle any unexpected errors gracefully
        pass
    return None


def is_user_authenticated() -> bool:
    """
    Check if the current user is authenticated.
    
    Returns:
        True if user is authenticated, False otherwise
    """
    try:
        return getattr(current_user, "is_authenticated", False)
    except Exception:
        return False


def require_authentication():
    """
    Decorator factory for endpoints that require authentication.
    
    This is a more explicit alternative to @login_required that provides
    better error messages and logging.
    """
    from functools import wraps
    from flask import jsonify
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_user_authenticated():
                return jsonify({
                    "error": "Authentication required",
                    "message": "This endpoint requires a logged-in user"
                }), 401
            return f(*args, **kwargs)
        return decorated_function
    return decorator
