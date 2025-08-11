from flask import Blueprint, abort, render_template
from .models_conversion import Conversion
from . import db

bp = Blueprint("view", __name__, url_prefix="/v")

@bp.get("/<id>")
def view_markdown(id):
    conv = db.session.get(Conversion, id)
    if not conv or not conv.markdown:
        abort(404)
    return render_template("view.html", filename=conv.filename, markdown=conv.markdown)
