"""
Health check endpoints for mdraft application.

This module provides health check endpoints for monitoring system status,
including database connectivity, storage availability, and PDF backend status.
"""
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

bp = Blueprint("health", __name__)


@bp.route("/health")
def health_check():
    """Comprehensive health check endpoint."""
    try:
        # Check database connectivity
        from ..extensions import db
        db.session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        current_app.logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check storage backend
    try:
        from app.storage_adapter import get_storage
        storage = get_storage()
        storage_status = "healthy"
        storage_backend = storage.backend_name
    except Exception as e:
        current_app.logger.error(f"Storage health check failed: {e}")
        storage_status = "unhealthy"
        storage_backend = "unknown"
    
    # Check PDF backend
    try:
        from app.services.pdf_backend import validate_pdf_backend
        pdf_status = validate_pdf_backend()
        if pdf_status["available"]:
            pdf_backend_status = "healthy"
            pdf_backend_name = pdf_status["backend"]
        else:
            pdf_backend_status = "unavailable"
            pdf_backend_name = None
    except Exception as e:
        current_app.logger.error(f"PDF backend health check failed: {e}")
        pdf_backend_status = "error"
        pdf_backend_name = None
    
    # Overall status
    overall_status = "healthy" if all([
        db_status == "healthy",
        storage_status == "healthy"
    ]) else "degraded"
    
    return jsonify({
        "status": overall_status,
        "timestamp": "2024-01-01T00:00:00Z",  # You can add actual timestamp
        "services": {
            "database": {
                "status": db_status
            },
            "storage": {
                "status": storage_status,
                "backend": storage_backend
            },
            "pdf_backend": {
                "status": pdf_backend_status,
                "backend": pdf_backend_name
            }
        }
    }), 200 if overall_status == "healthy" else 503


@bp.route("/health/simple")
def health_simple():
    """Simple health check for load balancers."""
    return jsonify({"ok": True}), 200


@bp.route("/health/pdf")
def health_pdf():
    """PDF backend health check endpoint."""
    try:
        from app.services.pdf_backend import validate_pdf_backend
        status = validate_pdf_backend()
        
        if status["available"]:
            return jsonify({
                "status": "healthy",
                "backend": status["backend"],
                "available": True
            }), 200
        else:
            return jsonify({
                "status": "unavailable",
                "error": status["error"],
                "recommendation": status["recommendation"],
                "available": False
            }), 503
            
    except Exception as e:
        current_app.logger.exception("PDF backend health check failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "available": False
        }), 503
