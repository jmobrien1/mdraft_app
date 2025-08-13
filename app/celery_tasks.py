"""
Celery tasks for mdraft.

This module defines Celery tasks for document conversion with proper
routing based on user priority and comprehensive logging.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from . import db
from .models import User, Job
from .conversion import process_job
from .services import Storage

logger = logging.getLogger(__name__)


def is_pro_user(user_id: int) -> bool:
    """Check if user has pro subscription.
    
    Args:
        user_id: Database user ID
        
    Returns:
        True if user has pro subscription, False otherwise
    """
    try:
        user = db.session.get(User, user_id)
        if user:
            return user.subscription_status in ['active', 'pro'] or user.plan in ['Pro', 'pro']
        return False
    except Exception as e:
        logger.error(f"Error checking pro status for user {user_id}: {e}")
        return False


def get_task_queue(user_id: int) -> str:
    """Determine task queue based on user priority.
    
    Args:
        user_id: Database user ID
        
    Returns:
        Queue name: 'mdraft_priority' for pro users, 'mdraft_default' otherwise
    """
    return 'mdraft_priority' if is_pro_user(user_id) else 'mdraft_default'


def convert_document(job_id: int, user_id: int, gcs_uri: str) -> dict:
    """Convert document using Celery task.
    
    Args:
        job_id: Database job ID
        user_id: Database user ID
        gcs_uri: Storage path for the document
        
    Returns:
        Dictionary with conversion results
    """
    # Set task metadata for logging
    import uuid
    task_id = str(uuid.uuid4())
    conversion_id = f"conv_{job_id}_{task_id[:8]}"
    
    logger.info(f"Starting conversion task {conversion_id} for job {job_id}", extra={
        'task_id': task_id,
        'conversion_id': conversion_id,
        'job_id': job_id,
        'user_id': user_id,
        'queue': 'unknown'
    })
    
    try:
        # Update job status to processing
        job = db.session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.status = "processing"
        job.started_at = db.func.now()
        db.session.commit()
        
        # Process the document
        markdown_content = process_job(job_id, gcs_uri)
        
        # Store result using Storage adapter
        storage = Storage()
        output_path = f"outputs/{job_id}/result.md"
        storage.write_bytes(output_path, markdown_content.encode('utf-8'))
        
        # Update job with success
        job.output_uri = output_path
        job.completed_at = db.func.now()
        job.error_message = None
        job.status = "completed"
        db.session.commit()
        
        logger.info(f"Completed conversion task {conversion_id} for job {job_id}", extra={
            'task_id': task_id,
            'conversion_id': conversion_id,
            'job_id': job_id,
            'output_path': output_path,
            'bytes_out': len(markdown_content.encode('utf-8'))
        })
        
        return {
            'status': 'completed',
            'job_id': job_id,
            'output_uri': output_path,
            'conversion_id': conversion_id
        }
        
    except Exception as e:
        # Update job with failure
        job = db.session.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.session.commit()
        
        logger.error(f"Failed conversion task {conversion_id} for job {job_id}: {e}", extra={
            'task_id': task_id,
            'conversion_id': conversion_id,
            'job_id': job_id,
            'error': str(e)
        })
        
        # Re-raise to mark task as failed
        raise


def enqueue_conversion_task(job_id: int, user_id: int, gcs_uri: str) -> Optional[str]:
    """Enqueue conversion task based on queue mode.
    
    Args:
        job_id: Database job ID
        user_id: Database user ID
        gcs_uri: Storage path for the document
        
    Returns:
        Task ID if enqueued, None if run synchronously
    """
    queue_mode = os.getenv("QUEUE_MODE", "celery").lower()
    
    if queue_mode == "celery":
        # Import Celery app and create task
        from celery_worker import celery
        
        # Create task function with decorator
        @celery.task(bind=True)
        def celery_convert_document(self, job_id: int, user_id: int, gcs_uri: str) -> dict:
            return convert_document(job_id, user_id, gcs_uri)
        
        # Enqueue as Celery task
        task = celery_convert_document.delay(job_id, user_id, gcs_uri)
        logger.info(f"Enqueued Celery task {task.id} for job {job_id}")
        return task.id
    else:
        # Run synchronously (for local development)
        logger.info(f"Running conversion synchronously for job {job_id}")
        try:
            result = convert_document(job_id, user_id, gcs_uri)
            return f"sync_{job_id}"
        except Exception as e:
            logger.error(f"Sync conversion failed for job {job_id}: {e}")
            raise


def daily_cleanup_task() -> dict:
    """Daily cleanup task for Celery beat.
    
    This task runs the cleanup process and is scheduled to run daily.
    
    Returns:
        Dictionary with cleanup results
    """
    from .cleanup import run_cleanup
    
    logger.info("Starting daily cleanup task")
    try:
        result = run_cleanup()
        logger.info(f"Daily cleanup completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Daily cleanup failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
