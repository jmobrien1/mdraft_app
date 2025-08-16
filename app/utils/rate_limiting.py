"""
Rate limiting utilities for fine-grained API security.

This module provides key functions for Flask-Limiter that support
user_id, API key, and IP-based rate limiting with fallback logic.
"""

from flask import request, current_app
from flask_login import current_user
from typing import Optional, Tuple
import hashlib
import time
from collections import defaultdict


def get_rate_limit_key() -> str:
    """
    Get the primary rate limit key for the current request.
    
    Priority order:
    1. Authenticated user ID (if logged in)
    2. API key (if present in headers/args/cookies)
    3. Client IP address (fallback)
    
    Returns:
        String key for rate limiting
    """
    # Check for authenticated user first
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return f"user:{current_user.id}"
    
    # Check for API key
    api_key = _get_api_key()
    if api_key:
        return f"apikey:{api_key}"
    
    # Fallback to IP address
    return f"ip:{_get_client_ip()}"


def get_combined_rate_limit_key() -> str:
    """
    Get a combined rate limit key that includes both user/API key and IP.
    
    This is useful for endpoints that need both per-user and per-IP limits.
    
    Returns:
        String key combining user/API key and IP
    """
    # Get the primary identifier
    primary_id = get_rate_limit_key()
    
    # Get IP address
    ip = _get_client_ip()
    
    # Combine them
    return f"{primary_id}:{ip}"


def get_login_rate_limit_key() -> str:
    """
    Get rate limit key specifically for login attempts.
    
    Uses username + IP combination to prevent both targeted attacks
    and IP-based brute force attempts.
    
    Returns:
        String key for login rate limiting
    """
    # Get username from form data
    username = request.form.get("email", "").strip().lower()
    if not username:
        username = "unknown"
    
    # Get IP address
    ip = _get_client_ip()
    
    # Combine username and IP
    return f"login:{username}:{ip}"


def get_upload_rate_limit_key() -> str:
    """
    Get rate limit key specifically for upload endpoints.
    
    For authenticated users: user_id
    For API key users: API key
    For anonymous users: IP address
    
    Returns:
        String key for upload rate limiting
    """
    # Check for authenticated user first
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return f"upload:user:{current_user.id}"
    
    # Check for API key
    api_key = _get_api_key()
    if api_key:
        return f"upload:apikey:{api_key}"
    
    # Fallback to IP address for anonymous users
    return f"upload:ip:{_get_client_ip()}"


def get_index_rate_limit_key() -> str:
    """
    Get rate limit key for the index endpoint.
    
    Uses IP address only since this is a public endpoint.
    
    Returns:
        String key for index rate limiting
    """
    return f"index:ip:{_get_client_ip()}"


def _get_api_key() -> Optional[str]:
    """
    Extract API key from request headers, query parameters, or cookies.
    
    Returns:
        API key string if found, None otherwise
    """
    # Check headers first (most common for API usage)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    
    # Check query parameters
    api_key = request.args.get("api_key")
    if api_key:
        return api_key
    
    # Check cookies (least common, but supported)
    api_key = request.cookies.get("api_key")
    if api_key:
        return api_key
    
    return None


def _get_client_ip() -> str:
    """
    Get the client IP address with support for proxies.
    
    Returns:
        Client IP address string
    """
    # Check for forwarded headers (common with proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to remote address
    return request.remote_addr or "unknown"


# Public alias for _get_client_ip
def get_client_ip() -> str:
    """
    Get the client IP address with support for proxies.
    
    Returns:
        Client IP address string
    """
    return _get_client_ip()


