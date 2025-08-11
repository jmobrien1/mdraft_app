import os, csv, io
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, redirect, url_for, make_response, abort, jsonify
from .models_conversion import Conversion
from .models_apikey import ApiKey
from .auth_api import generate_key
from . import db

bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

@bp.before_request
def guard():
    # allow login page
    if request.endpoint and request.endpoint.endswith("admin.login"):
        return
    if not ADMIN_TOKEN:
        abort(404)  # dashboard disabled if no token configured
    tok = request.cookies.get("admin_token") or request.headers.get("X-Admin-Token") or request.args.get("token")
    if tok != ADMIN_TOKEN:
        return redirect(url_for("admin.login", next=request.path))

@bp.get("/login")
def login():
    return render_template("admin/login.html", next=request.args.get("next", "/admin"))

@bp.post("/login")
def login_post():
    token = request.form.get("token", "")
    nxt = request.form.get("next") or "/admin"
    if token == ADMIN_TOKEN:
        resp = redirect(nxt)
        resp.set_cookie("admin_token", token, httponly=True, samesite="Lax", secure=True, max_age=60*60*6)
        return resp
    return render_template("admin/login.html", next=nxt, error="Invalid token"), 401

@bp.get("/")
def index():
    q = request.args.get("q","").strip()
    status = request.args.get("status","").strip()
    days = int(request.args.get("days","7"))
    since = datetime.utcnow() - timedelta(days=days)

    query = Conversion.query.filter(Conversion.created_at >= since)
    if status:
        query = query.filter_by(status=status)
    if q:
        like = f"%{q}%"
        query = query.filter(Conversion.filename.ilike(like))
    rows = query.order_by(Conversion.created_at.desc()).limit(200).all()

    metrics = {
        "total": Conversion.query.count(),
        "since": len(rows),
        "completed_24h": Conversion.query.filter(Conversion.created_at >= datetime.utcnow()-timedelta(days=1), Conversion.status=="COMPLETED").count(),
        "failed_24h": Conversion.query.filter(Conversion.created_at >= datetime.utcnow()-timedelta(days=1), Conversion.status=="FAILED").count(),
    }
    return render_template("admin/index.html", rows=rows, metrics=metrics, q=q, status=status, days=days)

@bp.get("/export.csv")
def export_csv():
    since_days = int(request.args.get("days","7"))
    since = datetime.utcnow() - timedelta(days=since_days)
    rows = Conversion.query.filter(Conversion.created_at >= since).order_by(Conversion.created_at.desc()).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id","filename","status","created_at","error"])
    for r in rows:
        w.writerow([r.id, r.filename, r.status, r.created_at.isoformat() if r.created_at else "", (r.error or "")[:1000]])
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = 'attachment; filename="conversions.csv"'
    return resp

# API key management
@bp.get("/keys")
def keys():
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return render_template("admin/keys.html", keys=keys)

@bp.post("/keys/create")
def keys_create():
    name = request.form.get("name","").strip() or "Unnamed"
    limit = request.form.get("rate_limit","60 per minute").strip() or "60 per minute"
    key = generate_key()
    ak = ApiKey(name=name, key=key, rate_limit=limit, is_active=True)
    db.session.add(ak); db.session.commit()
    return redirect(url_for("admin.keys"))

@bp.post("/keys/<id>/toggle")
def keys_toggle(id):
    ak = db.session.get(ApiKey, id) or abort(404)
    ak.is_active = not ak.is_active
    db.session.commit()
    return redirect(url_for("admin.keys"))

@bp.post("/keys/<id>/rotate")
def keys_rotate(id):
    ak = db.session.get(ApiKey, id) or abort(404)
    ak.key = generate_key()
    db.session.commit()
    return redirect(url_for("admin.keys"))
