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
from .storage import upload_to_gcs, generate_signed_url


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
    single file field named "file".  The file's MIME type is
    validated using its magic number.  If valid, the file is saved to
    the uploads directory, a Job record is created, and a background
    task is enqueued.  A JSON response containing the job ID and
    initial status is returned.
    """
    # Check for file in request
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    # Validate MIME type
    if not is_file_allowed(file.stream):
        return jsonify({"error": "File type not allowed"}), 400
    # Generate a unique filename using job ID
    job_id_str = generate_job_id()
    filename = f"{job_id_str}_{file.filename}"
    # Save file to uploads directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(project_root, "uploads")
    file_path = os.path.join(uploads_dir, filename)
    file.save(file_path)
    
    # Upload to GCS if configured
    gcs_uri = file_path
    bucket_name = current_app.config.get("GCS_BUCKET_NAME")
    if bucket_name:
        gcs_uri = upload_to_gcs(file_path, bucket_name, filename) or file_path
    
    # Create job record in the database.  For this MVP we don't have
    # authentication, so user_id is None.  In a multi‑user system
    # current_user.id would be used instead.
    job = Job(user_id=1, filename=filename, status="queued", gcs_uri=gcs_uri)
    db.session.add(job)
    db.session.commit()
    # Enqueue background task
    add_conversion_task(job.id)
    return jsonify({"job_id": job.id, "status": job.status}), 202


@bp.route("/jobs/<int:job_id>", methods=["GET"])
def job_status(job_id: int) -> Any:
    """Return the status of a conversion job.

    If the job is completed, include a download URL for the processed
    file.  If the job does not exist, return a 404.
    """
    job = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    response: Dict[str, Any] = {"job_id": job.id, "status": job.status}
    if job.status == "completed" and job.output_uri:
        # Generate a signed URL for download
        download_url = generate_signed_url(job.output_uri)
        if download_url:
            response["download_url"] = download_url
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