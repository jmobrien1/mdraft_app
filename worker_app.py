#!/usr/bin/env python3
"""
Worker application entrypoint for mdraft.

This module creates a Flask application specifically for the worker service
that processes document conversion tasks from Cloud Tasks. It only registers
the worker blueprint and includes worker-specific configuration.
"""
import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_worker_app() -> Flask:
    """Create and configure the Flask worker application."""
    app = Flask(__name__)
    
    # Set worker service flag
    os.environ["WORKER_SERVICE"] = "true"
    
    # Get centralized configuration
    from app.config import get_config
    config = get_config()
    
    # Apply non-sensitive configuration to Flask app
    app.config.update(config.to_dict())
    
    # Securely apply secrets to Flask app (prevents logging exposure)
    config.apply_secrets_to_app(app)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Set up structured logging
    if not app.debug:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
    
    # Register only the worker blueprint
    from app.worker_routes import worker_bp
    app.register_blueprint(worker_bp)
    
    # Initialize Cloud Tasks queue if needed
    from app.tasks import create_queue_if_not_exists
    with app.app_context():
        create_queue_if_not_exists()
    
    return app


# Create the application instance
app = create_worker_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
