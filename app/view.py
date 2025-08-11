from flask import Blueprint, abort, render_template
from .models_conversion import Conversion
from . import db

bp = Blueprint("view", __name__, url_prefix="/v")

@bp.get("/<id>")
def view_markdown(id):
    conv = db.session.get(Conversion, id)
    if not conv:
        abort(404)
    # Page can handle QUEUED/PROCESSING/FAILED gracefully
    return render_template(
        "view.html",
        id=conv.id,
        filename=conv.filename,
        status=conv.status,
        markdown=(conv.markdown or ""),
        error=conv.error,
    )
