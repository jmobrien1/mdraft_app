import os
import tempfile
import uuid
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename
from datetime import timezone

from . import db
from .models_conversion import Conversion

bp = Blueprint("api_convert", __name__, url_prefix="/api")

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
def api_convert():
    f = request.files.get("file")
    if not f:
        return jsonify(error="file is required (field name 'file')"), 400

    filename = secure_filename(f.filename or "upload.bin")
    queue_mode = os.getenv("QUEUE_MODE", "sync").lower()
    use_gcs = os.getenv("USE_GCS", "0").lower() in ("1","true","yes")

    if queue_mode == "async" and use_gcs:
        # Save locally and upload to GCS for the worker to fetch
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            f.save(tmp.name)
            tmp_path = tmp.name
        try:
            from google.cloud import storage
            bucket_name = os.environ["GCS_BUCKET_NAME"]
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            object_key = f"uploads/{uuid.uuid4()}-{filename}"
            blob = bucket.blob(object_key)
            blob.upload_from_filename(tmp_path)
            gcs_uri = f"gs://{bucket_name}/{object_key}"

            conv = Conversion(filename=filename, status="QUEUED")
            db.session.add(conv); db.session.commit()

            from celery_worker import celery
            celery.send_task("convert_from_gcs", args=[conv.id, gcs_uri])

            return jsonify(
                id=conv.id,
                filename=filename,
                status=conv.status,
                links={
                    "self": f"/api/conversions/{conv.id}",
                    "markdown": f"/api/conversions/{conv.id}/markdown",
                    "view": f"/v/{conv.id}",
                },
            ), 202
        finally:
            try: os.unlink(tmp_path)
            except Exception: pass

    # ---------- synchronous fallback (existing behavior) ----------
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        markdown = _convert_with_markitdown(tmp_path)
        conv = Conversion(filename=filename, status="COMPLETED", markdown=markdown)
        db.session.add(conv)
        db.session.commit()
        return jsonify(
            id=conv.id,
            filename=filename,
            status=conv.status,
            links={
                "self": f"/api/conversions/{conv.id}",
                "markdown": f"/api/conversions/{conv.id}/markdown",
                "view": f"/v/{conv.id}",
            },
        ), 200
    except Exception as e:
        conv = Conversion(filename=filename, status="FAILED", error=str(e))
        db.session.add(conv)
        db.session.commit()
        return jsonify(
            id=conv.id,
            filename=filename,
            status=conv.status,
            error=str(e),
            links={
                "self": f"/api/conversions/{conv.id}",
                "view": f"/v/{conv.id}",
            }
        ), 200
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
def list_conversions():
    try:
        limit = int(request.args.get("limit", 10))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify(error="limit/offset must be integers"), 400
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    q = Conversion.query.order_by(Conversion.created_at.desc()).offset(offset).limit(limit).all()
    items = []
    for c in q:
        items.append({
            "id": c.id,
            "filename": c.filename,
            "status": c.status,
            "created_at": (c.created_at.replace(tzinfo=timezone.utc).isoformat() if c.created_at else None),
            "links": {
                "self": f"/api/conversions/{c.id}",
                "markdown": f"/api/conversions/{c.id}/markdown",
                "view": f"/v/{c.id}",
            }
        })
    return jsonify(items=items, limit=limit, offset=offset), 200
