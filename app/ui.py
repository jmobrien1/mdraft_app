from flask import Blueprint, render_template

bp = Blueprint("ui", __name__)

@bp.get("/")
def index():
    # Simple landing page with an upload form that calls /beta/convert
    return render_template("index.html")
