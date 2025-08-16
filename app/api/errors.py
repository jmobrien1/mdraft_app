"""
Unified error handling for the mdraft application.

This module provides comprehensive error handlers that:
- Return safe JSON responses (no tracebacks)
- Include request IDs for correlation (always computed if missing)
- Log structured JSON with context
- Capture exceptions in Sentry when configured (with safe error handling)
- Map HTTPException names to error codes
- Handle common database, timeout, and circuit breaker errors
"""
import logging
import os
import uuid
from typing import Dict, Any, Optional, Tuple
from flask import Blueprint, jsonify, request, current_app
from werkzeug.exceptions import (
    HTTPException, BadRequest, Unauthorized, Forbidden, NotFound, 
    InternalServerError, MethodNotAllowed, RequestEntityTooLarge, 
    TooManyRequests, Conflict, UnprocessableEntity, UnsupportedMediaType
)

# Initialize logger for this module
logger = logging.getLogger(__name__)

errors = Blueprint("errors", __name__)


def _get_request_id() -> str:
    """Extract request ID from environment or generate one if missing.
    
    Always returns a valid request ID. Never assumes header exists.
    Falls back to UUID generation if environment variable is missing.
    """
    # Try to get from environment (set by middleware)
    request_id = request.environ.get('X-Request-ID')
    if request_id:
        return request_id
    
    # Try to get from headers as fallback
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Request-Id')
    if request_id:
        # Validate UUID format
        try:
            uuid.UUID(request_id)
            return request_id
        except (ValueError, TypeError):
            pass
    
    # Generate new UUID if no valid request ID found
    new_request_id = str(uuid.uuid4())
    logger.warning("No valid request ID found, generated new UUID", extra={
        "generated_request_id": new_request_id,
        "method": request.method,
        "path": request.path
    })
    return new_request_id


def _get_user_id() -> Optional[str]:
    """Extract user ID if available."""
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            return str(current_user.id)
    except Exception:
        pass
    return None


def _log_error(level: str, path: str, status: int, request_id: str, user_id: Optional[str], 
               error_name: str, detail: str, exception: Optional[Exception] = None) -> None:
    """Log structured JSON error information."""
    log_data: Dict[str, Any] = {
        "level": level,
        "path": path,
        "status": status,
        "request_id": request_id,
        "user_id": user_id or "anonymous",
        "error": error_name,
        "detail": detail
    }
    
    if exception:
        log_data["exception_type"] = type(exception).__name__
    
    logger.log(
        getattr(logging, level.upper()),
        "Error occurred",
        extra=log_data
    )


def _capture_sentry_exception(exception: Exception, request_id: str, user_id: Optional[str]) -> None:
    """Capture exception in Sentry if DSN is configured.
    
    Wraps all Sentry operations in try/except to prevent telemetry failures
    from breaking error responses.
    """
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if not sentry_dsn:
        return
    
    try:
        import sentry_sdk
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("request_id", request_id)
            if user_id:
                scope.set_user({"id": user_id})
            scope.set_context("request", {
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers)
            })
        sentry_sdk.capture_exception(exception)
    except Exception as e:
        # Don't let Sentry errors break error handling
        logger.warning("Failed to capture exception in Sentry", extra={
            "sentry_error": str(e),
            "sentry_error_type": type(e).__name__,
            "original_request_id": request_id,
            "original_exception": type(exception).__name__
        })


def _create_error_response(error_name: str, detail: str, status: int, 
                          request_id: str, user_id: Optional[str], 
                          exception: Optional[Exception] = None) -> tuple:
    """Create standardized error response and log it.
    
    Returns consistent JSON format: {error, message, request_id}
    """
    path = getattr(request, 'path', 'unknown')
    
    # Log the error
    _log_error("ERROR", path, status, request_id, user_id, error_name, detail, exception)
    
    # Capture in Sentry if it's an exception (with safe error handling)
    if exception:
        _capture_sentry_exception(exception, request_id, user_id)
    
    # Return safe JSON response with standardized format
    return jsonify({
        "error": error_name,
        "message": detail,  # Changed from 'detail' to 'message' for consistency
        "request_id": request_id
    }), status


