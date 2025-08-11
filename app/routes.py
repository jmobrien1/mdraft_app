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
from .tasks import add_conversion_task
from .utils import is_file_allowed, generate_job_id
from .storage import upload_stream_to_gcs, generate_download_url, generate_signed_url, generate_v4_signed_url


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
@limiter.limit("20 per minute")
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
    
    # Stream upload to GCS
    gcs_uri = None
    bucket_name = current_app.config.get("GCS_BUCKET_NAME")
    if bucket_name:
        # Reset stream position after validation
        file.stream.seek(0)
        gcs_uri = upload_stream_to_gcs(file.stream, bucket_name, filename)
    
    # Fallback to local storage if GCS upload failed or not configured
    if not gcs_uri:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.join(project_root, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        file_path = os.path.join(uploads_dir, filename)
        
        # Reset stream position after validation
        file.stream.seek(0)
        file.save(file_path)
        gcs_uri = file_path
    
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
        task_name = add_conversion_task(job.id, job.user_id, gcs_uri)
        if task_name:
            current_app.logger.info(f"Enqueued conversion task {task_name} for job {job.id}")
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
        if job.output_uri.startswith("gs://"):
            # Parse GCS URI and generate V4 signed URL with download headers
            bucket_name = job.output_uri.split("/")[2]
            blob_name = "/".join(job.output_uri.split("/")[3:])
            
            # Generate safe filename for download: job_<id>.md
            safe_filename = f"job_{job.id}.md"
            response_content_disposition = f"attachment; filename={safe_filename}"
            
            output_signed_url = generate_v4_signed_url(
                bucket_name, 
                blob_name, 
                "GET", 
                15,  # 15 minutes default
                response_content_disposition=response_content_disposition,
                response_content_type="text/markdown"
            )
            if output_signed_url:
                response["output_signed_url"] = output_signed_url
        else:
            # Local file, generate local download URL
            output_signed_url = generate_signed_url(job.output_uri)
            if output_signed_url:
                response["output_signed_url"] = output_signed_url
    
    return jsonify(response)


@bp.route("/download/<path:filename>", methods=["GET"])
def download_file(filename: str) -> Any:
    """Serve a processed file from the processed directory.

    This endpoint is provided for development convenience.  In
    production, files should be served directly from GCS using
    temporary signed URLs.  An expiry query parameter is accepted but
    ignored in this stub.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    processed_dir = os.path.join(project_root, "processed")
    return send_from_directory(processed_dir, filename, as_attachment=True)