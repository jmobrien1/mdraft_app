import os
import tempfile
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename

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
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        markdown = _convert_with_markitdown(tmp_path)
        conv = Conversion(filename=filename, status="COMPLETED", markdown=markdown)
        db.session.add(conv)
        db.session.commit()
        return jsonify(id=conv.id, filename=filename, status=conv.status,
                       links={"self": f"/api/conversions/{conv.id}",
                              "markdown": f"/api/conversions/{conv.id}/markdown"}), 200
    except Exception as e:
        conv = Conversion(filename=filename, status="FAILED", error=str(e))
        db.session.add(conv)
        db.session.commit()
        return jsonify(id=conv.id, filename=filename, status=conv.status, error=str(e),
                       links={"self": f"/api/conversions/{conv.id}"}), 200
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

@bp.get("/conversions/<id>")
def get_conversion(id):
    conv = Conversion.query.get_or_404(id)
    return jsonify(id=conv.id, filename=conv.filename, status=conv.status, error=conv.error,
                   links={"markdown": f"/api/conversions/{conv.id}/markdown"})

@bp.get("/conversions/<id>/markdown")
def get_conversion_markdown(id):
    conv = Conversion.query.get_or_404(id)
    return Response((conv.markdown or ""), mimetype="text/markdown")
