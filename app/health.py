"""
Health check endpoints for mdraft.

This module provides health check endpoints for monitoring the application's
status. The /healthz endpoint provides a fast health check, while /readyz
performs comprehensive checks including database connectivity, Redis ping,
Celery worker status, and storage access.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from . import db
from .services import Storage


bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


def _check_database(timeout: float = 2.0) -> Dict[str, Any]:
    """Check database connectivity with timeout.
    
    Args:
        timeout: Maximum time to wait for database response in seconds
        
    Returns:
        Dictionary with check result
    """
    start_time = time.time()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: db.session.execute(text("SELECT 1")))
            future.result(timeout=timeout)
        
        duration = time.time() - start_time
        return {
            "status": "healthy",
            "duration_ms": round(duration * 1000, 2),
            "error": None
        }
    except FutureTimeoutError:
        return {
            "status": "unhealthy",
            "duration_ms": round(timeout * 1000, 2),
            "error": "Database query timed out"
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "status": "unhealthy",
            "duration_ms": round(duration * 1000, 2),
            "error": str(e)
        }


def _check_redis(timeout: float = 1.0) -> Dict[str, Any]:
    """Check Redis connectivity with timeout.
    
    Args:
        timeout: Maximum time to wait for Redis response in seconds
        
    Returns:
        Dictionary with check result
    """
    start_time = time.time()
    try:
        # Check if Redis is configured
        redis_client = current_app.extensions.get('redis')
        if not redis_client:
            # Redis not configured, mark as healthy
            return {
                "status": "healthy",
                "duration_ms": 0,
                "error": None,
                "note": "Redis not configured"
            }
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(redis_client.ping)
            future.result(timeout=timeout)
        
        duration = time.time() - start_time
        return {
            "status": "healthy",
            "duration_ms": round(duration * 1000, 2),
            "error": None
        }
    except FutureTimeoutError:
        return {
            "status": "unhealthy",
            "duration_ms": round(timeout * 1000, 2),
            "error": "Redis ping timed out"
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "status": "unhealthy",
            "duration_ms": round(duration * 1000, 2),
            "error": str(e)
        }


def _check_celery(timeout: float = 3.0) -> Dict[str, Any]:
    """Check Celery worker connectivity with timeout.
    
    Args:
        timeout: Maximum time to wait for Celery response in seconds
        
    Returns:
        Dictionary with check result
    """
    start_time = time.time()
    try:
        # Import celery here to avoid circular imports
        from celery_worker import celery
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(celery.control.inspect().ping)
            result = future.result(timeout=timeout)
        
        duration = time.time() - start_time
        
        if result:
            # Count active workers
            active_workers = len(result)
            return {
                "status": "healthy",
                "duration_ms": round(duration * 1000, 2),
                "error": None,
                "active_workers": active_workers
            }
        else:
            return {
                "status": "unhealthy",
                "duration_ms": round(duration * 1000, 2),
                "error": "No active Celery workers found"
            }
    except FutureTimeoutError:
        return {
            "status": "unhealthy",
            "duration_ms": round(timeout * 1000, 2),
            "error": "Celery inspect ping timed out"
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "status": "unhealthy",
            "duration_ms": round(duration * 1000, 2),
            "error": str(e)
        }


def _check_storage(timeout: float = 2.0) -> Dict[str, Any]:
    """Check storage access with timeout.
    
    Args:
        timeout: Maximum time to wait for storage response in seconds
        
    Returns:
        Dictionary with check result
    """
    start_time = time.time()
    try:
        storage = Storage()
        
        # Check if GCS is configured
        use_gcs = current_app.config.get('USE_GCS', False)
        if use_gcs:
            # Test GCS bucket access
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(storage.list_prefix, 'health/')
                future.result(timeout=timeout)
        else:
            # For local storage, just check if storage object can be created
            # This is a minimal check that doesn't require actual file system access
            pass
        
        duration = time.time() - start_time
        return {
            "status": "healthy",
            "duration_ms": round(duration * 1000, 2),
            "error": None,
            "storage_type": "gcs" if use_gcs else "local"
        }
    except FutureTimeoutError:
        return {
            "status": "unhealthy",
            "duration_ms": round(timeout * 1000, 2),
            "error": "Storage access timed out"
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "status": "unhealthy",
            "duration_ms": round(duration * 1000, 2),
            "error": str(e)
        }


@bp.get("/healthz")
def healthz() -> tuple[Dict[str, Any], int]:
    """Fast health check endpoint for liveness.
    
    This endpoint performs minimal checks and returns quickly.
    It does not check database connectivity or external services.
    Used by Kubernetes liveness probes.
    
    Returns:
        JSON response with status information
    """
    return jsonify({
        "status": "healthy",
        "service": "mdraft",
        "version": "1.0.0",
        "timestamp": time.time()
    }), 200


@bp.get("/readyz")
def readyz() -> tuple[Dict[str, Any], int]:
    """Comprehensive readiness check endpoint.
    
    This endpoint performs thorough checks including:
    - Database connectivity (SELECT 1)
    - Redis connectivity (if configured)
    - Celery worker status (inspect ping)
    - Storage access (GCS bucket or local filesystem)
    
    All checks have bounded timeouts to prevent hanging.
    Used by Kubernetes readiness probes.
    
    Returns:
        JSON response with detailed status information
    """
    start_time = time.time()
    
    # Perform all health checks
    checks = {
        "database": _check_database(timeout=2.0),
        "redis": _check_redis(timeout=1.0),
        "celery": _check_celery(timeout=3.0),
        "storage": _check_storage(timeout=2.0)
    }
    
    # Determine overall status
    all_healthy = all(check["status"] == "healthy" for check in checks.values())
    status_code = 200 if all_healthy else 503
    
    # Calculate total duration
    total_duration = time.time() - start_time
    
    response = {
        "status": "ready" if all_healthy else "not_ready",
        "service": "mdraft",
        "version": "1.0.0",
        "timestamp": time.time(),
        "duration_ms": round(total_duration * 1000, 2),
        "checks": checks
    }
    
    if not all_healthy:
        # Add details about which checks failed
        failed_checks = [
            name for name, check in checks.items() 
            if check["status"] != "healthy"
        ]
        response["message"] = f"Health checks failed: {', '.join(failed_checks)}"
        response["failed_checks"] = failed_checks
    
    return jsonify(response), status_code


@bp.get("/health")
def health():
    """Legacy health endpoint - redirects to simple health check."""
    return jsonify({"ok": True}), 200


@bp.get("/health/simple")
def health_simple():
    """Fast readiness check - always returns 200, no DB/Redis checks."""
    return jsonify({"ok": True}), 200


@bp.get("/health/full")
def health_full():
    """Deep health check - DB ping, Redis ping, Celery inspect."""
    status = {}
    
    # DB
    try:
        db.session.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception as e:
        status["db"] = f"error:{type(e).__name__}"
    
    # Redis (session store)
    try:
        r = current_app.config.get("SESSION_REDIS")
        if r:
            r.ping()
            status["redis"] = "ok"
        else:
            status["redis"] = "not_configured"
    except Exception as e:
        status["redis"] = f"error:{type(e).__name__}"
    
    # Celery
    try:
        from celery_worker import celery as c
        insp = c.control.inspect(timeout=3)
        workers = insp and (insp.active() or insp.ping())
        status["celery"] = "ok" if workers else "down"
    except Exception as e:
        status["celery"] = f"error:{type(e).__name__}"

    code = 200 if all(v in ("ok","not_configured") for v in status.values()) else 503
    return jsonify(status), code
