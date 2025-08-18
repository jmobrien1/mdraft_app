import os
from flask import request
from flask_login import current_user


def allow_session_or_api_key():
    """Allow access if user has authenticated session, valid internal API key, or visitor session.
    
    Returns:
        bool: True if authenticated via session, valid internal API key, or has visitor session
    """
    # Session path - check if user is authenticated
    if getattr(current_user, "is_authenticated", False):
        return True
    
    # API key path (server-to-server only) - check internal API key
    sent = request.headers.get("x-api-key")
    real = os.environ.get("INTERNAL_API_KEY")
    if sent and real and sent == real:
        return True
    
    # Visitor session path - allow anonymous users with visitor sessions
    from app.auth.visitor import get_visitor_session_id
    visitor_id = get_visitor_session_id()
    if visitor_id:
        return True
    
    # Check for visitor session cookie (for new requests)
    visitor_cookie = request.cookies.get("visitor_session_id")
    if visitor_cookie:
        return True
    
    return False
