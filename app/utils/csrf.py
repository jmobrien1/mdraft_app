"""
CSRF protection utilities for mdraft.

This module provides decorators and utilities for managing CSRF protection
in the application, particularly for API routes that should be exempt from
CSRF validation when using proper authentication.
"""

import logging
from functools import wraps
from flask import request, current_app
from flask_wtf.csrf import CSRFProtect

logger = logging.getLogger(__name__)


def is_api_request(request) -> bool:
    """
    Determine if a request is an API request that should be exempt from CSRF protection.
    
    An API request is defined as:
    1. Content-Type is application/json, OR
    2. Has Authorization header with Bearer token, OR  
    3. Has X-API-Key header
    
    This provides an explicit allowlist predicate for CSRF exemptions.
    
    Args:
        request: Flask request object
        
    Returns:
        bool: True if request should be exempt from CSRF protection
    """
    # Check for JSON content type
    content_type = request.headers.get('Content-Type', '')
    is_json_request = 'application/json' in content_type.lower()
    
    # Check for Bearer token authentication (must have non-empty token)
    auth_header = request.headers.get('Authorization', '')
    has_bearer_token = auth_header.startswith('Bearer ') and len(auth_header) > 7
    
    # Check for API key authentication (must have non-empty key)
    api_key = request.headers.get('X-API-Key', '')
    has_api_key = bool(api_key and api_key.strip())
    
    # Request is exempt if it's JSON or has proper authentication
    is_exempt = is_json_request or has_bearer_token or has_api_key
    
    if is_exempt:
        logger.debug(
            "CSRF exemption granted",
            extra={
                "path": request.path,
                "method": request.method,
                "content_type": content_type,
                "has_bearer": has_bearer_token,
                "has_api_key": has_api_key,
                "exemption_reason": "API request with proper authentication"
            }
        )
    
    return is_exempt


def csrf_exempt_api(f):
    """
    Decorator to exempt API routes from CSRF protection.
    
    This decorator uses the is_api_request() helper to determine if a request
    should be exempt from CSRF validation. Only requests that meet the explicit
    allowlist criteria (JSON content type, Bearer token, or API key) are exempt.
    
    Usage:
        @app.route('/api/endpoint', methods=['POST'])
        @csrf_exempt_api
        def api_endpoint():
            return jsonify({'status': 'success'})
    
    Security:
        - Forms (application/x-www-form-urlencoded) still require CSRF tokens
        - Only API requests with proper authentication are exempt
        - Provides logging for audit trail of exemptions
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_api_request(request):
            # Exempt this request from CSRF validation
            csrf = current_app.extensions.get('csrf')
            if csrf:
                csrf.exempt(request)
                logger.info(
                    "CSRF exemption applied",
                    extra={
                        "endpoint": f.__name__,
                        "path": request.path,
                        "method": request.method,
                        "remote_addr": request.remote_addr
                    }
                )
        else:
            logger.debug(
                "CSRF protection maintained",
                extra={
                    "endpoint": f.__name__,
                    "path": request.path,
                    "method": request.method,
                    "content_type": request.headers.get('Content-Type', ''),
                    "reason": "Request does not meet API exemption criteria"
                }
            )
        
        return f(*args, **kwargs)
    return decorated_function


# Legacy functions for backward compatibility (deprecated)
def csrf_exempt(f):
    """
    DEPRECATED: Use @csrf_exempt_api instead.
    
    This decorator unconditionally exempts routes from CSRF protection.
    It should only be used for API routes that use proper authentication.
    """
    import warnings
    warnings.warn(
        "csrf_exempt is deprecated. Use csrf_exempt_api for API routes.",
        DeprecationWarning,
        stacklevel=2
    )
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Exempt this request from CSRF validation
        csrf = current_app.extensions.get('csrf')
        if csrf:
            csrf.exempt(request)
        return f(*args, **kwargs)
    return decorated_function


def csrf_exempt_for_api(f):
    """
    DEPRECATED: Use @csrf_exempt_api instead.
    
    This decorator checks for Bearer tokens or API keys and only exempts
    the route if proper authentication is present.
    """
    import warnings
    warnings.warn(
        "csrf_exempt_for_api is deprecated. Use csrf_exempt_api instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for proper authentication
        auth_header = request.headers.get("Authorization", "")
        has_bearer_token = auth_header.startswith("Bearer ")
        has_api_key = request.headers.get("X-API-Key") is not None
        
        if has_bearer_token or has_api_key:
            # Exempt this request from CSRF validation
            csrf = current_app.extensions.get('csrf')
            if csrf:
                csrf.exempt(request)
        
        return f(*args, **kwargs)
    return decorated_function


def exempt_csrf_for_request():
    """
    DEPRECATED: Use @csrf_exempt_api decorator instead.
    
    Exempt the current request from CSRF validation.
    This function should be called from within a route handler
    when the request should be exempt from CSRF validation.
    """
    import warnings
    warnings.warn(
        "exempt_csrf_for_request is deprecated. Use @csrf_exempt_api decorator instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    csrf = current_app.extensions.get('csrf')
    if csrf:
        csrf.exempt(request)


def should_exempt_csrf():
    """
    DEPRECATED: Use is_api_request() instead.
    
    Determine if the current request should be exempt from CSRF protection.
    
    Returns True if the request should be exempt, False otherwise.
    """
    import warnings
    warnings.warn(
        "should_exempt_csrf is deprecated. Use is_api_request() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return is_api_request(request)
