"""
Celery worker for mdraft document conversion tasks.

This module provides the Celery worker configuration and task definitions
for processing document conversion jobs asynchronously.
"""
from __future__ import annotations

import os
import logging
import signal
import sys
from typing import Any, Optional, Dict

from celery import Celery
from celery.signals import worker_shutdown, worker_ready, worker_init
from flask import Flask

# Configure logging before importing app modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)

def create_celery_app() -> Celery:
    """Create and configure the Celery application."""
    
    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Create Celery app
    celery_app = Celery(
        "mdraft_worker",
        broker=redis_url,
        backend=redis_url,
        include=["app.celery_tasks"]
    )
    
    # Configure Celery
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=False,
        worker_send_task_events=True,
        task_send_sent_event=True,
        result_expires=3600,  # 1 hour
        result_persistent=True,
        visibility_timeout=3600,  # 1 hour
    )
    
    return celery_app

# Create Celery app
celery_app = create_celery_app()

# Export celery for backward compatibility
celery = celery_app

# Signal handlers for graceful shutdown
@worker_init.connect
def worker_init_handler(sender: Any, **kwargs: Any) -> None:
    """Handle worker initialization."""
    logger.info("Worker initializing...")
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name} ({signum}), initiating graceful shutdown...")
        
        # Stop accepting new tasks
        sender.control.purge()
        logger.info("Purged pending tasks")
        
        # Shutdown gracefully
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Worker initialized successfully")

@worker_ready.connect
def worker_ready_handler(sender: Any, **kwargs: Any) -> None:
    """Handle worker ready state."""
    logger.info("Worker is ready to process tasks")

@worker_shutdown.connect
def worker_shutdown_handler(sender: Any, **kwargs: Any) -> None:
    """Handle worker shutdown gracefully."""
    logger.info("Worker shutting down gracefully...")
    
    # Clean up any remaining tasks
    try:
        sender.control.purge()
        logger.info("Purged remaining tasks during shutdown")
    except Exception as e:
        logger.warning(f"Error purging tasks during shutdown: {e}")
    
    logger.info("Worker shutdown complete")

# Task definitions
@celery_app.task(bind=True, name="app.celery_tasks.process_conversion")
def process_conversion_task(self, conversion_id: int, user_id: Optional[int], 
                          gcs_uri: str, callback_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Process a document conversion task.
    
    This task downloads the file from storage, converts it to Markdown,
    and updates the conversion record with the results.
    
    Args:
        conversion_id: ID of the conversion record
        user_id: ID of the user who uploaded the file
        gcs_uri: GCS URI of the uploaded file
        callback_url: Optional webhook URL to notify when complete
        
    Returns:
        Dictionary with task results
    """
    from app import create_app
    from app.models import Conversion
    from app.conversion import process_job
    from app.webhooks import deliver_webhook
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            logger.info(f"Starting conversion task {self.request.id} for conversion {conversion_id}")
            
            # Update task status
            self.update_state(
                state="PROGRESS",
                meta={"status": "processing", "conversion_id": conversion_id}
            )
            
            # Process the conversion
            markdown_content = process_job(conversion_id, gcs_uri)
            
            # Get updated conversion record
            conversion = Conversion.query.get(conversion_id)
            if not conversion:
                raise ValueError(f"Conversion {conversion_id} not found")
            
            # Prepare result
            result = {
                "status": "completed",
                "conversion_id": conversion_id,
                "task_id": self.request.id,
                "markdown_length": len(markdown_content) if markdown_content else 0
            }
            
            # Send webhook if configured
            if callback_url and conversion.status == "completed":
                try:
                    webhook_data = {
                        "conversion_id": conversion_id,
                        "status": conversion.status,
                        "filename": conversion.filename,
                        "task_id": self.request.id
                    }
                    deliver_webhook(callback_url, webhook_data)
                    logger.info(f"Webhook delivered to {callback_url}")
                except Exception as e:
                    logger.warning(f"Failed to deliver webhook: {e}")
            
            logger.info(f"Conversion task {self.request.id} completed successfully")
            return result
            
        except Exception as e:
            logger.exception(f"Conversion task {self.request.id} failed: {e}")
            
            # Update conversion status to failed
            try:
                conversion = Conversion.query.get(conversion_id)
                if conversion:
                    conversion.status = "failed"
                    conversion.error = str(e)
                    from app import db
                    db.session.commit()
                    logger.info(f"Updated conversion {conversion_id} status to failed")
            except Exception as db_error:
                logger.error(f"Failed to update conversion status: {db_error}")
            
            # Re-raise the exception
            raise

# Health check task
@celery_app.task(name="app.celery_tasks.health_check")
def health_check_task() -> Dict[str, Any]:
    """Simple health check task for monitoring."""
    return {"status": "healthy", "worker": "mdraft_worker"}

if __name__ == "__main__":
    # Start the worker
    logger.info("Starting mdraft Celery worker...")
    celery_app.start()
