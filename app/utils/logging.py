"""
Structured JSON logging utilities for mdraft.

This module provides comprehensive logging with correlation IDs, request tracking,
and Celery task integration for observability and debugging.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps

from flask import g, request, has_request_context
from celery import current_task

# Context variables for correlation IDs
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
task_id_var: ContextVar[Optional[str]] = ContextVar('task_id', default=None)
job_id_var: ContextVar[Optional[str]] = ContextVar('job_id', default=None)
conversion_id_var: ContextVar[Optional[str]] = ContextVar('conversion_id', default=None)


def _setup_sentry_scope():
    """Set up Sentry scope with correlation IDs and user context."""
    try:
        import sentry_sdk
        with sentry_sdk.configure_scope() as scope:
            # Set request_id tag
            request_id = request_id_var.get()
            if request_id:
                scope.set_tag("request_id", request_id)
            
            # Set user_id tag and user context
            user_id = user_id_var.get()
            if user_id:
                scope.set_tag("user_id", user_id)
                scope.set_user({"id": user_id})
            
            # Set task_id tag
            task_id = task_id_var.get()
            if task_id:
                scope.set_tag("task_id", task_id)
            
            # Set job_id tag
            job_id = job_id_var.get()
            if job_id:
                scope.set_tag("job_id", job_id)
            
            # Set conversion_id tag
            conversion_id = conversion_id_var.get()
            if conversion_id:
                scope.set_tag("conversion_id", conversion_id)
            
            # Add request context if available
            if has_request_context():
                scope.set_context("request", {
                    "url": request.url,
                    "method": request.method,
                    "path": request.path,
                    "remote_addr": request.remote_addr,
                    "user_agent": request.headers.get("User-Agent", ""),
                })
    except ImportError:
        pass  # Sentry not available
    except Exception:
        pass  # Don't let Sentry errors break logging


class StructuredJSONFormatter(logging.Formatter):
    """Format log records as structured JSON with correlation IDs and context."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with correlation IDs and context."""
        try:
            # Base log data
            log_data: Dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            
            # Add correlation IDs from context variables
            request_id = request_id_var.get()
            if request_id:
                log_data["request_id"] = request_id
                
            user_id = user_id_var.get()
            if user_id:
                log_data["user_id"] = user_id
                
            task_id = task_id_var.get()
            if task_id:
                log_data["task_id"] = task_id
                
            job_id = job_id_var.get()
            if job_id:
                log_data["job_id"] = job_id
                
            conversion_id = conversion_id_var.get()
            if conversion_id:
                log_data["conversion_id"] = conversion_id
            
            # Add Flask request context if available
            if has_request_context():
                # Request-specific data
                log_data.update({
                    "method": request.method,
                    "path": request.path,
                    "remote_addr": request.remote_addr,
                    "user_agent": request.headers.get("User-Agent", ""),
                })
                
                # Cloud Tasks headers
                task_name = request.headers.get("X-Cloud-Tasks-TaskName")
                if task_name:
                    log_data["cloud_task_name"] = task_name
                    
                queue_name = request.headers.get("X-Cloud-Tasks-QueueName")
                if queue_name:
                    log_data["cloud_queue_name"] = queue_name
                    
                execution_count = request.headers.get("X-Cloud-Tasks-Execution-Count")
                if execution_count:
                    log_data["cloud_execution_count"] = execution_count
            
            # Add Celery task context if available
            if current_task:
                try:
                    log_data.update({
                        "celery_task_id": current_task.request.id,
                        "celery_task_name": current_task.name,
                        "celery_retries": current_task.request.retries,
                        "celery_queue": getattr(current_task.request, 'delivery_info', {}).get('routing_key', ''),
                    })
                except Exception:
                    pass  # Celery context not available
            
            # Add timing information if available
            if hasattr(record, 'duration_ms'):
                log_data["duration_ms"] = record.duration_ms
                
            if hasattr(record, 'start_time'):
                log_data["start_time"] = record.start_time
                
            # Add extra fields from record
            if hasattr(record, 'extra_fields'):
                log_data.update(record.extra_fields)
                
            # Add exception information
            if record.exc_info:
                log_data["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                }
            
            return json.dumps(log_data, default=str)
            
        except Exception as e:
            # Fallback to basic JSON if formatting fails
            fallback_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "formatting_error": str(e),
                "original_record": str(record)
            }
            return json.dumps(fallback_data, default=str)


