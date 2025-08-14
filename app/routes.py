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

from flask import Blueprint, current_app, jsonify, request, send_from_directory, abort, make_response
from sqlalchemy import text

from . import db, limiter
from .models import Job

from app.utils import is_file_allowed, generate_job_id
from .storage import upload_stream_to_gcs, generate_download_url, generate_signed_url, generate_v4_signed_url
from .services import Storage
from .celery_tasks import enqueue_conversion_task
from .services.ai_tools import run_prompt
from .services.text_loader import get_rfp_text
from .schemas.free_capabilities import (
    COMPLIANCE_MATRIX_SCHEMA,
    EVAL_CRITERIA_SCHEMA,
    OUTLINE_SCHEMA,
    SUBMISSION_CHECKLIST_SCHEMA
)


bp = Blueprint("main", __name__)


def _prompt_path(current_app, hyphen_name: str, underscore_name: str) -> str:
    import os
    base = os.path.join(current_app.root_path, "prompts", "free_tier")
    p1 = os.path.join(base, hyphen_name)
    p2 = os.path.join(base, underscore_name)
    if os.path.exists(p1): return p1
    if os.path.exists(p2): return p2
    # default to hyphen path (ai_tools will fall back to in-code DEFAULT_PROMPTS)
    return p1


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


@bp.get("/healthz")
def healthz():
    return "ok", 200


@bp.get("/api/dev/diag")
def dev_diag():
    import os
    from flask import jsonify
    flag = (os.getenv("MDRAFT_DEV_STUB") or "").strip()
    return jsonify({"MDRAFT_DEV_STUB": flag, "stub_detected": flag.lower() in {"1","true","yes","on","y"}}), 200


@bp.get("/api/dev/check-prompts")
def dev_check_prompts():
    import os
    base = os.path.join(current_app.root_path, "prompts", "free_tier")
    files = [
      "compliance-matrix.txt","compliance_matrix.txt",
      "evaluation-criteria.txt","evaluation_criteria.txt",
      "annotated-outline.txt","annotated_outline.txt",
      "submission-checklist.txt","submission_checklist.txt",
    ]
    exists = {f: os.path.exists(os.path.join(base, f)) for f in files}
    flag = (os.getenv("MDRAFT_DEV_STUB") or "").strip()
    return jsonify({"MDRAFT_DEV_STUB": flag, "stub_detected": flag.lower() in {"1","true","yes","on","y"}, "base": base, "exists": exists}), 200


@bp.route("/api/session/bootstrap", methods=["GET"])
def session_bootstrap():
    """Bootstrap a visitor session for anonymous users.
    
    This endpoint ensures every anonymous visitor has a unique session ID
    stored in a secure cookie. It's safe to call multiple times.
    
    Returns:
        JSON response with session status
    """
    from .auth.visitor import get_or_create_visitor_session_id
    
    resp = make_response({"ok": True, "session_ready": True})
    vid, resp = get_or_create_visitor_session_id(resp)
    
    return resp, 200


@bp.route("/api/me/usage", methods=["GET"])
def get_usage():
    """Get usage information for the current user or anonymous visitor.
    
    Returns usage statistics and limits for both authenticated and anonymous users.
    Anonymous users get a minimal usage object with basic limits.
    
    Returns:
        JSON response with usage information
    """
    # Since Flask-Login is disabled, we'll return anonymous usage for now
    # In a real implementation, you'd check for authentication tokens/sessions
    return jsonify({
        "plan": "free-anon",
        "conversions_used": 0,
        "limit": 1,
        "can_convert": True,
        "authenticated": False
    }), 200


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
    
    # Validate file extension
    if not is_file_allowed(file.filename):
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





# Example curl commands for manual testing:
# curl -X POST http://localhost:5000/api/generate/compliance-matrix \
#   -H "Content-Type: application/json" \
#   -d '{"document_id": "123"}'
#
# curl -X POST http://localhost:5000/api/generate/evaluation-criteria \
#   -H "Content-Type: application/json" \
#   -d '{"document_id": "123"}'
#
# curl -X POST http://localhost:5000/api/generate/annotated-outline \
#   -H "Content-Type: application/json" \
#   -d '{"document_id": "123"}'
#
# curl -X POST http://localhost:5000/api/generate/submission-checklist \
#   -H "Content-Type: application/json" \
#   -d '{"document_id": "123"}'


