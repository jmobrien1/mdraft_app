import traceback
from app import create_app

try:
    print("--- WSGI: Attempting to create Flask app ---")
    app = create_app()
    print("--- WSGI: Flask app created successfully ---")
except Exception:
    print("❌❌❌ FATAL: Exception occurred during app creation in wsgi.py ❌❌❌")
    traceback.print_exc()
    # Exit with a non-zero code to make sure the server doesn't start
    import sys
    sys.exit(1)

# A wrapper to catch exceptions during the request
class ExceptionTrapMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except Exception:
            print("❌❌❌ FATAL: Exception occurred during a request in wsgi.py ❌❌❌")
            traceback.print_exc()
            # Try to return a 500 error response
            start_response('500 INTERNAL SERVER ERROR', [('Content-Type', 'text/plain')])
            return [b'A server error occurred.']

# Wrap the app with the middleware
app.wsgi_app = ExceptionTrapMiddleware(app.wsgi_app)

print("--- WSGI: Application is wrapped and ready ---")