def get_correlation_ids() -> Dict[str, Optional[str]]:
    """Get all current correlation IDs from context."""
    try:
        return {
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "task_id": task_id_var.get(),
            "job_id": job_id_var.get(),
            "conversion_id": conversion_id_var.get(),
        }
    except Exception:
        # Return empty dict if context variables fail
        return {
            "request_id": None,
            "user_id": None,
            "task_id": None,
            "job_id": None,
            "conversion_id": None,
        }


def set_correlation_id(key: str, value: Optional[str]) -> None:
    """Set a correlation ID in the current context with error handling."""
    try:
        if key == "request_id":
            request_id_var.set(value)
        elif key == "user_id":
            user_id_var.set(value)
        elif key == "task_id":
            task_id_var.set(value)
        elif key == "job_id":
            job_id_var.set(value)
        elif key == "conversion_id":
            conversion_id_var.set(value)
        else:
            raise ValueError(f"Unknown correlation ID key: {key}")
        
        # Update Sentry scope when correlation IDs change
        _setup_sentry_scope()
        
    except Exception as e:
        # Log the error but don't break the application
        logger = logging.getLogger("mdraft.logging")
        logger.error("Failed to set correlation ID", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "key": key,
            "value": value
        })


def clear_correlation_ids() -> None:
    """Clear all correlation IDs from context with error handling."""
    try:
        request_id_var.set(None)
        user_id_var.set(None)
        task_id_var.set(None)
        job_id_var.set(None)
        conversion_id_var.set(None)
    except Exception as e:
        # Log the error but don't break the application
        logger = logging.getLogger("mdraft.logging")
        logger.error("Failed to clear correlation IDs", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })


def log_with_context(level: str = "INFO", **extra_fields):
    """Log a message with correlation IDs and extra context with error handling."""
    try:
        logger = logging.getLogger("mdraft")
        
        # Create a custom record with extra fields
        record = logging.LogRecord(
            name=logger.name,
            level=getattr(logging, level.upper()),
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        
        # Add extra fields to the record
        record.extra_fields = extra_fields
        
        # Log the record
        logger.handle(record)
        
    except Exception as e:
        # Fallback to basic logging if structured logging fails
        logger = logging.getLogger("mdraft")
        logger.error("Failed to log with context", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "level": level,
            "extra_fields": str(extra_fields)
        })


