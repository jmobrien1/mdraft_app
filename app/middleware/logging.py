import time
import uuid
import logging
from flask import g, request

log = logging.getLogger("mdraft.request")


def init_request_logging(app):
    """Initialize request logging middleware.
    
    This adds before_request and after_request handlers that log:
    - Request ID for tracing
    - Method, path, status code
    - Response time in milliseconds
    """
    
    @app.before_request
    def _start():
        """Start timing and generate request ID."""
        g._t = time.time()
        g.request_id = uuid.uuid4().hex
    
    @app.after_request
    def _end(resp):
        """Log request completion with timing."""
        dt = int((time.time() - g._t) * 1000) if getattr(g, "_t", None) else -1
        log.info(
            "rid=%s %s %s %s %sms", 
            getattr(g, "request_id", "-"), 
            request.method, 
            request.path, 
            resp.status_code, 
            dt
        )
        return resp