def _stub_on() -> bool:
    return (os.getenv("MDRAFT_DEV_STUB") or "").strip().lower() in {"1","true","yes","on","y"}


@bp.route("/api/generate/compliance-matrix", methods=["POST"])
@limiter.limit(os.getenv("AI_RATE_LIMIT_DEFAULT", "10 per minute"))
def generate_compliance_matrix() -> Any:
    """Generate compliance matrix from RFP document."""
    data = request.get_json(silent=True) or {}
    doc_id = data.get('document_id') or data.get('id')
    if not isinstance(doc_id, str) or not doc_id.strip():
        return jsonify({"error": "document_id required"}), 400

    prompt_path = _prompt_path(current_app, "compliance-matrix.txt", "compliance_matrix.txt")
    current_app.logger.info("gen_compliance_matrix: doc_id=%r prompt=%s", doc_id, prompt_path)

    try:
        if _stub_on():
            # No loader, no model — exercise UI deterministically
            payload = run_prompt(prompt_path, "DEV_STUB_PLACEHOLDER", COMPLIANCE_MATRIX_SCHEMA)
            return jsonify(payload), 200

        # Real path: load text then call model
        rfp_text = get_rfp_text(doc_id)
        if not rfp_text:
            current_app.logger.warning("gen_compliance_matrix: document not found doc_id=%r", doc_id)
            return jsonify({"error": "document not found"}), 404

        # Truncate huge inputs before chunking
        limit = int(os.getenv("MDRAFT_TRUNCATE_CHARS") or 200_000)
        if len(rfp_text or "") > limit:
            rfp_text = rfp_text[:limit]
            current_app.logger.info("truncate: rfp_text -> %d chars", limit)

        payload = run_prompt(prompt_path, rfp_text, COMPLIANCE_MATRIX_SCHEMA)
        return jsonify(payload), 200
    except ValueError as ve:
        s = str(ve) or "model_error"
        code, detail = (s.split("|",1) + [None])[:2] if "|" in s else (s, None)
        
        # Handle validation errors with 422 status
        if code == "validation_error":
            return jsonify({
                "error": "validation_failed", 
                "details": detail,
                "message": "AI response failed validation"
            }), 422
        
        hints = {
            "openai_auth":"Set OPENAI_API_KEY.",
            "openai_permission":"Model/quota access issue.",
            "openai_bad_request":"Check MDRAFT_MODEL (gpt-4o-mini) & JSON mode.",
            "openai_unprocessable":"Input too long; reduce CHUNK_SIZE or TRUNCATE_CHARS.",
            "openai_not_found":"Use MDRAFT_MODEL=gpt-4o-mini.",
            "openai_rate_limit":"Retry / reduce concurrency.",
            "openai_connection":"Network hiccup; retry.",
            "openai_api":"Transient server error; retry.",
            "json_parse":"Model didn't return clean JSON; extractor failed.",
            "model_error":"Generic model error.",
            "openai_other":"Unhandled OpenAI error."
        }
        return jsonify({"error": code, "hint": hints.get(code), "detail": detail}), 502
    except RuntimeError as re:
        # pass-through from llm_client
        code = str(re)
        return jsonify({"error": code}), 502
    except Exception as e:
        current_app.logger.exception("server_error on compliance-matrix: %s", e)
        return jsonify({"error": "server_error"}), 500


