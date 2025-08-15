import time
import uuid
import logging
from flask import g, request, jsonify

log = logging.getLogger("mdraft.request")


def init_request_logging(app):
    """Initialize request logging middleware.
    
    Logs: method, path, status, duration, request_id
    Includes request_id in API error responses.
    """
    
    @app.before_request
    def _start():
        """Start timing and generate request ID."""
        g._t = time.time()
        g.request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        request.environ['X-Request-ID'] = g.request_id
    
    @app.after_request
    def _end(resp):
        """Log request completion with timing."""
        dt = int((time.time() - g._t) * 1000) if getattr(g, "_t", None) else -1
        request_id = getattr(g, "request_id", "-")
        
        # Add request_id to API error responses
        if resp.status_code >= 400 and request.path.startswith("/api/"):
            try:
                data = resp.get_json()
                if data and isinstance(data, dict):
                    data["request_id"] = request_id
                    resp.set_data(jsonify(data).get_data())
            except:
                pass  # Not JSON response
        
        log.info("rid=%s %s %s %s %sms", request_id, request.method, request.path, resp.status_code, dt)
        return resp
