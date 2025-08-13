"""
Cleanup tasks for mdraft.

This module provides cleanup functionality for removing old files
based on retention policies. It includes both Celery beat tasks
and CLI commands for manual execution.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from . import db
from .models import Job
from .services import Storage

logger = logging.getLogger(__name__)


def get_retention_days() -> int:
    """Get retention days from environment variable.
    
    Returns:
        Number of days to retain files (default: 30)
    """
    retention_str = os.getenv("RETENTION_DAYS", "30")
    return int(retention_str) if retention_str else 30


def should_delete_gcs() -> bool:
    """Check if GCS deletion is enabled.
    
    Returns:
        True if CLEANUP_DELETE_GCS=1, False otherwise
    """
    return os.getenv("CLEANUP_DELETE_GCS", "0") == "1"


def should_use_gcs() -> bool:
    """Check if GCS is enabled.
    
    Returns:
        True if USE_GCS=1, False otherwise
    """
    return os.getenv("USE_GCS", "0") == "1"


def cleanup_old_files() -> dict:
    """Clean up old files based on retention policy.
    
    This function is idempotent and safe to run multiple times.
    It will skip cleanup if GCS is not enabled or if deletion is disabled.
    
    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting cleanup of old files")
    
    # Check if cleanup should be performed
    if not should_use_gcs():
        logger.info("Skipping cleanup: USE_GCS=0")
        return {
            "status": "skipped",
            "reason": "USE_GCS=0",
            "files_deleted": 0,
            "errors": []
        }
    
    if not should_delete_gcs():
        logger.info("Skipping cleanup: CLEANUP_DELETE_GCS=0")
        return {
            "status": "skipped", 
            "reason": "CLEANUP_DELETE_GCS=0",
            "files_deleted": 0,
            "errors": []
        }
    
    retention_days = get_retention_days()
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    logger.info(f"Cleaning up files older than {cutoff_date} (retention: {retention_days} days)")
    
    storage = Storage()
    files_deleted = 0
    errors = []
    
    try:
        # Clean up outputs directory
        output_files = storage.list_prefix("outputs/")
        logger.info(f"Found {len(output_files)} files in outputs/")
        
        for file_path in output_files:
            try:
                # Extract job ID from path: outputs/<job_id>/result.md
                path_parts = file_path.split('/')
                if len(path_parts) >= 2:
                    job_id_str = path_parts[1]
                    try:
                        job_id = int(job_id_str)
                        
                        # Check job completion date
                        job = db.session.get(Job, job_id)
                        if job and job.completed_at:
                            if job.completed_at < cutoff_date:
                                # Delete the file
                                if storage.delete(file_path):
                                    files_deleted += 1
                                    logger.info(f"Deleted old file: {file_path} (job {job_id}, completed {job.completed_at})")
                                else:
                                    errors.append(f"Failed to delete file: {file_path}")
                            else:
                                logger.debug(f"Keeping file: {file_path} (job {job_id}, completed {job.completed_at})")
                        else:
                            logger.warning(f"Job {job_id} not found or has no completion date: {file_path}")
                            
                    except ValueError:
                        logger.warning(f"Invalid job ID in path: {file_path}")
                else:
                    logger.warning(f"Invalid file path format: {file_path}")
                    
            except Exception as e:
                error_msg = f"Error processing file {file_path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Clean up uploads directory (optional - more aggressive cleanup)
        upload_files = storage.list_prefix("uploads/")
        logger.info(f"Found {len(upload_files)} files in uploads/")
        
        for file_path in upload_files:
            try:
                # Extract job ID from path: uploads/<job_id>/<filename>
                path_parts = file_path.split('/')
                if len(path_parts) >= 2:
                    job_id_str = path_parts[1]
                    try:
                        job_id = int(job_id_str)
                        
                        # Check job creation date
                        job = db.session.get(Job, job_id)
                        if job and job.created_at:
                            if job.created_at < cutoff_date:
                                # Delete the file
                                if storage.delete(file_path):
                                    files_deleted += 1
                                    logger.info(f"Deleted old upload: {file_path} (job {job_id}, created {job.created_at})")
                                else:
                                    errors.append(f"Failed to delete upload: {file_path}")
                            else:
                                logger.debug(f"Keeping upload: {file_path} (job {job_id}, created {job.created_at})")
                        else:
                            logger.warning(f"Job {job_id} not found: {file_path}")
                            
                    except ValueError:
                        logger.warning(f"Invalid job ID in path: {file_path}")
                else:
                    logger.warning(f"Invalid file path format: {file_path}")
                    
            except Exception as e:
                error_msg = f"Error processing upload {file_path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        logger.info(f"Cleanup completed: {files_deleted} files deleted, {len(errors)} errors")
        
        return {
            "status": "completed",
            "files_deleted": files_deleted,
            "errors": errors,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        error_msg = f"Cleanup failed: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "error": error_msg,
            "files_deleted": files_deleted,
            "errors": errors
        }


def cleanup_old_jobs() -> dict:
    """Clean up old job records from database.
    
    This function removes job records older than retention period
    that are in terminal states (completed, failed).
    
    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting cleanup of old job records")
    
    retention_days = get_retention_days()
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    try:
        # Delete old completed/failed jobs
        old_jobs = db.session.query(Job).filter(
            Job.status.in_(['completed', 'failed']),
            Job.created_at < cutoff_date
        ).all()
        
        job_count = len(old_jobs)
        if job_count > 0:
            for job in old_jobs:
                db.session.delete(job)
            db.session.commit()
            logger.info(f"Deleted {job_count} old job records")
        else:
            logger.info("No old job records to delete")
            db.session.commit()  # Commit even when no jobs to delete
        
        return {
            "status": "completed",
            "jobs_deleted": job_count,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Job cleanup failed: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "error": error_msg
        }


def run_cleanup() -> dict:
    """Run complete cleanup process.
    
    This function runs both file cleanup and job record cleanup.
    
    Returns:
        Dictionary with combined cleanup results
    """
    logger.info("Starting complete cleanup process")
    
    file_results = cleanup_old_files()
    job_results = cleanup_old_jobs()
    
    return {
        "file_cleanup": file_results,
        "job_cleanup": job_results,
        "timestamp": datetime.utcnow().isoformat()
    }