def _map_exception_to_error(exception: Exception) -> Tuple[str, str, int]:
    """Map exception to standardized error response.
    
    Comprehensive mapping covering:
    - HTTP exceptions (400, 401, 403, 404, 405, 409, 413, 415, 422, 429, 500)
    - Database exceptions (IntegrityError, OperationalError, TimeoutError)
    - Storage exceptions (StorageError, StorageTimeoutError)
    - Network exceptions (ConnectionError, TimeoutError)
    - Circuit breaker exceptions
    """
    if isinstance(exception, HTTPException):
        status = exception.code or 500
        # Comprehensive HTTPException name mapping
        name_mapping = {
            "Bad Request": "bad_request",
            "Unauthorized": "unauthorized", 
            "Forbidden": "forbidden",
            "Not Found": "not_found",
            "Method Not Allowed": "method_not_allowed",
            "Conflict": "conflict",
            "Request Entity Too Large": "payload_too_large",
            "Unsupported Media Type": "unsupported_media_type",
            "Unprocessable Entity": "unprocessable_entity",
            "Too Many Requests": "rate_limited",
            "Internal Server Error": "internal_error"
        }
        error_name = name_mapping.get(exception.name, "http_error")
        detail = getattr(exception, 'description', str(exception))
        return error_name, detail, status
    
    # Database exceptions
    try:
        from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError as SQLTimeoutError
        if isinstance(exception, IntegrityError):
            return "database_integrity_error", "Database constraint violation", 409
        elif isinstance(exception, OperationalError):
            return "database_connection_error", "Database connection failed", 503
        elif isinstance(exception, SQLTimeoutError):
            return "database_timeout_error", "Database operation timed out", 504
    except ImportError:
        pass
    
    # Storage exceptions
    try:
        from app.services.storage import StorageError, StorageTimeoutError
        if isinstance(exception, StorageTimeoutError):
            return "storage_timeout_error", "Storage operation timed out", 504
        elif isinstance(exception, StorageError):
            return "storage_error", "Storage operation failed", 503
    except ImportError:
        pass
    
    # Network and timeout exceptions
    if isinstance(exception, TimeoutError):
        return "timeout_error", "Operation timed out", 504
    elif isinstance(exception, ConnectionError):
        return "connection_error", "Connection failed", 503
    
    # Circuit breaker exceptions (if using circuit breaker pattern)
    if hasattr(exception, '__class__') and 'CircuitBreaker' in exception.__class__.__name__:
        return "circuit_breaker_open", "Service temporarily unavailable", 503
    
    # Generic exception handling
    return "internal_error", "Internal server error", 500


@errors.app_errorhandler(400)
def handle_bad_request(e):
    """Handle 400 Bad Request errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(401)
def handle_unauthorized(e):
    """Handle 401 Unauthorized errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(403)
def handle_forbidden(e):
    """Handle 403 Forbidden errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(404)
def handle_not_found(e):
    """Handle 404 Not Found errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(405)
def handle_method_not_allowed(e):
    """Handle 405 Method Not Allowed errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(409)
def handle_conflict(e):
    """Handle 409 Conflict errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(413)
def handle_payload_too_large(e):
    """Handle 413 Payload Too Large errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(415)
def handle_unsupported_media_type(e):
    """Handle 415 Unsupported Media Type errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(422)
def handle_unprocessable_entity(e):
    """Handle 422 Unprocessable Entity errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(429)
def handle_rate_limited(e):
    """Handle 429 Too Many Requests errors."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(500)
def handle_internal_server_error(e):
    """Handle 500 Internal Server Error."""
    if not request.path.startswith("/api/"):
        return e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)


@errors.app_errorhandler(Exception)
def handle_exception(e):
    """Handle all other exceptions."""
    # Only force JSON for API routes
    if not request.path.startswith("/api/"):
        # Non-API routes behave normally (HTML)
        if isinstance(e, HTTPException):
            return e
        raise e
    
    request_id = _get_request_id()
    user_id = _get_user_id()
    error_name, detail, status = _map_exception_to_error(e)
    
    return _create_error_response(error_name, detail, status, request_id, user_id, e)
