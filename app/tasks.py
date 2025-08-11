"""
Cloud Tasks integration for mdraft.

This module handles enqueueing background tasks for document conversion
using Google Cloud Tasks. Tasks are sent to a worker service that
processes documents asynchronously.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

logger = logging.getLogger(__name__)


def add_conversion_task(job_id: int, user_id: int, gcs_uri: str) -> Optional[str]:
    """Enqueue a document conversion task to Cloud Tasks.
    
    This function creates a task in the Cloud Tasks queue that will be
    processed by the worker service. The task includes the job ID, user ID,
    and GCS URI of the uploaded document.
    
    Args:
        job_id: The database ID of the conversion job
        user_id: The database ID of the user who uploaded the document
        gcs_uri: The GCS URI of the uploaded document
        
    Returns:
        The task name if successful, None if failed
        
    Raises:
        Exception: If task creation fails
    """
    try:
        # Get configuration from environment
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        queue_name = os.getenv("CLOUD_TASKS_QUEUE_NAME", "mdraft-conversion-queue")
        location = os.getenv("CLOUD_TASKS_LOCATION", "us-central1")
        worker_service_url = os.getenv("WORKER_SERVICE_URL")
        worker_invoker_sa_email = os.getenv("WORKER_INVOKER_SA_EMAIL")
        
        if not all([project_id, worker_service_url, worker_invoker_sa_email]):
            logger.error("Missing required environment variables for Cloud Tasks")
            return None
        
        # Create Cloud Tasks client
        client = tasks_v2.CloudTasksClient()
        
        # Construct the queue path
        queue_path = client.queue_path(project_id, location, queue_name)
        
        # Construct the task
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{worker_service_url}/tasks/process-document",
                "headers": {
                    "Content-Type": "application/json",
                },
                "oidc_token": {
                    "service_account_email": worker_invoker_sa_email,
                    "audience": worker_service_url,
                },
                "body": json.dumps({
                    "job_id": job_id,
                    "user_id": user_id,
                    "gcs_uri": gcs_uri,
                }).encode(),
            }
        }
        
        # Add retry configuration
        task["dispatch_deadline"] = {
            "seconds": 600,  # 10 minute deadline
        }
        
        # Create the task
        response = client.create_task(request={"parent": queue_path, "task": task})
        
        logger.info(f"Created Cloud Task: {response.name} for job {job_id}")
        return response.name
        
    except Exception as e:
        logger.error(f"Failed to create Cloud Task for job {job_id}: {e}")
        raise


def create_queue_if_not_exists() -> None:
    """Create the Cloud Tasks queue if it doesn't exist.
    
    This function ensures the required queue exists before the application
    starts processing requests. It should be called during application
    initialization.
    """
    try:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        queue_name = os.getenv("CLOUD_TASKS_QUEUE_NAME", "mdraft-conversion-queue")
        location = os.getenv("CLOUD_TASKS_LOCATION", "us-central1")
        
        if not project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT not set, skipping queue creation")
            return
        
        client = tasks_v2.CloudTasksClient()
        queue_path = client.queue_path(project_id, location, queue_name)
        
        try:
            # Try to get the queue
            client.get_queue(name=queue_path)
            logger.info(f"Queue {queue_name} already exists")
        except Exception:
            # Queue doesn't exist, create it
            queue = {
                "name": queue_path,
                "rate_limits": {
                    "max_concurrent_dispatches": 100,
                    "max_dispatches_per_second": 500,
                },
                "retry_config": {
                    "max_attempts": 5,
                    "min_backoff": {
                        "seconds": 20,
                    },
                    "max_backoff": {
                        "seconds": 600,
                    },
                    "max_doublings": 3,
                },
            }
            
            client.create_queue(
                request={
                    "parent": client.location_path(project_id, location),
                    "queue": queue,
                }
            )
            logger.info(f"Created queue {queue_name}")
            
    except Exception as e:
        logger.error(f"Failed to create queue: {e}")
        # Don't raise - queue creation is not critical for app startup