def timing_decorator(func):
    """Decorator to log function execution time with correlation IDs and error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = f"{func.__module__}.{func.__name__}"
        
        try:
            result = func(*args, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            
            log_with_context(
                level="INFO",
                event="function_completed",
                function_name=func_name,
                duration_ms=duration_ms,
                success=True,
            )
            
            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            log_with_context(
                level="ERROR",
                event="function_failed",
                function_name=func_name,
                duration_ms=duration_ms,
                success=False,
                error=str(e),
                error_type=type(e).__name__,
            )
            
            raise
    
    return wrapper


class RequestLogger:
    """Request logging middleware with correlation IDs and timing."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize request logging middleware with comprehensive error handling."""
        
        @app.before_request
        def before_request():
            """Set up request context and correlation IDs with error handling."""
            try:
                # Generate or extract request ID (guarantee UUIDv4 format)
                header_request_id = (
                    request.headers.get('X-Request-ID') or 
                    request.headers.get('X-Request-Id')
                )
                
                if header_request_id:
                    # Validate the header request ID format
                    try:
                        uuid.UUID(header_request_id)
                        request_id = header_request_id
                    except (ValueError, TypeError):
                        # Invalid UUID format, generate new one
                        request_id = str(uuid.uuid4())
                        logger = logging.getLogger("mdraft.request")
                        logger.warning("Invalid X-Request-ID header format, generated new UUID", extra={
                            "invalid_request_id": header_request_id,
                            "new_request_id": request_id
                        })
                else:
                    # No header provided, generate new UUIDv4
                    request_id = str(uuid.uuid4())
                
                # Set correlation IDs
                set_correlation_id("request_id", request_id)
                
                # Set user ID if authenticated
                try:
                    if hasattr(request, 'user') and request.user and hasattr(request.user, 'id'):
                        set_correlation_id("user_id", str(request.user.id))
                    elif hasattr(g, 'user_id'):
                        set_correlation_id("user_id", str(g.user_id))
                except Exception as e:
                    logger = logging.getLogger("mdraft.request")
                    logger.warning("Failed to set user_id", extra={
                        "error": str(e),
                        "request_id": request_id
                    })
                
                # Set job_id and conversion_id from headers/environment
                try:
                    job_id = (
                        request.headers.get('X-Job-ID') or 
                        request.environ.get('X-Job-ID')
                    )
                    if job_id:
                        set_correlation_id("job_id", str(job_id))
                        
                    conversion_id = (
                        request.headers.get('X-Conversion-ID') or 
                        request.environ.get('X-Conversion-ID')
                    )
                    if conversion_id:
                        set_correlation_id("conversion_id", str(conversion_id))
                except Exception as e:
                    logger = logging.getLogger("mdraft.request")
                    logger.warning("Failed to set job/conversion IDs", extra={
                        "error": str(e),
                        "request_id": request_id
                    })
                
                # Store start time
                g._request_start_time = time.time()
                
                # Log request start
                log_with_context(
                    level="INFO",
                    event="request_started",
                    method=request.method,
                    path=request.path,
                    remote_addr=request.remote_addr,
                )
                
            except Exception as e:
                # Critical error in request setup - log it but don't break the request
                logger = logging.getLogger("mdraft.request")
                logger.error("Critical error in request setup", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "method": request.method,
                    "path": request.path
                })
        
        @app.after_request
        def after_request(response):
            """Log request completion with timing and status with error handling."""
            try:
                # Calculate duration
                duration_ms = int((time.time() - g._request_start_time) * 1000) if hasattr(g, '_request_start_time') else -1
                
                # Add X-Request-ID header to all responses
                request_id = get_correlation_ids().get("request_id")
                if request_id:
                    response.headers.setdefault('X-Request-ID', request_id)
                
                # Log request completion
                log_with_context(
                    level="INFO",
                    event="request_completed",
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    content_length=response.content_length,
                )
                
                # Add request_id to error responses
                if response.status_code >= 400 and request.path.startswith("/api/"):
                    try:
                        data = response.get_json()
                        if data and isinstance(data, dict):
                            data["request_id"] = get_correlation_ids().get("request_id")
                            response.set_data(json.dumps(data))
                    except Exception as e:
                        logger = logging.getLogger("mdraft.request")
                        logger.warning("Failed to add request_id to error response", extra={
                            "error": str(e),
                            "request_id": get_correlation_ids().get("request_id"),
                            "status_code": response.status_code
                        })
                
                # Clear correlation IDs after request
                clear_correlation_ids()
                
            except Exception as e:
                # Critical error in response logging - log it but don't break the response
                logger = logging.getLogger("mdraft.request")
                logger.error("Critical error in response logging", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code if response else "unknown"
                })
                
                # Ensure response still has X-Request-ID header even if logging failed
                try:
                    request_id = get_correlation_ids().get("request_id", "unknown")
                    response.headers.setdefault('X-Request-ID', request_id)
                except Exception:
                    pass  # Don't let header setting break the response
                
                # Clear correlation IDs even if logging failed
                try:
                    clear_correlation_ids()
                except Exception:
                    pass
            
            return response
        
        @app.teardown_request
        def teardown_request(exception=None):
            """Clean up request context and log any unhandled exceptions with error handling."""
            try:
                if exception:
                    log_with_context(
                        level="ERROR",
                        event="request_exception",
                        error=str(exception),
                        exception_type=type(exception).__name__,
                    )
                
                # Clear correlation IDs
                clear_correlation_ids()
                
            except Exception as e:
                # Don't let teardown errors break the application
                logger = logging.getLogger("mdraft.request")
                logger.error("Critical error in request teardown", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "original_exception": str(exception) if exception else None
                })


