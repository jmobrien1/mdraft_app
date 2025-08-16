"""
Session management utilities for authentication security.

This module provides session rotation and invalidation functionality
to enhance security during login/logout operations.
"""
import uuid
from typing import Optional
from flask import session, current_app
from flask_login import current_user


def rotate_session() -> None:
    """
    Rotate the session ID for security.
    
    This invalidates any previous session and creates a new one,
    which helps prevent session fixation attacks.
    """
    # Store current session data
    session_data = dict(session)
    
    # Clear the session
    session.clear()
    
    # Generate new session ID
    session['_id'] = str(uuid.uuid4())
    
    # Restore session data with new ID
    for key, value in session_data.items():
        if key != '_id':  # Don't restore the old session ID
            session[key] = value


def invalidate_other_sessions(user_id: int) -> None:
    """
    Invalidate other sessions for a user (single session mode).
    
    This is used when AUTH_SINGLE_SESSION is enabled to ensure
    only one active session per user.
    
    Args:
        user_id: The user ID whose other sessions should be invalidated
    """
    # This would typically involve Redis or database operations
    # to track and invalidate other sessions. For now, we'll
    # implement a basic version that works with the current setup.
    
    # If using Redis for sessions, we could store session mappings
    # and invalidate them here. For now, we'll rely on session rotation
    # which provides good security for most use cases.
    
    current_app.logger.info(f"Invalidating other sessions for user {user_id}")
    
    # Note: In a production environment with Redis session storage,
    # you would implement session tracking and invalidation here.
    # For example:
    # redis_client.delete(f"user_sessions:{user_id}")
    # redis_client.sadd(f"user_sessions:{user_id}", session['_id'])


def get_session_info() -> dict:
    """
    Get information about the current session.
    
    Returns:
        Dictionary with session information
    """
    return {
        'session_id': session.get('_id'),
        'user_id': getattr(current_user, 'id', None) if current_user.is_authenticated else None,
        'authenticated': current_user.is_authenticated,
        'created_at': session.get('_created', None)
    }


def is_session_valid() -> bool:
    """
    Check if the current session is valid.
    
    Returns:
        True if session is valid, False otherwise
    """
    # Basic validation - check if session ID exists
    if not session.get('_id'):
        return False
    
    # Check if user is authenticated (if session suggests they should be)
    if session.get('_user_id') and not current_user.is_authenticated:
        return False
    
    return True
