"""
API error handlers for the mdraft application.

This module provides custom error handlers for API endpoints,
ensuring consistent JSON responses for errors.
"""
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

errors = Blueprint("errors", __name__)


@errors.app_errorhandler(401)
def handle_unauth(e):
    """Handle 401 Unauthorized errors for API endpoints."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorized", "detail": "Login required"}), 401
    return e


@errors.app_errorhandler(Exception)
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
