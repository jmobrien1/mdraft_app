import os
import tempfile
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

bp = Blueprint("beta", __name__)

@bp.post("/beta/convert")
def beta_convert():
    f = request.files.get("file")
    if not f:
        return jsonify(error="file is required. Send as multipart form field named 'file'."), 400

    filename = secure_filename(f.filename or "upload.bin")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        try:
            # Try MarkItDown if available
            from markitdown import MarkItDown
            md = MarkItDown()
            res = md.convert(tmp_path)

            # Try to extract markdown/text content from different possible return shapes
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

            if not markdown:
                markdown = ""

            return jsonify({"filename": filename, "markdown": markdown}), 200

        except Exception as e:
            # Safe fallback: return the first few KB of text so the endpoint still demos
            with open(tmp_path, "rb") as fh:
                head = fh.read(8192)
            preview = head.decode("utf-8", errors="ignore")
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
