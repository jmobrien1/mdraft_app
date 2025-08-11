import os, secrets
from datetime import datetime
from flask import request, abort
from .models_apikey import ApiKey
from . import db

REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "0").lower() in ("1","true","yes")

def _raw_key():
    return request.headers.get("X-API-Key") or request.args.get("api_key") or request.cookies.get("api_key")

def fetch_valid_key():
    k = _raw_key()
    if not k:
        return None
    ak = ApiKey.query.filter_by(key=k, is_active=True).first()
    if ak:
        ak.last_used_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ak
    return None

def require_api_key_if_configured():
    if REQUIRE_API_KEY and not fetch_valid_key():
        abort(401, description="missing_or_invalid_api_key")

def rate_limit_key_func():
    # Limiter identity: use API key if present, else client IP
    return _raw_key() or request.remote_addr or "anonymous"

def rate_limit_for_convert():
    # Per-key limit string; fallback to default env or safe default
    ak = fetch_valid_key()
    if ak and ak.rate_limit:
        return ak.rate_limit
    return os.getenv("CONVERT_RATE_LIMIT_DEFAULT", "30 per minute")

def generate_key():
    # 48 chars urlsafe by default; enough entropy + fits DB
    return secrets.token_urlsafe(36)
