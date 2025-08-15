import os
import tempfile
from flask import Blueprint, request, jsonify
from flask_login import login_required
from werkzeug.utils import secure_filename

bp = Blueprint("beta", __name__)

@bp.post("/beta/convert")
@login_required
def beta_convert():
    f = request.files.get("file")
    if not f:
        return jsonify(error="file is required (multipart form field 'file')"), 400

    filename = secure_filename(f.filename or "upload.bin")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            res = md.convert(tmp_path)

            # Normalize result to markdown string
            markdown = None
            if hasattr(res, "text_content"):
                markdown = res.text_content
            elif hasattr(res, "markdown"):
                markdown = res.markdown
            elif isinstance(res, str):
                markdown = res
            else:
                try:
                    markdown = res.get("text_content") or res.get("markdown")
                except Exception:
                    markdown = None

            markdown = markdown or ""
            return jsonify({"filename": filename, "markdown": markdown}), 200

        except Exception as e:
            # Fallback so the demo still works if MarkItDown fails
            with open(tmp_path, "rb") as fh:
                preview = fh.read(8192).decode("utf-8", errors="ignore")
            return jsonify({
                "filename": filename,
                "markdown": preview,
                "warning": f"markitdown failed: {type(e).__name__}"
            }), 200
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
