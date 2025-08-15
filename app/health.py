"""
Health check endpoints for mdraft.

This module provides health check endpoints for monitoring the application's
status. The /healthz endpoint provides a fast health check, while /readyz
performs comprehensive checks including database connectivity, Redis ping,
and storage access.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from . import db
from .services import Storage


bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@bp.get("/healthz")
def healthz() -> tuple[Dict[str, Any], int]:
    """Fast health check endpoint.
    
    This endpoint performs minimal checks and returns quickly.
    It does not check database connectivity or external services.
    
    Returns:
        JSON response with status information
    """
    return jsonify({
        "status": "healthy",
        "service": "mdraft",
        "version": "1.0.0"
    }), 200


@bp.get("/readyz")
def readyz() -> tuple[Dict[str, Any], int]:
    """Comprehensive readiness check endpoint.
    
    This endpoint performs thorough checks including:
    - Database connectivity
    - Redis connectivity (if configured)
    - Storage access
    
    Returns:
        JSON response with detailed status information
    """
    checks = {
        "database": False,
        "redis": False,
        "storage": False
    }
    
    # Check database connectivity
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = True
        logger.debug("Database health check passed")
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # Check Redis connectivity (if configured)
    try:
        redis_client = current_app.extensions.get('redis')
        if redis_client:
            redis_client.ping()
            checks["redis"] = True
            logger.debug("Redis health check passed")
        else:
            # Redis not configured, mark as healthy
            checks["redis"] = True
            logger.debug("Redis not configured, skipping health check")
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
    
    # Check storage access
    try:
        storage = Storage()
        # Test storage by listing a health check prefix
        storage.list_prefix('health/')
        checks["storage"] = True
        logger.debug("Storage health check passed")
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
    
    # Determine overall status
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    response = {
        "status": "ready" if all_healthy else "not_ready",
        "service": "mdraft",
        "version": "1.0.0",
        "checks": checks
    }
    
    if not all_healthy:
        response["message"] = "One or more health checks failed"
    
    return jsonify(response), status_code


@bp.get("/health")
def health() -> tuple[Dict[str, Any], int]:
    """Lightweight health check endpoint.
    
    This endpoint executes a lightweight DB query and returns {status:'ok'}.
    Used by monitoring systems for basic health checks.
    
    Returns:
        JSON response with status information
    """
    try:
        # Execute lightweight DB query
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception("Database health check failed")
        return jsonify({"status": "database_error"}), 503