class AuthRateLimiter:
    """
    Rate limiter for authentication attempts with configurable thresholds.
    
    This class provides rate limiting for login attempts with separate
    tracking for username and IP address to prevent both targeted
    and brute force attacks.
    """
    
    def __init__(self, config):
        """
        Initialize the rate limiter with configuration.
        
        Args:
            config: Application configuration object
        """
        self.max_fails = config.security.AUTH_MAX_FAILS
        self.fail_window = config.security.AUTH_FAIL_WINDOW_SEC
        self.lockout_minutes = config.security.AUTH_LOCKOUT_MINUTES
        
        # In-memory storage for failed attempts
        # In production, this should use Redis or database
        self.failed_attempts = defaultdict(list)
        self.lockouts = {}
    
    def check_auth_attempt(self, identifier: str, identifier_type: str) -> Tuple[bool, str]:
        """
        Check if an authentication attempt is allowed.
        
        Args:
            identifier: Username or IP address
            identifier_type: "username" or "ip"
            
        Returns:
            Tuple of (allowed, message)
        """
        current_time = time.time()
        
        # Check if identifier is currently locked out
        lockout_key = f"{identifier_type}:{identifier}"
        if lockout_key in self.lockouts:
            lockout_until = self.lockouts[lockout_key]
            if current_time < lockout_until:
                remaining = int(lockout_until - current_time)
                return False, f"Account temporarily locked. Try again in {remaining} seconds."
            else:
                # Lockout expired, remove it
                del self.lockouts[lockout_key]
        
        # Clean old failed attempts outside the window
        window_start = current_time - self.fail_window
        self.failed_attempts[identifier] = [
            attempt_time for attempt_time in self.failed_attempts[identifier]
            if attempt_time > window_start
        ]
        
        # Check if too many failed attempts
        if len(self.failed_attempts[identifier]) >= self.max_fails:
            # Lock out the identifier
            lockout_until = current_time + (self.lockout_minutes * 60)
            self.lockouts[lockout_key] = lockout_until
            return False, f"Too many failed attempts. Account locked for {self.lockout_minutes} minutes."
        
        return True, "Authentication attempt allowed."
    
    def record_failed_attempt(self, identifier: str) -> None:
        """
        Record a failed authentication attempt.
        
        Args:
            identifier: Username or IP address
        """
        self.failed_attempts[identifier].append(time.time())
    
    def record_successful_attempt(self, identifier: str, identifier_type: str) -> None:
        """
        Record a successful authentication attempt and clear failed attempts.
        
        Args:
            identifier: Username or IP address
            identifier_type: "username" or "ip"
        """
        # Clear failed attempts for this identifier
        self.failed_attempts[identifier] = []
        
        # Clear any lockout for this identifier
        lockout_key = f"{identifier_type}:{identifier}"
        if lockout_key in self.lockouts:
            del self.lockouts[lockout_key]


def create_auth_rate_limiter(config) -> AuthRateLimiter:
    """
    Create an authentication rate limiter instance.
    
    Args:
        config: Application configuration object
        
    Returns:
        AuthRateLimiter instance
    """
    return AuthRateLimiter(config)


def get_rate_limit_identifier() -> Tuple[str, str]:
    """
    Get both the rate limit key and the identifier type for logging.
    
    Returns:
        Tuple of (rate_limit_key, identifier_type)
    """
    # Check for authenticated user first
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return f"user:{current_user.id}", "user_id"
    
    # Check for API key
    api_key = _get_api_key()
    if api_key:
        # Hash the API key for logging to avoid exposure
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()[:8]
        return f"apikey:{hashed_key}", "api_key"
    
    # Fallback to IP address
    ip = _get_client_ip()
    return f"ip:{ip}", "ip_address"


def validate_rate_limit_key(key: str) -> bool:
    """
    Validate that a rate limit key is properly formatted.
    
    Args:
        key: Rate limit key to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not key or not isinstance(key, str):
        return False
    
    # Check for expected prefixes
    valid_prefixes = ["user:", "apikey:", "ip:", "login:", "upload:", "index:"]
    return any(key.startswith(prefix) for prefix in valid_prefixes)


def get_rate_limit_info() -> dict:
    """
    Get comprehensive rate limit information for the current request.
    
    Returns:
        Dictionary with rate limit details
    """
    key, identifier_type = get_rate_limit_identifier()
    
    info = {
        "rate_limit_key": key,
        "identifier_type": identifier_type,
        "client_ip": _get_client_ip(),
        "user_authenticated": hasattr(current_user, 'is_authenticated') and current_user.is_authenticated,
    }
    
    if info["user_authenticated"]:
        info["user_id"] = current_user.id
    
    api_key = _get_api_key()
    if api_key:
        info["has_api_key"] = True
        info["api_key_hash"] = hashlib.sha256(api_key.encode()).hexdigest()[:8]
    else:
        info["has_api_key"] = False
    
    return info
