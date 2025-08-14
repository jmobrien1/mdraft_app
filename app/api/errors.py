from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

api_errors = Blueprint("api_errors", __name__)

@api_errors.app_errorhandler(Exception)
def handle_exception(e):
    # Only force JSON for API routes
    if not request.path.startswith("/api/"):
        # Non-API routes behave normally (HTML)
        if isinstance(e, HTTPException):
            return e
        raise e

    status = 500
    code = "server_error"
    detail = "Internal Server Error"

    if isinstance(e, HTTPException):
        status = e.code or 500
        code = getattr(e, "name", "http_error").lower().replace(" ", "_")
        detail = getattr(e, "description", str(e))

    return jsonify({"error": code, "detail": detail}), status
