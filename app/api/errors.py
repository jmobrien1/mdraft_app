"""
API error handlers for the mdraft application.

This module provides custom error handlers for API endpoints,
ensuring consistent JSON responses for errors.
"""
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException, BadRequest, Unauthorized, Forbidden, NotFound, InternalServerError

errors = Blueprint("errors", __name__)


@errors.app_errorhandler(400)
def handle_bad_request(e):
    """Handle 400 Bad Request errors for API endpoints."""
    if request.path.startswith("/api/"):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return jsonify({
            "error": "bad_request", 
            "detail": str(e) if hasattr(e, 'description') else "Invalid request",
            "request_id": request_id
        }), 400
    return e


@errors.app_errorhandler(401)
def handle_unauthorized(e):
    """Handle 401 Unauthorized errors for API endpoints."""
    if request.path.startswith("/api/"):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return jsonify({
            "error": "unauthorized", 
            "detail": "Login required",
            "request_id": request_id
        }), 401
    return e


@errors.app_errorhandler(403)
def handle_forbidden(e):
    """Handle 403 Forbidden errors for API endpoints."""
    if request.path.startswith("/api/"):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return jsonify({
            "error": "forbidden", 
            "detail": "Access denied",
            "request_id": request_id
        }), 403
    return e


@errors.app_errorhandler(404)
def handle_not_found(e):
    """Handle 404 Not Found errors for API endpoints."""
    if request.path.startswith("/api/"):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return jsonify({
            "error": "not_found", 
            "detail": "Resource not found",
            "request_id": request_id
        }), 404
    return e


@errors.app_errorhandler(500)
def handle_internal_server_error(e):
    """Handle 500 Internal Server Error for API endpoints."""
    if request.path.startswith("/api/"):
        request_id = request.environ.get('X-Request-ID', 'unknown')
        return jsonify({
            "error": "internal_server_error", 
            "detail": "Internal server error",
            "request_id": request_id
        }), 500
    return e


@errors.app_errorhandler(Exception)
def handle_exception(e):
    """Handle all other exceptions for API endpoints."""
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

    request_id = request.environ.get('X-Request-ID', 'unknown')
    return jsonify({"error": code, "detail": detail, "request_id": request_id}), status
