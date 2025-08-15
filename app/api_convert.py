import os
import tempfile
import uuid
from flask import Blueprint, request, jsonify, Response, current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone

from . import db, limiter
from .models_conversion import Conversion
from .security import sniff_category, size_ok
from .auth_api import require_api_key_if_configured, rate_limit_for_convert, rate_limit_key_func
from .utils.authz import allow_session_or_api_key
from .quality import sha256_file, clean_markdown, pdf_text_fallback
from .webhooks import deliver_webhook
from .utils import is_file_allowed

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

@bp.post("/convert")
@limiter.limit(rate_limit_for_convert, key_func=rate_limit_key_func)
def api_convert():
    if not allow_session_or_api_key():
        return jsonify({"error": "unauthorized"}), 401
    
    # Validate multipart first
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error":"file_required"}), 400
    
    # Check file size
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size == 0:
        return jsonify({"error":"file_empty"}), 400
    
    # Validate file type
    if not is_file_allowed(file.filename):
        return jsonify({"error":"file_type_not_allowed"}), 400

    # Initialize conv and conv_id to prevent UnboundLocalError
    conv = None
    conv_id = None

    filename = secure_filename(file.filename or "upload.bin")
    queue_mode = os.getenv("QUEUE_MODE", "sync").lower()
    use_gcs = os.getenv("USE_GCS", "0").lower() in ("1","true","yes")

    callback_url = (
        request.form.get("callback_url")
        or request.args.get("callback_url")
        or (request.json or {}).get("callback_url") if request.is_json else None
    )
    # optionally validate it's http/https
    if callback_url and not (callback_url.startswith("http://") or callback_url.startswith("https://")):
        return jsonify(error="invalid_callback_url"), 400

    if queue_mode == "async" and use_gcs:
        # Save locally and upload to GCS for the worker to fetch
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        # Enforce security checks
        fallback_mime = (file.mimetype or None)
        mime, category = sniff_category(tmp_path, fallback_mime=fallback_mime)
        if category is None:
            try: os.unlink(tmp_path)
            except Exception: pass
            return jsonify(error="unsupported_media_type", mime=(mime or fallback_mime)), 415
        if not size_ok(tmp_path, category):
            try: os.unlink(tmp_path)
            except Exception: pass
            return jsonify(error="payload_too_large", category=category), 413

        file_hash = sha256_file(tmp_path)
        original_size = os.path.getsize(tmp_path)
        original_mime = mime or fallback_mime or "application/octet-stream"

        # Dedupe unless explicitly forced
        force = (request.args.get("force") in ("1","true","yes"))
        if not force:
            existing = Conversion.query.filter_by(sha256=file_hash, status="COMPLETED").order_by(Conversion.created_at.desc()).first()
            if existing and existing.markdown:
                return jsonify(
                    id=existing.id,
                    filename=existing.filename,
                    status="COMPLETED",
                    duplicate_of=existing.id,
                    links=_links(existing.id),
                    note="deduplicated"
                ), 200
        
        try:
            from google.cloud import storage
            bucket_name = os.environ["GCS_BUCKET_NAME"]
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            object_key = f"uploads/{uuid.uuid4()}-{filename}"
            blob = bucket.blob(object_key)
            blob.upload_from_filename(tmp_path)
            gcs_uri = f"gs://{bucket_name}/{object_key}"

            ttl_days = int(os.getenv("RETENTION_DAYS", "30"))
            owner_fields = _get_owner_fields()
            conv = Conversion(
                filename=filename,
                status="QUEUED",
                sha256=file_hash,
                original_mime=original_mime,
                original_size=original_size,
                stored_uri=None,  # set below
                expires_at=(datetime.utcnow() + timedelta(days=ttl_days)) if ttl_days > 0 else None,
                **owner_fields
            )
            db.session.add(conv)
            db.session.commit()
            
            # Set conv_id immediately after committing
            conv_id = conv.id

            conv.stored_uri = gcs_uri
            db.session.commit()

            from celery_worker import celery
            celery.send_task("convert_from_gcs", args=[conv.id, gcs_uri, filename, callback_url])

            resp = {
                "id": conv_id,
                "filename": filename,
                "status": conv.status,
                "links": _links(conv_id),
            }
            if callback_url:
                resp["callback_url"] = callback_url
            return jsonify(resp), 202
        except Exception as e:
            current_app.logger.exception("convert_failed: %s", e)
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
        finally:
            try: os.unlink(tmp_path)
            except Exception: pass

    # ---------- synchronous fallback (existing behavior) ----------
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Enforce security checks
    fallback_mime = (file.mimetype or None)
    mime, category = sniff_category(tmp_path, fallback_mime=fallback_mime)
    if category is None:
        try: os.unlink(tmp_path)
        except Exception: pass
        return jsonify(error="unsupported_media_type", mime=(mime or fallback_mime)), 415
    if not size_ok(tmp_path, category):
        try: os.unlink(tmp_path)
        except Exception: pass
        return jsonify(error="payload_too_large", category=category), 413

    file_hash = sha256_file(tmp_path)
    original_size = os.path.getsize(tmp_path)
    original_mime = mime or fallback_mime or "application/octet-stream"

    # Dedupe unless explicitly forced
    force = (request.args.get("force") in ("1","true","yes"))
    if not force:
        existing = Conversion.query.filter_by(sha256=file_hash, status="COMPLETED").order_by(Conversion.created_at.desc()).first()
        if existing and existing.markdown:
            return jsonify(
                id=existing.id,
                filename=existing.filename,
                status="COMPLETED",
                duplicate_of=existing.id,
                links=_links(existing.id),
                note="deduplicated"
            ), 200

    try:
        # Wrap downstream converter in try/except and map expected failures
        try:
            markdown = _convert_with_markitdown(tmp_path) or ""
            if not markdown and original_mime == "application/pdf":
                fb = pdf_text_fallback(tmp_path)
                if fb:
                    markdown = fb
            markdown = clean_markdown(markdown)
        except Exception as e:
            current_app.logger.exception("extract_failed: %s", e)
            return jsonify({"error":"extract_failed"}), 422

        ttl_days = int(os.getenv("RETENTION_DAYS", "30"))
        owner_fields = _get_owner_fields()
        conv = Conversion(
            filename=filename,
            status="COMPLETED",
            markdown=markdown,
            sha256=file_hash,
            original_mime=original_mime,
            original_size=original_size,
            stored_uri=None,
            expires_at=(datetime.utcnow() + timedelta(days=ttl_days)) if ttl_days > 0 else None,
            **owner_fields
        )
        db.session.add(conv)
        db.session.commit()
        
        # Set conv_id immediately after committing
        conv_id = conv.id
        
        if callback_url:
            try:
                code, _ = deliver_webhook(
                    callback_url,
                    "conversion.completed",
                    {
                        "id": conv_id,
                        "filename": conv.filename,
                        "status": "COMPLETED",
                        "links": _links(conv_id),
                    },
                )
                current_app.logger.info("webhook_delivered_sync", extra={"url": callback_url, "code": code})
            except Exception as e:
                current_app.logger.exception("webhook_sync_error: %s", e)
        
        return jsonify(
            id=conv_id,
            filename=filename,
            status=conv.status,
            links=_links(conv_id),
        ), 200
    except Exception as e:
        current_app.logger.exception("convert_failed: %s", e)
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
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

@bp.get("/conversions/<id>")
def get_conversion(id):
    conv = Conversion.query.get_or_404(id)
    return jsonify(
        id=conv.id,
        filename=conv.filename,
        status=conv.status,
        error=conv.error,
        links={
            "markdown": f"/api/conversions/{conv.id}/markdown",
            "view": f"/v/{conv.id}",
        }
    )

@bp.get("/conversions/<id>/markdown")
def get_conversion_markdown(id):
    conv = Conversion.query.get_or_404(id)
    return Response((conv.markdown or ""), mimetype="text/markdown")

@bp.get("/conversions")
@limiter.limit(os.getenv("LIST_RATE_LIMIT", "240 per minute"))
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

        items = [{
            "id": c.id,
            "filename": c.filename,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
            "links": {
                "self": f"/api/conversions/{c.id}",
                "markdown": f"/api/conversions/{c.id}/markdown",
                "view": f"/v/{c.id}",
            },
        } for c in q.all()]

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
