import time
import uuid
import logging
import json
from flask import g, request, jsonify

log = logging.getLogger("mdraft.request")


def init_request_logging(app):
    """Initialize request logging middleware.
    
    Logs: method, path, status, duration, request_id, user_id
    Includes request_id in API error responses.
    Guarantees UUIDv4 request_id creation; falls back to X-Request-ID header if provided.
    Wraps all operations in try/except to prevent middleware errors from breaking responses.
    """
    
    @app.before_request
    def _start():
        """Start timing and generate request ID with comprehensive error handling."""
        try:
            # Start timing
            g._t = time.time()
            
            # Guarantee UUIDv4 request_id creation; fall back to X-Request-ID header if provided
            header_request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Request-Id')
            if header_request_id:
                # Validate the header request ID format (should be UUID-like)
                try:
                    # Try to parse as UUID to validate format
                    uuid.UUID(header_request_id)
                    g.request_id = header_request_id
                except (ValueError, TypeError):
                    # Invalid UUID format, generate new one
                    g.request_id = str(uuid.uuid4())
                    log.warning("Invalid X-Request-ID header format, generated new UUID", extra={
                        "invalid_request_id": header_request_id,
                        "new_request_id": g.request_id,
                        "method": request.method,
                        "path": request.path
                    })
            else:
                # No header provided, generate new UUIDv4
                g.request_id = str(uuid.uuid4())
            
            # Store in environment for access by other components
            request.environ['X-Request-ID'] = g.request_id
            request.environ['HTTP_X_REQUEST_ID'] = g.request_id
            
            # Set correlation ID in structured logging context
            try:
                from app.utils.logging import set_correlation_id
                set_correlation_id("request_id", g.request_id)
            except ImportError:
                log.warning("Structured logging not available, continuing with basic logging", extra={
                    "request_id": g.request_id,
                    "method": request.method,
                    "path": request.path
                })
            except Exception as e:
                log.error("Failed to set correlation ID", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "request_id": g.request_id,
                    "method": request.method,
                    "path": request.path
                })
                
        except Exception as e:
            # Generate fallback request_id even if everything else fails
            try:
                g.request_id = str(uuid.uuid4())
                g._t = time.time()
            except Exception:
                # Last resort - use timestamp-based ID
                g.request_id = f"fallback-{int(time.time() * 1000)}"
                g._t = time.time()
            
            log.error("Critical error in request logging middleware", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "fallback_request_id": g.request_id,
                "method": request.method,
                "path": request.path
            })
    
    @app.after_request
    def _end(resp):
        """Log request completion with timing and comprehensive error handling."""
        try:
            # Calculate duration with fallback
            dt = int((time.time() - g._t) * 1000) if getattr(g, "_t", None) else -1
            request_id = getattr(g, "request_id", "unknown")
            
            # Extract user_id from various sources
            user_id = "anonymous"
            try:
                if hasattr(request, 'user') and request.user and hasattr(request.user, 'id'):
                    user_id = str(request.user.id)
                elif hasattr(g, 'user_id'):
                    user_id = str(g.user_id)
                elif hasattr(g, 'current_user') and g.current_user and hasattr(g.current_user, 'id'):
                    user_id = str(g.current_user.id)
            except Exception as e:
                log.warning("Failed to extract user_id", extra={
                    "error": str(e),
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path
                })
            
            # Add request_id to API error responses with error handling
            if resp.status_code >= 400 and request.path.startswith("/api/"):
                try:
                    data = resp.get_json()
                    if data and isinstance(data, dict):
                        data["request_id"] = request_id
                        resp.set_data(jsonify(data).get_data())
                except Exception as e:
                    # Not JSON response or other error - log but don't break
                    log.warning("Failed to add request_id to error response", extra={
                        "error": str(e),
                        "request_id": request_id,
                        "status_code": resp.status_code,
                        "content_type": resp.content_type,
                        "method": request.method,
                        "path": request.path
                    })
            
            # Add X-Request-ID header to all responses for correlation
            resp.headers.setdefault('X-Request-ID', request_id)
            
            # Log structured JSON with all required fields
            log_data = {
                "method": request.method,
                "path": request.path,
                "status": resp.status_code,
                "duration_ms": dt,
                "request_id": request_id,
                "user_id": user_id,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", ""),
                "content_length": resp.content_length,
                "content_type": resp.content_type
            }
            
            # Add additional context for errors
            if resp.status_code >= 400:
                log_data["error_category"] = "client_error" if resp.status_code < 500 else "server_error"
            
            # Log with appropriate level
            if resp.status_code >= 500:
                log.error("Request completed with server error", extra=log_data)
            elif resp.status_code >= 400:
                log.warning("Request completed with client error", extra=log_data)
            else:
                log.info("Request completed successfully", extra=log_data)
                
        except Exception as e:
            # Critical error in response logging - log it but don't break the response
            fallback_request_id = getattr(g, "request_id", "unknown")
            log.error("Critical error in response logging middleware", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "fallback_request_id": fallback_request_id,
                "method": request.method,
                "path": request.path,
                "status_code": resp.status_code if resp else "unknown"
            })
            
            # Ensure response still has X-Request-ID header even if logging failed
            try:
                resp.headers.setdefault('X-Request-ID', fallback_request_id)
            except Exception:
                pass  # Don't let header setting break the response
        
        return resp
    
    @app.teardown_request
    def _teardown(exception=None):
        """Clean up request context and log any unhandled exceptions."""
        try:
            request_id = getattr(g, "request_id", "unknown")
            
            if exception:
                log.error("Unhandled exception in request", extra={
                    "error": str(exception),
                    "exception_type": type(exception).__name__,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path
                })
            
            # Clear correlation IDs
            try:
                from app.utils.logging import clear_correlation_ids
                clear_correlation_ids()
            except ImportError:
                pass  # Structured logging not available
            except Exception as e:
                log.warning("Failed to clear correlation IDs", extra={
                    "error": str(e),
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path
                })
                
        except Exception as e:
            # Don't let teardown errors break the application
            log.error("Critical error in request teardown", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "original_exception": str(exception) if exception else None
            })
