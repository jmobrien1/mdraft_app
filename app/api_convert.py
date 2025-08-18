"""
API endpoints for document conversion.

This module provides RESTful endpoints for uploading documents and
managing conversion jobs. It includes atomic upload handling with
idempotency, progress tracking, and comprehensive error handling.
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request, send_file, Response
from flask_login import current_user
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from . import db
from .models_conversion import Conversion
from .models import User
from .services import Storage
from .celery_tasks import enqueue_conversion_task
from .utils.authz import allow_session_or_api_key
from .utils.csrf import csrf_exempt_for_api
from .utils.rate_limiting import get_upload_rate_limit_key
from .utils.serialization import serialize_conversion_status
from .utils.validation import validate_file_upload
from .utils.files import is_file_allowed, get_file_hash, get_file_size
from .extensions import limiter

# Public mode toggle
PUBLIC = (os.getenv("MDRAFT_PUBLIC_MODE") or "").strip().lower() in {"1","true","yes","on","y"}

bp = Blueprint("api_convert", __name__, url_prefix="/api")

def _links(cid: str):
    return {
        "self": f"/api/conversions/{cid}",
        "markdown": f"/api/conversions/{cid}/markdown",
        "view": f"/v/{cid}",
    }

def _get_owner_fields():
    """Get ownership fields for the current request."""
    from .auth.ownership import get_owner_id_for_creation
    from .auth.visitor import get_or_create_visitor_session_id
    from flask_login import current_user
    
    # Ensure visitor session exists for anonymous users
    if not getattr(current_user, "is_authenticated", False):
        resp = None
        vid, resp = get_or_create_visitor_session_id(resp)
    
    owner_id = get_owner_id_for_creation()
    
    # Get proposal_id if provided in request
    proposal_id = request.form.get("proposal_id") or request.args.get("proposal_id")
    if proposal_id:
        try:
            proposal_id = int(proposal_id)
        except (ValueError, TypeError):
            proposal_id = None
    
    fields = {}
    if getattr(current_user, "is_authenticated", False):
        fields["user_id"] = owner_id
    else:
        fields["visitor_session_id"] = owner_id
    
    if proposal_id:
        fields["proposal_id"] = proposal_id
    
    return fields

def _atomic_upload_handler(file_hash: str, filename: str, original_mime: str, 
                          original_size: int, gcs_uri: str, owner_fields: dict, 
                          ttl_days: int, callback_url: str = None, storage_backend: str = "unknown"):
    """
    Atomic upload handler that ensures idempotency under concurrency.
    
    This function:
    1. Begins a database transaction
    2. Uses SELECT ... FOR UPDATE to lock any existing conversion with the same SHA256+owner
    3. If a COMPLETED conversion exists, returns it immediately
    4. If a pending conversion exists, returns it
    5. Otherwise creates a new conversion and enqueues the task
    6. Commits the transaction
    
    This prevents race conditions where multiple concurrent uploads of the same file
    could create duplicate conversions.
    """
    from .celery_tasks import enqueue_conversion_task
    
    # Start transaction (only if not already in one)
    # Use a try/except approach since in_transaction() might not be available
    try:
        db.session.begin()
    except Exception:
        # Transaction might already be in progress, continue
        pass
    
    try:
        # Build the WHERE clause for the SELECT ... FOR UPDATE query
        where_conditions = ["sha256 = :sha256"]
        params = {"sha256": file_hash}
        
        if owner_fields.get("user_id"):
            where_conditions.append("user_id = :user_id")
            params["user_id"] = owner_fields["user_id"]
        else:
            where_conditions.append("user_id IS NULL")
            
        if owner_fields.get("visitor_session_id"):
            where_conditions.append("visitor_session_id = :visitor_session_id")
            params["visitor_session_id"] = owner_fields["visitor_session_id"]
        else:
            where_conditions.append("visitor_session_id IS NULL")
        
        where_clause = " AND ".join(where_conditions)
        
        # SELECT existing conversion (SQLite doesn't support FOR UPDATE)
        sql_query = f"SELECT id, status, filename, markdown FROM conversions WHERE {where_clause}"
        current_app.logger.info(f"Executing SQL query: {sql_query}")
        current_app.logger.info(f"With parameters: {params}")
        
        result = db.session.execute(
            text(sql_query),
            params
        ).fetchone()
        
        if result:
            existing_id, existing_status, existing_filename, existing_markdown = result
            
            # If completed conversion exists, return it immediately
            if existing_status == "COMPLETED" and existing_markdown:
                current_app.logger.info(f"Idempotency hit: returning existing completed conversion {existing_id} for SHA256 {file_hash[:8]}...")
                db.session.rollback()  # Release the lock
                return {
                    "id": existing_id,  # Frontend expects 'id' first
                    "conversion_id": existing_id,
                    "status": serialize_conversion_status("COMPLETED"),  # Use centralized serialization
                    "filename": existing_filename,
                    "duplicate_of": existing_id,
                    "links": _links(existing_id),
                    "note": "deduplicated",
                    "storage_backend": storage_backend
                }, 200
            
            # If pending/processing conversion exists, return it
            if existing_status in ["QUEUED", "PROCESSING"]:
                current_app.logger.info(f"Duplicate upload detected: returning existing pending conversion {existing_id} for SHA256 {file_hash[:8]}...")
                db.session.rollback()  # Release the lock
                return {
                    "id": existing_id,  # Frontend expects 'id' first
                    "conversion_id": existing_id,
                    "status": serialize_conversion_status(existing_status),  # Use centralized serialization
                    "filename": existing_filename,
                    "links": _links(existing_id),
                    "note": "duplicate_upload",
                    "storage_backend": storage_backend
                }, 202
        
        # No existing conversion found, create a new one
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)) if ttl_days > 0 else None
        
        conv = Conversion(
            filename=filename,
            status="QUEUED",
            sha256=file_hash,
            original_mime=original_mime,
            original_size=original_size,
            stored_uri=gcs_uri,
            expires_at=expires_at,
            **owner_fields
        )
        
        db.session.add(conv)
        db.session.flush()  # Get the ID without committing
        
        conv_id = conv.id
        
        # Enqueue Celery task for async processing
        task_id = enqueue_conversion_task(conv_id, owner_fields.get("user_id"), gcs_uri, callback_url)
        
        # Commit the transaction
        db.session.commit()
        
        current_app.logger.info(f"Created new conversion {conv_id} and enqueued task {task_id} for SHA256 {file_hash[:8]}...")
        
        return {
            "id": conv_id,  # Frontend expects 'id' first
            "conversion_id": conv_id,
            "status": serialize_conversion_status(conv.status),  # Use centralized serialization
            "filename": filename,
            "task_id": task_id,
            "links": _links(conv_id),
            "storage_backend": storage_backend
        }, 202
        
    except IntegrityError as e:
        # Handle unique constraint violation (shouldn't happen with FOR UPDATE, but safety)
        db.session.rollback()
        current_app.logger.warning(f"IntegrityError during atomic upload: {e}")
        
        # Try to find the existing conversion that caused the violation
        from .services.query_service import ConversionQueryService
        existing = ConversionQueryService.get_conversion_by_sha256(
            sha256=file_hash,
            user_id=owner_fields.get("user_id"),
            visitor_session_id=owner_fields.get("visitor_session_id")
        )
        
        if existing:
            return {
                "id": existing.id,  # Frontend expects 'id' first
                "conversion_id": existing.id,
                "status": serialize_conversion_status(existing.status),  # Use centralized serialization
                "filename": existing.filename,
                "links": _links(existing.id),
                "note": "duplicate_detected",
                "storage_backend": storage_backend
            }, 202 if serialize_conversion_status(existing.status) in ["QUEUED", "PROCESSING"] else 200
        
        # If we can't find the existing conversion, something went wrong
        raise
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error in atomic upload handler: {e}")
        raise

def _convert_with_markitdown(path: str) -> str:
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        res = md.convert(path)

        if hasattr(res, "text_content"):
            return res.text_content or ""
        if hasattr(res, "markdown"):
            return res.markdown or ""
        if isinstance(res, str):
            return res
        try:
            return (res.get("text_content") or res.get("markdown") or "")
        except Exception:
            return ""
    except Exception:
        # Fallback: return a small preview so demo never fails
        with open(path, "rb") as fh:
            return fh.read(8192).decode("utf-8", errors="ignore")

@bp.post("/upload")
@limiter.limit(lambda: current_app.config.get("UPLOAD_RATE_LIMIT", "20 per minute"), 
               key_func=lambda: get_upload_rate_limit_key())
@csrf_exempt_for_api
def api_upload():
    """
    Fully async upload endpoint that never blocks on conversion.
    
    This endpoint:
    1. Validates the uploaded file
    2. Calculates SHA256 for idempotency
    3. Uses atomic database operations to ensure only one conversion per file per owner
    4. If duplicate found, returns existing result immediately
    5. Otherwise, saves file to GCS and enqueues Celery task
    6. Returns 202 Accepted with conversion ID for polling
    
    The endpoint is idempotent - multiple identical uploads will only
    create one conversion job, even under high concurrency.
    """
    import os
    from flask_login import current_user
    from flask import current_app
    
    # Add debugging at the very beginning
    current_app.logger.info("=== api_upload() called ===")
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Request path: {request.path}")
    current_app.logger.info(f"Request files: {list(request.files.keys()) if request.files else 'None'}")
    current_app.logger.info(f"Request form: {list(request.form.keys()) if request.form else 'None'}")
    
    # Check if login is required for conversion
    REQUIRE_LOGIN_CONVERT = os.getenv("CONVERT_REQUIRES_LOGIN", "0") in {"1", "true", "True"}
    
    if REQUIRE_LOGIN_CONVERT and not current_user.is_authenticated:
        return jsonify(error="unauthorized"), 401
    if not allow_session_or_api_key():
        return jsonify({"error": "unauthorized"}), 401
    
    # Validate multipart first
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error":"file_required"}), 400
    
    # Config-driven allowlists for file types
    ALLOWED_EXTS = set((current_app.config.get("ALLOWED_EXTENSIONS") or "pdf,docx,txt").split(","))
    ALLOWED_MIMES = set((current_app.config.get("ALLOWED_MIME_TYPES") or "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain").split(","))
    
    # Validate file type by extension and MIME type
    ext_ok = file.filename and file.filename.rsplit(".",1)[-1].lower() in ALLOWED_EXTS
    mime = file.mimetype or ""
    mime_ok = (not ALLOWED_MIMES) or (mime in ALLOWED_MIMES)
    if not ext_ok or not mime_ok:
        return jsonify(error="file_type_not_allowed",
                       allowed_extensions=sorted(ALLOWED_EXTS),
                       detected_mime=mime), 400
    
    # Check file size
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size == 0:
        return jsonify({"error":"file_empty"}), 400
    
    # Validate file using comprehensive validation system
    from .utils.validation import validate_upload_file, ValidationError
    
    # Get correlation ID for logging
    correlation_id = request.headers.get('X-Correlation-ID') or request.headers.get('X-Request-ID')
    
    current_app.logger.info("Starting file validation...")
    validation_result = validate_upload_file(file.stream, file.filename, correlation_id)
    current_app.logger.info("File validation completed successfully")
    
    if not validation_result.is_valid:
        error_response = {"error": validation_result.error.value}
        if validation_result.error == ValidationError.FILE_TOO_LARGE:
            return jsonify(error_response), 413
        elif validation_result.error == ValidationError.EMPTY_FILE:
            return jsonify({"error": "file_empty"}), 400
        elif validation_result.error == ValidationError.VIRUS_DETECTED:
            return jsonify(error_response), 400
        else:
            return jsonify(error_response), 400

    current_app.logger.info("Processing filename and callback URL...")
    current_app.logger.info(f"Original filename: {file.filename}")
    current_app.logger.info(f"File object type: {type(file)}")
    
    try:
        filename = secure_filename(file.filename or "upload.bin")
        current_app.logger.info(f"Secure filename: {filename}")
    except Exception as e:
        current_app.logger.error(f"Error in secure_filename: {type(e).__name__}: {str(e)}")
        raise
    
    callback_url = (
        request.form.get("callback_url")
        or request.args.get("callback_url")
        or (request.json or {}).get("callback_url") if request.is_json else None
    )
    current_app.logger.info(f"Callback URL: {callback_url}")
    
    # Validate callback URL
    if callback_url and not (callback_url.startswith("http://") or callback_url.startswith("https://")):
        current_app.logger.warning(f"Invalid callback URL: {callback_url}")
        return jsonify(error="invalid_callback_url"), 400
    
    current_app.logger.info("Callback URL validation passed")

    # Save file temporarily for processing
    current_app.logger.info("Saving file to temporary location...")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    current_app.logger.info(f"File saved to temporary location: {tmp_path}")
    
    try:
        # Enforce security checks
        current_app.logger.info("Starting security checks...")
        fallback_mime = (file.mimetype or None)
        current_app.logger.info(f"Fallback MIME type: {fallback_mime}")
        mime, category = sniff_category(tmp_path, fallback_mime=fallback_mime)
        current_app.logger.info(f"Security check result - MIME: {mime}, Category: {category}")
        if category is None:
            return jsonify(error="unsupported_media_type", mime=(mime or fallback_mime)), 415
        if not size_ok(tmp_path, category):
            return jsonify(error="payload_too_large", category=category), 413

        # Calculate SHA256 for idempotency
        current_app.logger.info("Calculating SHA256 hash...")
        file_hash = sha256_file(tmp_path)
        current_app.logger.info(f"SHA256 hash calculated: {file_hash[:8]}...")
        original_size = os.path.getsize(tmp_path)
        original_mime = mime or fallback_mime or "application/octet-stream"
        current_app.logger.info(f"File size: {original_size}, MIME: {original_mime}")

        # Check for force flag (bypass idempotency)
        force = (request.args.get("force") in ("1","true","yes"))
        if force:
            # Use the old non-atomic path for forced uploads
            return _legacy_upload_handler(tmp_path, filename, file_hash, original_mime, original_size, callback_url)

        # Upload file using storage with fallback
        try:
            from flask import current_app
            
            # Reset file stream position for upload
            file.stream.seek(0)
            
            # Get storage backend
            kind, handle = current_app.extensions.get("storage", ("local", None))
            current_app.logger.info(f"Storage backend: {kind}, handle: {type(handle).__name__ if handle else 'None'}")
            
            if not handle:
                current_app.logger.error("Storage backend not initialized properly")
                return jsonify({"error": "server_error", "detail": "Storage backend not initialized"}), 500
            
            if kind == "gcs":
                blob_name = secure_filename(file.filename or "upload.bin")
                client, bucket = handle
                blob = bucket.blob(f"uploads/{blob_name}")
                blob.upload_from_file(file.stream, rewind=True)
                source_ref = {"backend":"gcs","bucket":bucket.name,"blob":blob.name}
                gcs_uri = f"gs://{bucket.name}/{blob.name}"
            else:
                source_ref = handle.save(file)  # {"backend":"local","path":..., "name":...}
                gcs_uri = source_ref["path"]
            
            current_app.logger.info(f"Using storage URI: {gcs_uri}")

            # Get owner fields and TTL
            ttl_days = int(os.getenv("RETENTION_DAYS", "30"))
            owner_fields = _get_owner_fields()
            
            # Use atomic upload handler
            return _atomic_upload_handler(
                file_hash, filename, original_mime, original_size,
                gcs_uri, owner_fields, ttl_days, callback_url, kind
            )

        except Exception as e:
            current_app.logger.exception("Upload failed: %s", e)
            current_app.logger.error(f"Upload error details: {type(e).__name__}: {str(e)}")
            # Include more detailed error information for debugging
            error_detail = f"{type(e).__name__}: {str(e)}"
            return jsonify({"error": "server_error", "detail": error_detail[:200]}), 500
    


    finally:
        try: 
            os.unlink(tmp_path)
        except Exception: 
            pass

def _legacy_upload_handler(tmp_path: str, filename: str, file_hash: str, 
                          original_mime: str, original_size: int, callback_url: str = None):
    """
    Legacy upload handler for forced uploads (bypasses idempotency).
    This maintains backward compatibility for the force=true parameter.
    """
    # Check for existing completed conversion with same SHA256 (idempotency)
    from .services.query_service import ConversionQueryService
    existing = ConversionQueryService.get_completed_conversion_by_sha256(sha256=file_hash)
    if existing and existing.markdown:
        current_app.logger.info(f"Idempotency hit: returning existing conversion {existing.id} for SHA256 {file_hash[:8]}...")
        return jsonify({
            "id": existing.id,  # Frontend expects 'id' first
            "conversion_id": existing.id,
            "status": "COMPLETED",
            "filename": existing.filename,
            "duplicate_of": existing.id,
            "links": _links(existing.id),
            "note": "deduplicated",
            "storage_backend": "unknown"  # Legacy handler doesn't know storage backend
        }), 200

    # Check for existing pending/processing conversion with same SHA256
    existing_pending_list = ConversionQueryService.get_pending_conversions_by_sha256(sha256=file_hash)
    existing_pending = existing_pending_list[0] if existing_pending_list else None
    
    if existing_pending:
        current_app.logger.info(f"Duplicate upload detected: returning existing pending conversion {existing_pending.id} for SHA256 {file_hash[:8]}...")
        return jsonify({
            "id": existing_pending.id,  # Frontend expects 'id' first
            "conversion_id": existing_pending.id,
            "status": existing_pending.status,
            "filename": existing_pending.filename,
            "links": _links(existing_pending.id),
            "note": "duplicate_upload",
            "storage_backend": "unknown"  # Legacy handler doesn't know storage backend
        }), 202

    # Upload file using storage with fallback
    try:
        from flask import current_app
        
        # Get storage backend
        kind, handle = current_app.extensions.get("storage", ("local", None))
        
        if kind == "gcs":
            blob_name = f"uploads/{uuid.uuid4()}-{secure_filename(filename)}"
            client, bucket = handle
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(tmp_path)
            gcs_uri = f"gs://{bucket.name}/{blob.name}"
        else:
            # For local storage, we need to save the file and get the path
            with open(tmp_path, 'rb') as f:
                from io import BytesIO
                file_storage = type('FileStorage', (), {
                    'filename': filename,
                    'stream': BytesIO(f.read()),
                    'save': lambda path: None
                })()
                file_storage.stream.seek(0)
                source_ref = handle.save(file_storage)
                gcs_uri = source_ref["path"]

        # Create conversion record
        ttl_days = int(os.getenv("RETENTION_DAYS", "30"))
        owner_fields = _get_owner_fields()
        conv = Conversion(
            filename=filename,
            status="QUEUED",
            sha256=file_hash,
            original_mime=original_mime,
            original_size=original_size,
            stored_uri=gcs_uri,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=ttl_days)) if ttl_days > 0 else None,
            **owner_fields
        )
        db.session.add(conv)
        db.session.commit()
        
        conv_id = conv.id

        # Enqueue Celery task for async processing
        from .celery_tasks import enqueue_conversion_task
        task_id = enqueue_conversion_task(conv_id, owner_fields.get("user_id"), gcs_uri, callback_url)

        current_app.logger.info(f"Enqueued conversion task {task_id} for conversion {conv_id} (SHA256: {file_hash[:8]}...)")

        current_app.logger.info("=== Preparing response ===")
        try:
            links = _links(conv_id)
            current_app.logger.info(f"Generated links: {links}")
            
            response_data = {
                "id": conv_id,  # Frontend expects 'id' first
                "conversion_id": conv_id,
                "status": conv.status,
                "filename": filename,
                "task_id": task_id,
                "links": links,
                "storage_backend": kind
            }
            current_app.logger.info(f"Response data prepared: {response_data}")
            
            response = jsonify(response_data)
            current_app.logger.info("=== Response created successfully ===")
            return response, 202
            
        except Exception as response_error:
            current_app.logger.error(f"Error creating response: {type(response_error).__name__}: {str(response_error)}")
            raise

    except Exception as e:
        current_app.logger.exception("Upload failed: %s", e)
        if conv is not None:
            try:
                conv.status = "FAILED"
                conv.error = str(e)
                db.session.commit()
            except Exception:
                db.session.rollback()
        resp = {"error": "server_error"}
        if conv_id:
            resp["id"] = conv_id
            resp["links"] = {"self": f"/api/conversions/{conv_id}"}
        return jsonify(resp), 500

@bp.get("/conversions/<id>")
@csrf_exempt_for_api
def get_conversion(id):
    current_app.logger.info(f"=== get_conversion() called with id: {id} ===")
    
    try:
        conv = Conversion.query.get_or_404(id)
        current_app.logger.info(f"Found conversion: {conv.id}, status: {conv.status}")
        
        # Check if this is an async task that failed
        error_details = None
        status_value = serialize_conversion_status(conv.status)
        if status_value == "FAILED" and conv.error:
            current_app.logger.info(f"Conversion failed with error: {conv.error}")
            error_details = {
                "error": conv.error,
                "readable_message": _get_readable_error_message(conv.error)
            }
        
        # Defensive progress handling - prevents 500s if column doesn't exist
        current_app.logger.info("Getting progress...")
        progress = getattr(conv, "progress", None)
        if progress is None:
            # Guess a sane default from status if you have it
            status_str = status_value.lower()
            progress = 100 if status_str in {"done", "completed", "finished", "success"} else 0
            current_app.logger.info(f"Progress was None, using default: {progress} based on status: {status_str}")
        else:
            current_app.logger.info(f"Progress from database: {progress}")
        
        current_app.logger.info("Preparing response data...")
        
        status_value = serialize_conversion_status(conv.status)
        current_app.logger.info(f"Status enum: {conv.status}, Status value: {status_value}")
        
        response_data = {
            "id": conv.id,  # Frontend expects 'id' first
            "conversion_id": conv.id,
            "filename": conv.filename,
            "status": status_value,  # Use centralized serialization
            "progress": progress,
            "error": error_details,
            "links": {
                "markdown": f"/api/conversions/{conv.id}/markdown",
                "view": f"/v/{conv.id}",
            }
        }
        current_app.logger.info(f"Response data prepared: {response_data}")
        
        response = jsonify(response_data)
        current_app.logger.info("=== get_conversion() returning successfully ===")
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error in get_conversion: {type(e).__name__}: {str(e)}")
        raise


def _get_readable_error_message(error_text: str) -> str:
    """Convert technical error messages to user-friendly messages."""
    error_lower = error_text.lower()
    
    if "file not found" in error_lower or "no such file" in error_lower:
        return "The uploaded file could not be found or processed. Please try uploading again."
    elif "unsupported" in error_lower or "file type" in error_lower:
        return "This file type is not supported. Please upload a PDF, DOCX, or other supported document format."
    elif "size" in error_lower or "too large" in error_lower:
        return "The file is too large. Please upload a smaller file (under 50MB)."
    elif "permission" in error_lower or "access" in error_lower:
        return "Permission denied. Please check your account status and try again."
    elif "network" in error_lower or "connection" in error_lower:
        return "Network error occurred. Please check your connection and try again."
    elif "timeout" in error_lower:
        return "The conversion took too long and timed out. Please try again with a smaller file."
    elif "memory" in error_lower or "out of memory" in error_lower:
        return "The file is too complex to process. Please try with a simpler document."
    else:
        return "An error occurred during conversion. Please try again or contact support if the problem persists."

@bp.get("/conversions/<id>/markdown")
@csrf_exempt_for_api
def get_conversion_markdown(id):
    conv = Conversion.query.get_or_404(id)
    return Response((conv.markdown or ""), mimetype="text/markdown")

@bp.post("/convert")
@limiter.limit(lambda: current_app.config.get("UPLOAD_RATE_LIMIT", "20 per minute"), 
               key_func=lambda: get_upload_rate_limit_key())
@csrf_exempt_for_api
def api_convert():
    """
    Alias for /api/upload endpoint to maintain UI compatibility.
    
    This endpoint provides the same functionality as /api/upload but
    uses the /api/convert path that the UI expects.
    """
    import os
    from flask import make_response, current_app
    from app.auth.visitor import get_or_create_visitor_session_id
    from flask_login import current_user
    
    # Add debugging at the very beginning
    current_app.logger.info("=== api_convert() called ===")
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Request path: {request.path}")
    current_app.logger.info(f"Request files: {list(request.files.keys()) if request.files else 'None'}")
    current_app.logger.info(f"Request form: {list(request.form.keys()) if request.form else 'None'}")
    
    # Check if login is required for conversion
    REQUIRE_LOGIN_CONVERT = os.getenv("CONVERT_REQUIRES_LOGIN", "0") in {"1", "true", "True"}
    
    if REQUIRE_LOGIN_CONVERT and not current_user.is_authenticated:
        return jsonify(error="unauthorized"), 401
    
    # Ensure visitor session exists for anonymous users
    if not getattr(current_user, "is_authenticated", False):
        resp = make_response()
        vid, resp = get_or_create_visitor_session_id(resp)
    
    if not allow_session_or_api_key():
        return jsonify({"error": "unauthorized"}), 401
    
    # Call api_upload and handle visitor session cookie
    result = api_upload()
    
    # If this is an anonymous user, we need to add the visitor session cookie
    if not getattr(current_user, "is_authenticated", False):
        # Convert the result to a response object if it's not already
        if isinstance(result, tuple):
            response_data, status_code = result
            resp = make_response(response_data, status_code)
        else:
            resp = make_response(result)
        
        # Add visitor session cookie
        vid, resp = get_or_create_visitor_session_id(resp)
        return resp
    
    return result

@bp.get("/conversions")
@limiter.limit("240 per minute")  # Rate limit configured in centralized config
@csrf_exempt_for_api
def list_conversions():
    from flask import request, jsonify, current_app, make_response, g
    try:
        limit = max(1, min(int(request.args.get("limit", 10)), 50))
        offset = max(0, int(request.args.get("offset", 0)))
        public = bool(os.getenv("MDRAFT_PUBLIC_MODE"))
        
        # Get owner filter for the current request
        from app.auth.ownership import get_owner_tuple
        from app.auth.visitor import get_or_create_visitor_session_id
        from flask_login import current_user
        
        # Ensure visitor session exists for anonymous users
        if not getattr(current_user, "is_authenticated", False):
            resp = make_response()
            vid, resp = get_or_create_visitor_session_id(resp)
        
        who, val = get_owner_tuple()
        
        if who and val:
            # Filter by owner using join to proposals for robust ownership enforcement
            from app.models import Proposal
            
            q = (db.session.query(Conversion)
                 .outerjoin(Proposal, Conversion.proposal_id == Proposal.id))
            
            if who == "user":
                # Filter by user ownership (either direct or via proposal)
                q = q.filter(
                    (Proposal.user_id == val) | 
                    (Conversion.user_id == val)
                )
            else:
                # Filter by visitor session ownership (either direct or via proposal)
                q = q.filter(
                    (Proposal.visitor_session_id == val) | 
                    (Conversion.visitor_session_id == val)
                )
            
            q = q.order_by(Conversion.created_at.desc()).offset(offset).limit(limit)
        elif public:
            # Public mode - show all conversions
            q = (Conversion.query
                 .order_by(Conversion.created_at.desc())
                 .offset(offset).limit(limit))
        else:
            # Not public and no owner - return empty list
            resp = make_response(jsonify([]), 200)
            resp.headers["X-Limit"] = str(limit)
            resp.headers["X-Offset"] = str(offset)
            return resp

        items = []
        for c in q.all():
            # Defensive progress handling - prevents 500s if column doesn't exist
            progress = getattr(c, "progress", None)
            if progress is None:
                # Guess a sane default from status if you have it
                status_str = serialize_conversion_status(c.status).lower()
                progress = 100 if status_str in {"done", "completed", "finished", "success"} else 0
            
            # Use centralized serialization to prevent JSON serialization errors
            from app.utils.serialization import serialize_conversion_status
            
            items.append({
                "id": c.id,
                "filename": c.filename,
                "status": serialize_conversion_status(c.status),  # Use centralized serialization
                "progress": progress,
                "created_at": c.created_at.isoformat(),
                "links": {
                    "self": f"/api/conversions/{c.id}",
                    "markdown": f"/api/conversions/{c.id}/markdown",
                    "view": f"/v/{c.id}",
                },
            })

        resp = make_response(jsonify(items), 200)
        resp.headers["X-Limit"] = str(limit)
        resp.headers["X-Offset"] = str(offset)
        
        # Set visitor session cookie if needed
        if not getattr(current_user, "is_authenticated", False):
            vid, resp = get_or_create_visitor_session_id(resp)
        
        return resp
    except Exception as e:
        current_app.logger.exception("/api/conversions failed")
        return jsonify({"error":"conversions_failed","detail":str(e)[:200]}), 500

# CSRF exemption for multipart uploads
try:
    from app.extensions import csrf
    csrf.exempt(bp)
except Exception:
    pass