@bp.route("/api/generate/evaluation-criteria", methods=["POST"])
@bp.route("/api/generate/evaluation_criteria", methods=["POST"])
@limiter.limit(os.getenv("AI_RATE_LIMIT_DEFAULT", "10 per minute"))
def generate_evaluation_criteria() -> Any:
    """Generate evaluation criteria from RFP document."""
    data = request.get_json(silent=True) or {}
    doc_id = data.get('document_id') or data.get('id')
    if not isinstance(doc_id, str) or not doc_id.strip():
        return jsonify({"error": "document_id required"}), 400

    prompt_path = _prompt_path(current_app, "evaluation-criteria.txt", "evaluation_criteria.txt")
    current_app.logger.info("gen_evaluation_criteria: doc_id=%r prompt=%s", doc_id, prompt_path)

    try:
        if _stub_on():
            # No loader, no model — exercise UI deterministically
            payload = run_prompt(prompt_path, "DEV_STUB_PLACEHOLDER", EVAL_CRITERIA_SCHEMA)
            return jsonify(payload), 200

        # Real path: load text then call model
        rfp_text = get_rfp_text(doc_id)
        if not rfp_text:
            current_app.logger.warning("gen_evaluation_criteria: document not found doc_id=%r", doc_id)
            return jsonify({"error": "document not found"}), 404

        # Truncate huge inputs before chunking
        limit = int(os.getenv("MDRAFT_TRUNCATE_CHARS") or 200_000)
        if len(rfp_text or "") > limit:
            rfp_text = rfp_text[:limit]
            current_app.logger.info("truncate: rfp_text -> %d chars", limit)

        payload = run_prompt(prompt_path, rfp_text, EVAL_CRITERIA_SCHEMA)
        return jsonify(payload), 200
    except ValueError as ve:
        s = str(ve) or "model_error"
        code, detail = (s.split("|",1) + [None])[:2] if "|" in s else (s, None)
        hints = {
            "openai_auth":"Set OPENAI_API_KEY.",
            "openai_permission":"Model/quota access issue.",
            "openai_bad_request":"Check MDRAFT_MODEL (gpt-4o-mini) & JSON mode.",
            "openai_unprocessable":"Input too long; reduce CHUNK_SIZE or TRUNCATE_CHARS.",
            "openai_not_found":"Use MDRAFT_MODEL=gpt-4o-mini.",
            "openai_rate_limit":"Retry / reduce concurrency.",
            "openai_connection":"Network hiccup; retry.",
            "openai_api":"Transient server error; retry.",
            "json_parse":"Model didn't return clean JSON; extractor failed.",
            "model_error":"Generic model error.",
            "openai_other":"Unhandled OpenAI error."
        }
        return jsonify({"error": code, "hint": hints.get(code), "detail": detail}), 502
    except RuntimeError as re:
        # pass-through from llm_client
        code = str(re)
        return jsonify({"error": code}), 502
    except Exception as e:
        current_app.logger.exception("server_error on evaluation-criteria: %s", e)
        return jsonify({"error": "server_error"}), 500


@bp.route("/api/generate/annotated-outline", methods=["POST"])
@limiter.limit(os.getenv("AI_RATE_LIMIT_DEFAULT", "10 per minute"))
def generate_annotated_outline() -> Any:
    """Generate annotated outline from RFP document."""
    data = request.get_json(silent=True) or {}
    doc_id = data.get('document_id') or data.get('id')
    if not isinstance(doc_id, str) or not doc_id.strip():
        return jsonify({"error": "document_id required"}), 400

    prompt_path = _prompt_path(current_app, "annotated-outline.txt", "annotated_outline.txt")
    current_app.logger.info("gen_annotated_outline: doc_id=%r prompt=%s", doc_id, prompt_path)

    try:
        if _stub_on():
            # No loader, no model — exercise UI deterministically
            payload = run_prompt(prompt_path, "DEV_STUB_PLACEHOLDER", OUTLINE_SCHEMA)
            return jsonify(payload), 200

        # Real path: load text then call model
        rfp_text = get_rfp_text(doc_id)
        if not rfp_text:
            current_app.logger.warning("gen_annotated_outline: document not found doc_id=%r", doc_id)
            return jsonify({"error": "document not found"}), 404

        # Truncate huge inputs before chunking
        limit = int(os.getenv("MDRAFT_TRUNCATE_CHARS") or 200_000)
        if len(rfp_text or "") > limit:
            rfp_text = rfp_text[:limit]
            current_app.logger.info("truncate: rfp_text -> %d chars", limit)

        payload = run_prompt(prompt_path, rfp_text, OUTLINE_SCHEMA)
        return jsonify(payload), 200
    except ValueError as ve:
        s = str(ve) or "model_error"
        code, detail = (s.split("|",1) + [None])[:2] if "|" in s else (s, None)
        hints = {
            "openai_auth":"Set OPENAI_API_KEY.",
            "openai_permission":"Model/quota access issue.",
            "openai_bad_request":"Check MDRAFT_MODEL (gpt-4o-mini) & JSON mode.",
            "openai_unprocessable":"Input too long; reduce CHUNK_SIZE or TRUNCATE_CHARS.",
            "openai_not_found":"Use MDRAFT_MODEL=gpt-4o-mini.",
            "openai_rate_limit":"Retry / reduce concurrency.",
            "openai_connection":"Network hiccup; retry.",
            "openai_api":"Transient server error; retry.",
            "json_parse":"Model didn't return clean JSON; extractor failed.",
            "model_error":"Generic model error.",
            "openai_other":"Unhandled OpenAI error."
        }
        return jsonify({"error": code, "hint": hints.get(code), "detail": detail}), 502
    except RuntimeError as re:
        # pass-through from llm_client
        code = str(re)
        return jsonify({"error": code}), 502
    except Exception as e:
        current_app.logger.exception("server_error on annotated-outline: %s", e)
        return jsonify({"error": "server_error"}), 500


