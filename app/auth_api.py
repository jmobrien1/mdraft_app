import os, secrets
from datetime import datetime
from flask import request, abort
from .models_apikey import ApiKey
from . import db
from .utils.rate_limiting import get_rate_limit_key, get_upload_rate_limit_key, _get_api_key

REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "0").lower() in ("1","true","yes")

def _raw_key():
    return request.headers.get("X-API-Key") or request.args.get("api_key") or request.cookies.get("api_key")

def fetch_valid_key():
    k = _raw_key()
    if not k:
        return None
    ak = ApiKey.query.filter_by(key=k, is_active=True).first()
    if ak:
        ak.last_used_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ak
    return None

def require_api_key_if_configured():
    if REQUIRE_API_KEY and not fetch_valid_key():
        abort(401, description="missing_or_invalid_api_key")

def rate_limit_key_func():
    """
    Enhanced rate limit key function that prioritizes user_id, then API key, then IP.
    
    This function is used by Flask-Limiter to determine the rate limit key
    for the current request.
    """
    return get_rate_limit_key()

def rate_limit_for_convert():
    """
    Get the rate limit string for conversion endpoints.
    
    Returns:
        Rate limit string (e.g., "20 per minute")
    """
    # Check if user has a custom rate limit via API key
    ak = fetch_valid_key()
    if ak and ak.rate_limit:
        return ak.rate_limit
    
    # Get default rate limit from configuration
    from .config import get_config
    config = get_config()
    return config.get_rate_limit("convert")

def rate_limit_for_upload():
    """
    Get the rate limit string for upload endpoints.
    
    Returns:
        Rate limit string (e.g., "20 per minute" for authenticated, "10 per minute" for anonymous)
    """
    # Check if user has a custom rate limit via API key
    ak = fetch_valid_key()
    if ak and ak.rate_limit:
        return ak.rate_limit
    
    # Get default rate limit from configuration
    from .config import get_config
    config = get_config()
    
    # Use different limits for authenticated vs anonymous users
    if hasattr(request, 'user') and request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated:
        return config.get_rate_limit("convert")  # Same as convert for authenticated users
    else:
        # Stricter limit for anonymous users
        return "10 per minute"

def generate_key():
    # 48 chars urlsafe by default; enough entropy + fits DB
    return secrets.token_urlsafe(36)
