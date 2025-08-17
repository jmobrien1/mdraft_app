#!/usr/bin/env python3
"""
Production Flask server for Render deployment.
Handles PORT environment variable correctly for Render's port scanner.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file (for local development)
load_dotenv()

def main():
    """Start the Flask application for production deployment."""
    try:
        from app import create_app
        
        # Create Flask app
        app = create_app()
        
        # Get port from environment (Render sets this)
        port = int(os.environ.get("PORT", 10000))
        
        # Log startup information
        logger.info("=" * 60)
        logger.info("🚀 Starting mdraft Flask application")
        logger.info(f"📡 Binding to port: {port}")
        logger.info(f"🌐 Host: 0.0.0.0")
        logger.info(f"🔧 Environment: {os.environ.get('FLASK_ENV', 'production')}")
        logger.info("=" * 60)
        
        # Start Flask server with production settings
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,           # Disable debug mode for production
            threaded=True,         # Enable threading for concurrent requests
            use_reloader=False,    # Disable reloader for production
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start Flask application: {e}")
        sys.exit(1)

# Export app object for WSGI servers (keep compatibility)
app = None
try:
    from app import create_app
    app = create_app()
except Exception as e:
    logger.error(f"❌ Failed to create Flask app: {e}")

if __name__ == "__main__":
    main()