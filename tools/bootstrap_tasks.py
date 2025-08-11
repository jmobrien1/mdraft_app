#!/usr/bin/env python3
"""
Cloud Tasks bootstrap script for mdraft.

This script ensures that the required Cloud Tasks queue exists with
proper configuration for document conversion tasks.
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from google.cloud import tasks_v2
from google.api_core import exceptions

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def ensure_queue() -> bool:
    """Ensure the Cloud Tasks queue exists with proper configuration.
    
    Creates the queue if it doesn't exist, or verifies the configuration
    if it already exists.
    
    Returns:
        True if queue is ready, False otherwise
    """
    try:
        # Get configuration from environment
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        queue_name = os.getenv("CLOUD_TASKS_QUEUE_NAME", "mdraft-conversion-queue")
        location = os.getenv("CLOUD_TASKS_LOCATION", "us-central1")
        
        if not project_id:
            logger.error("GOOGLE_CLOUD_PROJECT environment variable is required")
            return False
        
        logger.info(f"Ensuring queue '{queue_name}' exists in project '{project_id}' at location '{location}'")
        
        # Create Cloud Tasks client
        client = tasks_v2.CloudTasksClient()
        queue_path = client.queue_path(project_id, location, queue_name)
        location_path = f"projects/{project_id}/locations/{location}"
        
        try:
            # Try to get the existing queue
            existing_queue = client.get_queue(name=queue_path)
            logger.info(f"Queue '{queue_name}' already exists")
            
            # Verify retry configuration
            retry_config = existing_queue.retry_config
            if retry_config:
                logger.info(f"Queue retry config: max_attempts={retry_config.max_attempts}, "
                          f"min_backoff={retry_config.min_backoff}, "
                          f"max_backoff={retry_config.max_backoff}")
            else:
                logger.warning("Queue exists but has no retry configuration")
            
            return True
            
        except exceptions.NotFound:
            # Queue doesn't exist, create it
            logger.info(f"Queue '{queue_name}' not found, creating...")
            
            # Define queue configuration
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
            
            # Create the queue
            created_queue = client.create_queue(
                request={
                    "parent": location_path,
                    "queue": queue,
                }
            )
            
            logger.info(f"Successfully created queue '{queue_name}'")
            logger.info(f"Queue retry config: max_attempts=5, min_backoff=20s, max_backoff=600s")
            return True
            
    except exceptions.PermissionDenied:
        logger.error("Permission denied. Ensure the service account has 'Cloud Tasks Admin' role")
        return False
    except exceptions.InvalidArgument as e:
        logger.error(f"Invalid argument: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to ensure queue: {e}")
        return False


def main():
    """Main function to bootstrap Cloud Tasks queue."""
    print("🚀 Bootstrapping Cloud Tasks queue for mdraft...")
    
    # Check required environment variables
    required_vars = ["GOOGLE_CLOUD_PROJECT"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nRequired environment variables:")
        print("  GOOGLE_CLOUD_PROJECT - Your Google Cloud project ID")
        print("  CLOUD_TASKS_LOCATION - Cloud Tasks location (default: us-central1)")
        print("  CLOUD_TASKS_QUEUE_NAME - Queue name (default: mdraft-conversion-queue)")
        print("\nExample usage:")
        print("  GOOGLE_CLOUD_PROJECT=my-project python tools/bootstrap_tasks.py")
        return 1
    
    # Ensure queue exists
    if ensure_queue():
        print("✅ Queue bootstrap completed successfully")
        return 0
    else:
        print("❌ Queue bootstrap failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
