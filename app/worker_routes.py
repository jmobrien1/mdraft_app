"""
Worker service routes for mdraft.

This module defines the HTTP endpoints for the worker service that
processes document conversion tasks from Cloud Tasks. The worker
service is designed to be idempotent - duplicate task requests are
safely ignored if the job is already completed.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, abort
from sqlalchemy import text

from . import db
from .models import Job
from .conversion import process_job
from .storage import download_from_gcs, upload_stream_to_gcs, upload_text_to_gcs
from .services import Storage
from utils.db import advisory_lock, get_job_with_lock
from .utils.logging import log_with_context, set_correlation_id, get_correlation_ids

logger = logging.getLogger(__name__)

# Create worker blueprint
worker_bp = Blueprint("worker", __name__)


@worker_bp.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint for the worker service.
    
    This endpoint verifies that the worker service is running and
    can connect to the database.
    """
    try:
        # Execute a simple SELECT to validate the connection
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "service": "worker"})
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Worker database health check failed")
        return jsonify({"status": "database_error", "service": "worker"}), 503


def update_job_status_atomic(session, job_id: int, new_status: str, allowed_statuses: list[str]) -> bool:
    """Atomically update job status if it's in an allowed state.
    
    This function prevents race conditions by using a WHERE clause to
    ensure the job is in an expected state before updating.
    
    Args:
        session: SQLAlchemy database session
        job_id: The job ID to update
        new_status: The new status to set
        allowed_statuses: List of statuses that allow the update
        
    Returns:
        True if the update was successful, False otherwise
    """
    try:
        # Build the WHERE clause for allowed statuses
        status_placeholders = ", ".join([f"'{status}'" for status in allowed_statuses])
        
        result = session.execute(
            text(f"""
                UPDATE jobs 
                SET status = :new_status, updated_at = NOW() 
                WHERE id = :job_id AND status IN ({status_placeholders})
            """),
            {
                "job_id": job_id,
                "new_status": new_status
            }
        )
        
        rows_updated = result.rowcount
        if rows_updated > 0:
            session.commit()
            log_with_context(
                level="INFO",
                event="job_status_updated",
                job_id=job_id,
                new_status=new_status
            )
            return True
        else:
            log_with_context(
                level="WARNING",
                event="job_status_update_failed",
                job_id=job_id,
                new_status=new_status,
                allowed_statuses=allowed_statuses
            )
            return False
            
    except Exception as e:
        log_with_context(
            level="ERROR",
            event="job_status_update_error",
            job_id=job_id,
            error=str(e)
        )
        session.rollback()
        return False


def start_job_processing_atomic(session, job_id: int) -> tuple[bool, Optional[str]]:
    """Atomically start job processing with status check.
    
    This function uses an atomic UPDATE with RETURNING to check the current
    status and update to 'processing' if allowed.
    
    Args:
        session: SQLAlchemy database session
        job_id: The job ID to start processing
        
    Returns:
        Tuple of (success: bool, current_status: Optional[str])
        If success is True, the job is now in 'processing' state
        If success is False, current_status contains the actual status
    """
    try:
        # First, try to update to processing state
        result = session.execute(
            text("""
                UPDATE jobs 
                SET status = 'PROCESSING', started_at = NOW(), updated_at = NOW() 
                WHERE id = :job_id AND status IN ('PENDING', 'PROCESSING')
                RETURNING id
            """),
            {"job_id": job_id}
        )
        
        if result.rowcount > 0:
            session.commit()
            logger.info(f"Started processing job {job_id}")
            return True, None
        
        # If no rows were updated, check the current status
        status_result = session.execute(
            text("SELECT status FROM jobs WHERE id = :job_id"),
            {"job_id": job_id}
        ).fetchone()
        
        if status_result:
            current_status = status_result[0]
            logger.info(f"Job {job_id} is in status '{current_status}', cannot start processing")
            return False, current_status
        else:
            logger.error(f"Job {job_id} not found")
            return False, None
            
    except Exception as e:
        logger.error(f"Error starting job {job_id} processing: {e}")
        session.rollback()
        return False, None


