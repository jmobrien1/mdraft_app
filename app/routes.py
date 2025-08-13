"""
HTTP route definitions for mdraft.

This module defines the web API exposed by the mdraft application.  It
provides endpoints for health checking, file upload, job status
retrieval, and downloading processed files.  Each route includes
appropriate validation and uses the configured extensions for rate
limiting and database access.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request, send_from_directory, abort
from sqlalchemy import text

from . import db, limiter
from .models import Job

from .utils import is_file_allowed, generate_job_id
from .storage import upload_stream_to_gcs, generate_download_url, generate_signed_url, generate_v4_signed_url
from .services import Storage
from .celery_tasks import enqueue_conversion_task


bp = Blueprint("main", __name__)


@bp.route("/", methods=["GET"])
def index() -> Any:
    """Return a welcome message indicating the service is running."""
    return jsonify({"status": "ok", "message": "Welcome to mdraft!"})


@bp.route("/health", methods=["GET"])
def health_check() -> Any:
    """Simple health check that verifies database connectivity.

    Executes a trivial query against the database.  If the query fails
    an exception will be raised and a 503 response returned.
    """
    try:
        # Execute a simple SELECT to validate the connection.  Using
        # text() ensures raw SQL execution without model imports.
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"})
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Database health check failed")
        return jsonify({"status": "database_error"}), 503


@bp.route("/upload", methods=["POST"])
@limiter.limit(os.getenv("CONVERT_RATE_LIMIT_DEFAULT", "20 per minute"))
def upload() -> Any:
    """Handle document upload and enqueue a conversion job.

    This endpoint expects a multipart/form-data request containing a
    single file field named "file". The file's MIME type is validated
    using its magic number. If valid, the file is streamed directly to
    GCS using upload_from_file, a Job record is created with status='queued',
    and a background task is enqueued. A JSON response containing the job ID
    is returned.
    """
    # Check for file in request
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    
    # Validate MIME type using magic number and allowed MIME types
    if not is_file_allowed(file.stream, file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    # Generate a unique filename using job ID
    job_id_str = generate_job_id()
    filename = f"{job_id_str}_{file.filename}"
    
    # Use Storage adapter for upload
    storage = Storage()
    upload_path = f"uploads/{job_id_str}/{file.filename}"
    
    try:
        # Reset stream position after validation
        file.stream.seek(0)
        file_data = file.read()
        storage.write_bytes(upload_path, file_data)
        
        # Store the path for job tracking
        gcs_uri = upload_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to upload file {filename}: {e}")
        return jsonify({"error": "Upload failed"}), 500
    
    # Create job record in the database with status='queued'
    # For this MVP we don't have authentication, so user_id is 1
    # In a multi-user system current_user.id would be used instead
    job = Job(
        user_id=1,
        filename=filename,
        status="queued",
        gcs_uri=gcs_uri
    )
    db.session.add(job)
    db.session.commit()
    
    # Add job_id to request context for logging
    request.environ["X-Job-ID"] = str(job.id)
    
    # Enqueue background task for conversion
    try:
        task_id = enqueue_conversion_task(job.id, job.user_id, gcs_uri)
        if task_id:
            current_app.logger.info(f"Enqueued conversion task {task_id} for job {job.id}")
        else:
            current_app.logger.warning(f"Failed to enqueue conversion task for job {job.id}")
    except Exception as e:
        # Enhanced error logging with full stack trace
        current_app.logger.exception(f"Error enqueueing conversion task for job {job.id}: {e}")
        # Don't fail the upload if task enqueueing fails
    
    return jsonify({"job_id": job.id}), 202


@bp.route("/jobs/<int:job_id>", methods=["GET"])
def job_status(job_id: int) -> Any:
    """Return the status of a conversion job.

    Returns JSON with status, output_signed_url (V4 signed, 15 min) if available,
    started_at, completed_at, and error information.
    """
    # Add job_id to request context for logging
    request.environ["X-Job-ID"] = str(job_id)
    
    job = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    
    # Build response with status and timing information
    response: Dict[str, Any] = {
        "job_id": job.id,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    
    # Add error information if job failed
    if job.status == "failed" and job.error_message:
        response["error"] = job.error_message
    
    # Add output signed URL if job is completed and has output
    if job.status == "completed" and job.output_uri:
        try:
            storage = Storage()
            
            # Check if the file exists in storage
            if storage.exists(job.output_uri):
                # Generate safe filename for download: job_<id>.md
                safe_filename = f"job_{job.id}.md"
                
                # For now, return a simple download URL
                # In production, you might want to generate signed URLs for GCS
                response["output_signed_url"] = f"/download/{job.output_uri}"
                response["output_filename"] = safe_filename
            else:
                current_app.logger.warning(f"Output file not found in storage: {job.output_uri}")
        except Exception as e:
            current_app.logger.error(f"Error checking output file: {e}")
    
    return jsonify(response)


@bp.route("/download/<path:storage_path>", methods=["GET"])
def download_file(storage_path: str) -> Any:
    """Serve a file from storage.

    This endpoint serves files from the Storage adapter (GCS or local).
    It's provided for development convenience. In production, files should
    be served directly from GCS using temporary signed URLs.
    """
    try:
        storage = Storage()
        
        # Check if file exists
        if not storage.exists(storage_path):
            return jsonify({"error": "File not found"}), 404
        
        # Read file data
        file_data = storage.read_bytes(storage_path)
        
        # Determine filename for download
        filename = storage_path.split('/')[-1]
        if not filename:
            filename = "download"
        
        # Return file as attachment
        from flask import Response
        response = Response(file_data, mimetype='application/octet-stream')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error serving file {storage_path}: {e}")
        return jsonify({"error": "Internal server error"}), 500