@bp.route("/api/generate/submission-checklist", methods=["POST"])
@limiter.limit(os.getenv("AI_RATE_LIMIT_DEFAULT", "10 per minute"))
def generate_submission_checklist() -> Any:
    """Generate submission checklist from RFP document."""
    data = request.get_json(silent=True) or {}
    doc_id = data.get('document_id') or data.get('id')
    if not isinstance(doc_id, str) or not doc_id.strip():
        return jsonify({"error": "document_id required"}), 400

    prompt_path = _prompt_path(current_app, "submission-checklist.txt", "submission_checklist.txt")
    current_app.logger.info("gen_submission_checklist: doc_id=%r prompt=%s", doc_id, prompt_path)

    try:
        if _stub_on():
            # No loader, no model — exercise UI deterministically
            payload = run_prompt(prompt_path, "DEV_STUB_PLACEHOLDER", SUBMISSION_CHECKLIST_SCHEMA)
            return jsonify(payload), 200

        # Real path: load text then call model
        rfp_text = get_rfp_text(doc_id)
        if not rfp_text:
            current_app.logger.warning("gen_submission_checklist: document not found doc_id=%r", doc_id)
            return jsonify({"error": "document not found"}), 404

        # Truncate huge inputs before chunking
        limit = int(os.getenv("MDRAFT_TRUNCATE_CHARS") or 200_000)
        if len(rfp_text or "") > limit:
            rfp_text = rfp_text[:limit]
            current_app.logger.info("truncate: rfp_text -> %d chars", limit)

        payload = run_prompt(prompt_path, rfp_text, SUBMISSION_CHECKLIST_SCHEMA)
        return jsonify(payload), 200
    except ValueError as ve:
        s = str(ve) or "model_error"
        code, detail = (s.split("|",1) + [None])[:2] if "|" in s else (s, None)
        hints = {
            "openai_auth":"Set OPENAI_API_KEY.",
            "openai_permission":"Model/quota access issue.",
            "openai_bad_request":"Check MDRAFT_MODEL (gpt-4o-mini) & JSON mode.",
            "openai_unprocessable":"Input too long; reduce CHUNK_SIZE or TRUNCATE_CHARS.",
            "openai_not_found":"Use MDRAFT_MODEL=gpt-4o-mini.",
            "openai_rate_limit":"Retry / reduce concurrency.",
            "openai_connection":"Network hiccup; retry.",
            "openai_api":"Transient server error; retry.",
            "json_parse":"Model didn't return clean JSON; extractor failed.",
            "model_error":"Generic model error.",
            "openai_other":"Unhandled OpenAI error."
        }
        return jsonify({"error": code, "hint": hints.get(code), "detail": detail}), 502
    except RuntimeError as re:
        # pass-through from llm_client
        code = str(re)
        return jsonify({"error": code}), 502
    except Exception as e:
        current_app.logger.exception("server_error on submission-checklist: %s", e)
        return jsonify({"error": "server_error"}), 500


@bp.get("/api/dev/openai-ping")
def dev_openai_ping():
    from app.services.llm_client import chat_json
    try:
        msg = [
            {"role":"system","content":"Return strictly JSON."},
            {"role":"user","content":"Return {\"ok\": true, \"model\": \"echo\"} exactly as JSON."}
        ]
        raw = chat_json(msg, response_json_hint=True)
        return current_app.response_class(raw, mimetype="application/json"), 200
    except RuntimeError as re:
        # pass-through from llm_client
        code = str(re)
        return jsonify({"error": code}), 502
    except Exception as e:
        current_app.logger.exception("openai-ping failed: %s", e)
        return jsonify({"error":"openai_ping_failed"}), 502


