#!/usr/bin/env python3
"""
WSGI entry point for mdraft application.
This file MUST exist and MUST work for Render deployment.
"""
import os
import sys
import logging

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up basic logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)
logger.info("=== WSGI STARTUP INITIATED ===")

try:
    # Load environment variables first
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Environment variables loaded from .env")
    except ImportError:
        logger.info("python-dotenv not available, using system environment")
    
    # Import and create the Flask application
    logger.info("Importing Flask application factory...")
    from app import create_app
    
    logger.info("Creating Flask application...")
    app = create_app()
    
    logger.info("Flask application created successfully")
    logger.info(f"App config - Debug: {app.debug}, Testing: {app.testing}")
    
    # Test that the app can handle a basic request
    with app.test_client() as client:
        logger.info("Testing basic application functionality...")
        # This will fail if there are fundamental issues
        response = client.get('/health/simple')
        logger.info(f"Health check status: {response.status_code}")
    
    logger.info("=== WSGI APPLICATION READY ===")

except Exception as e:
    logger.error(f"=== WSGI STARTUP FAILED ===")
    logger.error(f"Error: {type(e).__name__}: {e}")
    logger.error("Full traceback:", exc_info=True)
    
    # Create a minimal error app so we can at least see what's wrong
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/')
    def error_info():
        return jsonify({
            "error": "Application startup failed",
            "exception": str(e),
            "type": type(e).__name__
        }), 500
    
    @app.route('/health')
    def health():
        return jsonify({"status": "startup_failed", "error": str(e)}), 503
        
    logger.info("Created minimal error reporting app")

# Export for WSGI server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
