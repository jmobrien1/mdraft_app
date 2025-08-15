"""
Operations API endpoints for mdraft.

This module provides operational endpoints for monitoring, debugging,
and administrative tasks.
"""
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required
import os
import time
from datetime import datetime

bp = Blueprint("ops", __name__, url_prefix="/api/ops")


@bp.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }), 200


@bp.route("/ping", methods=["POST"])
@login_required
def ping_celery():
    """Test Celery worker connectivity with a ping task.
    
    This endpoint sends a ping task to the Celery worker to verify:
    1. The worker can receive tasks
    2. The worker can process tasks
    3. The worker can return results
    
    Request:
    {
        "message": "optional custom message"
    }
    
    Returns:
    {
        "status": "success|error",
        "task_id": "celery task id",
        "result": "ping response",
        "duration_ms": 123,
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    try:
        # Check if Celery is configured
        queue_mode = os.getenv("QUEUE_MODE", "celery").lower()
        if queue_mode != "celery":
            return jsonify({
                "status": "error",
                "error": "Celery not enabled (QUEUE_MODE != 'celery')",
                "queue_mode": queue_mode
            }), 400
        
        # Get message from request
        data = request.get_json() or {}
        message = data.get("message", "pong")
        
        # Import Celery app
        from celery_worker import celery
        
        # Send ping task
        start_time = time.time()
        task = celery.send_task('ping_task', args=[message])
        
        # Wait for result with timeout
        timeout = 30  # seconds
        start_wait = time.time()
        
        while time.time() - start_wait < timeout:
            if task.ready():
                break
            time.sleep(0.1)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if task.ready():
            if task.successful():
                result = task.get()
                return jsonify({
                    "status": "success",
                    "task_id": task.id,
                    "result": result,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat()
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "task_id": task.id,
                    "error": str(task.info),
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat()
                }), 500
        else:
            return jsonify({
                "status": "error",
                "task_id": task.id,
                "error": "Task timed out",
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat()
            }), 408
            
    except Exception as e:
        current_app.logger.exception("Ping task failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@bp.route("/config", methods=["GET"])
@login_required
def get_config():
    """Get configuration information for debugging.
    
    Returns:
    {
        "queue_mode": "celery|sync",
        "broker_url": "redis://...",
        "worker_service": true|false,
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    try:
        return jsonify({
            "queue_mode": os.getenv("QUEUE_MODE", "celery"),
            "broker_url": os.getenv("CELERY_BROKER_URL", "NOT SET"),
            "worker_service": os.getenv("WORKER_SERVICE", "false").lower() == "true",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        current_app.logger.exception("Config endpoint failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@bp.route("/migration_status", methods=["GET"])
@login_required
def migration_status():
    """Get database migration status.
    
    Reports current alembic head and whether expected tables exist.
    
    Returns:
    {
        "alembic_head": "revision_id",
        "tables_exist": {
            "proposals": true,
            "conversions": true,
            "users": true,
            "api_keys": true
        },
        "status": "ok|error",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    try:
        from sqlalchemy import text, inspect
        from .. import db
        
        # Get alembic head
        alembic_head = None
        try:
            result = db.session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            alembic_head = result.scalar()
        except Exception as e:
            current_app.logger.warning(f"Could not get alembic head: {e}")
        
        # Check if expected tables exist
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        
        expected_tables = ["proposals", "conversions", "users", "api_keys"]
        tables_exist = {}
        
        for table in expected_tables:
            tables_exist[table] = table in existing_tables
        
        return jsonify({
            "alembic_head": alembic_head,
            "tables_exist": tables_exist,
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.exception("Migration status check failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500