@bp.get("/api/dev/openai-ping-detailed")
def dev_openai_ping_detailed():
    from app.services.llm_client import chat_json
    try:
        msg = [
            {"role":"system","content":"Return strictly JSON."},
            {"role":"user","content":"{\"ping\": true, \"model\": \"echo\"}"}
        ]
        raw = chat_json(msg, response_json_hint=True)
        return current_app.response_class(raw, mimetype="application/json"), 200
    except RuntimeError as re:
        # return the code to the client to avoid tailing logs
        return jsonify({"error": str(re)}), 502


@bp.post("/api/dev/gen-smoke")
def dev_gen_smoke():
    from flask import request, jsonify, current_app
    from app.services.ai_tools import run_prompt
    from app.schemas.free_capabilities import (
        COMPLIANCE_MATRIX_SCHEMA, EVAL_CRITERIA_SCHEMA, OUTLINE_SCHEMA, SUBMISSION_CHECKLIST_SCHEMA
    )
    tool = (request.json or {}).get("tool","").strip().lower()
    base = {
      "compliance": ("compliance-matrix.txt","compliance_matrix.txt", COMPLIANCE_MATRIX_SCHEMA),
      "criteria": ("evaluation-criteria.txt","evaluation_criteria.txt", EVAL_CRITERIA_SCHEMA),
      "outline": ("annotated-outline.txt","annotated_outline.txt", OUTLINE_SCHEMA),
      "checklist": ("submission-checklist.txt","submission_checklist.txt", SUBMISSION_CHECKLIST_SCHEMA),
    }
    if tool not in base:
        return jsonify({"error":"tool_required", "allowed": list(base)}), 400

    def _prompt_path(hy, us):
        import os
        base_dir = os.path.join(current_app.root_path, "prompts", "free_tier")
        p1 = os.path.join(base_dir, hy)
        p2 = os.path.join(base_dir, us)
        return p1 if os.path.exists(p1) else (p2 if os.path.exists(p2) else p1)

    hy, us, schema = base[tool]
    prompt_path = _prompt_path(hy, us)
    rfp = (
      "SECTION L: Offeror shall submit a Technical Volume not to exceed 10 pages. "
      "Acknowledge all amendments. "
      "SECTION M: Evaluation factors include Technical Approach (40%), Past Performance, and Price. "
      "SECTION C: Contractor must provide a PMP-certified Project Manager."
    )
    try:
        payload = run_prompt(prompt_path, rfp, schema)
        return jsonify(payload), 200
    except Exception as e:
        current_app.logger.exception("dev_gen_smoke failed")
        return jsonify({"error":"dev_gen_smoke_failed","detail":str(e)[:200]}), 502


@bp.get("/api/dev/selftest")
def dev_selftest():
    import os
    from sqlalchemy import text
    ok = {}
    # DB
    try:
        from app import db
        cnt = db.session.execute(text("select count(*) from alembic_version")).scalar()
        ok["db"] = {"ok": True, "alembic_rows": cnt}
    except Exception as e:
        ok["db"] = {"ok": False, "error": str(e)}
    # Prompts
    base = os.path.join(current_app.root_path, "prompts", "free_tier")
    files = ["compliance-matrix.txt","evaluation-criteria.txt","annotated-outline.txt","submission-checklist.txt"]
    ok["prompts"] = {f: os.path.exists(os.path.join(base, f)) for f in files}
    # OpenAI
    try:
        from app.services.llm_client import chat_json
        raw = chat_json(
            [{"role":"system","content":"Return strictly JSON"},
             {"role":"user","content":"{\"ping\":true}"}],
            response_json_hint=True
        )
        ok["openai"] = {"ok": True, "sample": raw[:60]}
    except RuntimeError as re:
        ok["openai"] = {"ok": False, "error": str(re)}
    except Exception as e:
        ok["openai"] = {"ok": False, "error": str(e)}
    return jsonify(ok), 200