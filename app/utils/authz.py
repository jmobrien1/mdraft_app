import os
from flask import request
from flask_login import current_user


def allow_session_or_api_key():
    """Allow access if user has authenticated session or valid internal API key.
    
    Returns:
        bool: True if authenticated via session or valid internal API key
    """
    # Session path - check if user is authenticated
    if getattr(current_user, "is_authenticated", False):
        return True
    
    # API key path (server-to-server only) - check internal API key
    sent = request.headers.get("x-api-key")
    real = os.environ.get("INTERNAL_API_KEY")
    return bool(sent and real and sent == real)