@worker_bp.route("/tasks/process-document", methods=["POST"])
def process_document_task() -> Any:
    """Process a document conversion task from Cloud Tasks.
    
    This endpoint receives task requests from Cloud Tasks and processes
    document conversions. It implements idempotency using PostgreSQL
    advisory locks and atomic status updates to prevent duplicate processing.
    
    Expected JSON payload:
    {
        "job_id": 123,
        "user_id": 456,
        "gcs_uri": "gs://bucket/path/to/document.pdf"
    }
    
    Returns:
        200: Task processed successfully (or already completed)
        400: Invalid request payload
        404: Job not found
        409: Job already failed
        500: Processing error
    """
    start_time = time.time()
    
    # Set up correlation IDs for structured logging
    task_id = request.headers.get("X-Cloud-Tasks-TaskName", str(uuid.uuid4()))
    set_correlation_id("task_id", task_id)
    
    # Header guard: verify this is a legitimate Cloud Tasks request
    queue_name = request.headers.get("X-Cloud-Tasks-QueueName")
    if not queue_name:
        log_with_context(
            level="WARNING",
            event="unauthorized_cloud_tasks_request",
            missing_header="X-Cloud-Tasks-QueueName"
        )
        return jsonify({"error": "Unauthorized"}), 403
    
    # Log Cloud Tasks headers for debugging
    task_name = request.headers.get("X-Cloud-Tasks-TaskName", "unknown")
    execution_count = request.headers.get("X-Cloud-Tasks-Execution-Count", "1")
    
    log_with_context(
        level="INFO",
        event="cloud_tasks_request_received",
        queue_name=queue_name,
        task_name=task_name,
        execution_count=execution_count
    )
    
    try:
        # Parse request payload
        if not request.is_json:
            log_with_context(level="ERROR", event="invalid_request_format", error="Request is not JSON")
            return jsonify({"error": "Request must be JSON"}), 400
        
        payload = request.get_json()
        if not payload:
            log_with_context(level="ERROR", event="empty_request_payload")
            return jsonify({"error": "Empty request payload"}), 400
        
        # Extract required fields
        job_id = payload.get("job_id")
        user_id = payload.get("user_id")
        gcs_uri = payload.get("gcs_uri")
        
        if not all([job_id, user_id, gcs_uri]):
            log_with_context(
                level="ERROR",
                event="missing_required_fields",
                job_id=job_id,
                user_id=user_id,
                gcs_uri=gcs_uri
            )
            return jsonify({"error": "Missing required fields: job_id, user_id, gcs_uri"}), 400
        
        # Set correlation IDs
        set_correlation_id("job_id", str(job_id))
        set_correlation_id("user_id", str(user_id))
        
        log_with_context(
            level="INFO",
            event="processing_document_task",
            job_id=job_id,
            user_id=user_id,
            gcs_uri=gcs_uri
        )
        
        # Add job_id to request context for logging
        request.environ["X-Job-ID"] = str(job_id)
        
        # Get job information with user validation
        job_info = get_job_with_lock(db.session, job_id, user_id)
        if not job_info:
            log_with_context(
                level="ERROR",
                event="job_not_found",
                job_id=job_id,
                user_id=user_id
            )
            return jsonify({"error": "Job not found"}), 404
        
        # Use advisory lock to ensure only one worker processes this job
        with advisory_lock(db.session, job_id, timeout_seconds=30) as lock_acquired:
            if not lock_acquired:
                log_with_context(
                    level="WARNING",
                    event="advisory_lock_failed",
                    job_id=job_id
                )
                return jsonify({
                    "status": "skipped",
                    "message": "Job is being processed by another worker",
                    "job_id": job_id
                }), 200
            
            # Atomically start job processing
            success, current_status = start_job_processing_atomic(db.session, job_id)
            
            if not success:
                if current_status == "completed":
                    logger.info(f"Job {job_id} already completed, skipping")
                    return jsonify({
                        "status": "skipped",
                        "message": "Job already completed",
                        "job_id": job_id
                    }), 200
                elif current_status == "failed":
                    logger.info(f"Job {job_id} already failed, skipping")
                    return jsonify({
                        "status": "skipped",
                        "message": "Job already failed",
                        "job_id": job_id
                    }), 409
                else:
                    logger.warning(f"Job {job_id} in unexpected status '{current_status}', skipping")
                    return jsonify({
                        "status": "skipped",
                        "message": f"Job in unexpected status: {current_status}",
                        "job_id": job_id
                    }), 200
            
            logger.info(f"Starting processing for job {job_id}")
            
            # Process the job with Storage adapter
            try:
                markdown_content = process_job(job_id, gcs_uri)
                
                # Use Storage adapter for output
                storage = Storage()
                output_path = f"outputs/{job_id}/result.md"
                storage.write_bytes(output_path, markdown_content.encode('utf-8'))
                logger.info(f"Uploaded result to storage: {output_path}")
                
                # Update job with success information
                job = db.session.get(Job, job_id)
                if job:
                    job.output_uri = output_path
                    job.completed_at = datetime.utcnow()
                    job.error_message = None
                    job.status = "completed"
                    db.session.commit()
                
                processing_duration = time.time() - start_time
                bytes_out = len(markdown_content.encode('utf-8'))
                logger.info(f"Successfully completed job {job_id} in {processing_duration:.2f}s")
                logger.info(f"Job {job_id} metrics: output_path={output_path}, bytes_out={bytes_out}")
                
                return jsonify({
                    "status": "completed",
                    "job_id": job_id,
                    "output_uri": output_path,
                    "bytes_out": bytes_out,
                    "processing_duration": processing_duration
                }), 200
                
            except Exception as e:
                # Update job with failure information
                job = db.session.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    db.session.commit()
                
                # Enhanced error logging with full stack trace
                logger.exception(f"Failed to process job {job_id}: {e}")
                return jsonify({
                    "status": "failed",
                    "error": str(e),
                    "job_id": job_id
                }), 500
            
    except Exception as e:
        # Enhanced error logging with full stack trace
        logger.exception(f"Unexpected error processing task: {e}")
        return jsonify({"error": "Internal server error"}), 500
