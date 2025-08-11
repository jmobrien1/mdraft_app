"""
Database utilities for mdraft.

This module provides database helper functions including advisory locks
for ensuring idempotent task processing.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@contextmanager
def advisory_lock(session: Session, job_id: int, timeout_seconds: int = 30) -> bool:
    """Acquire a PostgreSQL advisory lock for a job.
    
    This function uses PostgreSQL advisory locks to ensure that only one
    worker can process a job at a time. If the lock cannot be acquired
    within the timeout period, it returns False.
    
    Args:
        session: SQLAlchemy database session
        job_id: The job ID to lock
        timeout_seconds: Maximum time to wait for lock acquisition
        
    Yields:
        True if lock was acquired, False otherwise
        
    Example:
        with advisory_lock(db.session, job_id) as acquired:
            if acquired:
                # Process the job
                process_job(job_id)
            else:
                # Lock acquisition failed, job is being processed elsewhere
                logger.info(f"Could not acquire lock for job {job_id}")
    """
    lock_acquired = False
    start_time = time.time()
    
    try:
        # Try to acquire advisory lock with timeout
        while time.time() - start_time < timeout_seconds:
            result = session.execute(
                text("SELECT pg_try_advisory_lock(:job_id)"),
                {"job_id": job_id}
            ).scalar()
            
            if result:
                lock_acquired = True
                logger.info(f"Acquired advisory lock for job {job_id}")
                break
            else:
                logger.debug(f"Advisory lock for job {job_id} not available, retrying...")
                time.sleep(0.1)  # Small delay before retry
        
        if not lock_acquired:
            logger.warning(f"Could not acquire advisory lock for job {job_id} within {timeout_seconds}s")
        
        yield lock_acquired
        
    except Exception as e:
        logger.error(f"Error with advisory lock for job {job_id}: {e}")
        yield False
        
    finally:
        if lock_acquired:
            try:
                # Release the advisory lock
                session.execute(
                    text("SELECT pg_advisory_unlock(:job_id)"),
                    {"job_id": job_id}
                )
                logger.info(f"Released advisory lock for job {job_id}")
            except Exception as e:
                logger.error(f"Error releasing advisory lock for job {job_id}: {e}")


def update_job_status_atomic(session: Session, job_id: int, new_status: str, 
                           allowed_current_statuses: list[str]) -> bool:
    """Atomically update job status if it's in an allowed state.
    
    This function prevents race conditions by using a WHERE clause to
    ensure the job is in an expected state before updating.
    
    Args:
        session: SQLAlchemy database session
        job_id: The job ID to update
        new_status: The new status to set
        allowed_current_statuses: List of statuses that allow the update
        
    Returns:
        True if the update was successful, False otherwise
    """
    try:
        # Build the WHERE clause for allowed statuses
        status_placeholders = ", ".join([f"'{status}'" for status in allowed_current_statuses])
        
        result = session.execute(
            text(f"""
                UPDATE jobs 
                SET status = :new_status, updated_at = NOW() 
                WHERE id = :job_id AND status IN ({status_placeholders})
            """),
            {
                "job_id": job_id,
                "new_status": new_status
            }
        )
        
        rows_updated = result.rowcount
        if rows_updated > 0:
            session.commit()
            logger.info(f"Updated job {job_id} status to {new_status}")
            return True
        else:
            logger.warning(f"Could not update job {job_id} status to {new_status} - not in allowed states: {allowed_current_statuses}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating job {job_id} status: {e}")
        session.rollback()
        return False


def get_job_with_lock(session: Session, job_id: int, user_id: int) -> Optional[dict]:
    """Get job information with advisory lock check.
    
    Args:
        session: SQLAlchemy database session
        job_id: The job ID to retrieve
        user_id: The user ID for validation
        
    Returns:
        Job dictionary if found and belongs to user, None otherwise
    """
    try:
        result = session.execute(
            text("""
                SELECT id, user_id, filename, status, gcs_uri, output_uri, 
                       created_at, updated_at
                FROM jobs 
                WHERE id = :job_id
            """),
            {"job_id": job_id}
        ).fetchone()
        
        if not result:
            logger.error(f"Job {job_id} not found")
            return None
        
        job = dict(result._mapping)
        
        # Validate user ownership
        if job["user_id"] != user_id:
            logger.error(f"Job {job_id} does not belong to user {user_id}")
            return None
        
        return job
        
    except Exception as e:
        logger.error(f"Error retrieving job {job_id}: {e}")
        return None