class CeleryTaskLogger:
    """Celery task logging with correlation IDs and error handling."""
    
    @staticmethod
    def setup_task_logging(task_id: str, **extra_context):
        """Set up logging context for a Celery task with error handling."""
        try:
            set_correlation_id("task_id", task_id)
            
            # Set additional context
            for key, value in extra_context.items():
                if key in ["job_id", "conversion_id", "user_id"]:
                    set_correlation_id(key, str(value) if value else None)
            
            log_with_context(
                level="INFO",
                event="celery_task_started",
                task_id=task_id,
                **extra_context
            )
        except Exception as e:
            logger = logging.getLogger("mdraft.celery")
            logger.error("Failed to setup task logging", extra={
                "error": str(e),
                "task_id": task_id
            })
    
    @staticmethod
    def log_task_completion(task_id: str, success: bool, duration_ms: int, **extra_context):
        """Log Celery task completion with error handling."""
        try:
            log_with_context(
                level="INFO" if success else "ERROR",
                event="celery_task_completed" if success else "celery_task_failed",
                task_id=task_id,
                success=success,
                duration_ms=duration_ms,
                **extra_context
            )
            
            # Clear task context
            clear_correlation_ids()
        except Exception as e:
            logger = logging.getLogger("mdraft.celery")
            logger.error("Failed to log task completion", extra={
                "error": str(e),
                "task_id": task_id,
                "success": success
            })


def setup_logging(app, log_level: str = "INFO"):
    """Set up structured JSON logging for the application with error handling."""
    try:
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create structured JSON handler
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJSONFormatter())
        root_logger.addHandler(handler)
        
        # Configure Flask app logger
        app.logger.setLevel(getattr(logging, log_level.upper()))
        app.logger.propagate = False  # Prevent duplicate logs
        
        # Add structured handler to app logger
        app_handler = logging.StreamHandler()
        app_handler.setFormatter(StructuredJSONFormatter())
        app.logger.addHandler(app_handler)
        
        # Initialize request logging
        RequestLogger(app)
        
        app.logger.info("Structured JSON logging initialized", extra={
            "log_level": log_level,
            "formatter": "StructuredJSONFormatter"
        })
        
    except Exception as e:
        # Fallback to basic logging if structured logging setup fails
        app.logger.error("Failed to setup structured logging, falling back to basic logging", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })


# Convenience functions for common logging patterns
def log_api_request(method: str, path: str, status_code: int, duration_ms: int, **extra):
    """Log API request with correlation IDs and error handling."""
    try:
        log_with_context(
            level="INFO",
            event="api_request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            **extra
        )
    except Exception as e:
        logger = logging.getLogger("mdraft.api")
        logger.error("Failed to log API request", extra={
            "error": str(e),
            "method": method,
            "path": path,
            "status_code": status_code
        })


def log_database_operation(operation: str, table: str, duration_ms: int, **extra):
    """Log database operation with correlation IDs and error handling."""
    try:
        log_with_context(
            level="INFO",
            event="database_operation",
            operation=operation,
            table=table,
            duration_ms=duration_ms,
            **extra
        )
    except Exception as e:
        logger = logging.getLogger("mdraft.database")
        logger.error("Failed to log database operation", extra={
            "error": str(e),
            "operation": operation,
            "table": table
        })


def log_conversion_event(conversion_id: str, event: str, **extra):
    """Log conversion-related event with correlation IDs and error handling."""
    try:
        set_correlation_id("conversion_id", conversion_id)
        log_with_context(
            level="INFO",
            event=f"conversion_{event}",
            conversion_id=conversion_id,
            **extra
        )
    except Exception as e:
        logger = logging.getLogger("mdraft.conversion")
        logger.error("Failed to log conversion event", extra={
            "error": str(e),
            "conversion_id": conversion_id,
            "event": event
        })


def log_job_event(job_id: str, event: str, **extra):
    """Log job-related event with correlation IDs and error handling."""
    try:
        set_correlation_id("job_id", job_id)
        log_with_context(
            level="INFO",
            event=f"job_{event}",
            job_id=job_id,
            **extra
        )
    except Exception as e:
        logger = logging.getLogger("mdraft.job")
        logger.error("Failed to log job event", extra={
            "error": str(e),
            "job_id": job_id,
            "event": event
        })
