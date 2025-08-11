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
    
    # Application configuration
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "worker-secret-key")
    
    # Database configuration
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mdraft_worker.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Google Cloud Storage configuration
    app.config["GCS_BUCKET_NAME"] = os.environ.get("GCS_BUCKET_NAME")
    app.config["GCS_PROCESSED_BUCKET_NAME"] = os.environ.get("GCS_PROCESSED_BUCKET_NAME")
    
    # Google Cloud Tasks configuration
    app.config["CLOUD_TASKS_QUEUE_NAME"] = os.environ.get("CLOUD_TASKS_QUEUE_NAME", "mdraft-conversion-queue")
    app.config["CLOUD_TASKS_LOCATION"] = os.environ.get("CLOUD_TASKS_LOCATION", "us-central1")
    
    # Document AI configuration
    app.config["DOCAI_PROCESSOR_ID"] = os.environ.get("DOCAI_PROCESSOR_ID")
    app.config["DOCAI_LOCATION"] = os.environ.get("DOCAI_LOCATION", "us")
    
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
