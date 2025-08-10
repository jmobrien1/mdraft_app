"""
Google Cloud Storage integration for mdraft.

This module provides functions for uploading files to GCS, generating
signed URLs for downloads, and managing file lifecycle. It includes
fallback to local storage for development environments.
"""
from __future__ import annotations

import os
import logging
from typing import Optional
from datetime import datetime, timedelta

from flask import current_app


def upload_to_gcs(file_path: str, bucket_name: str, blob_name: str) -> Optional[str]:
    """Upload a file to Google Cloud Storage.
    
    Args:
        file_path: Local path to the file to upload.
        bucket_name: Name of the GCS bucket.
        blob_name: Name to give the file in GCS.
        
    Returns:
        GCS URI of the uploaded file, or None if upload failed.
    """
    logger = logging.getLogger(__name__)
    
    try:
        from google.cloud import storage
        
        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Upload the file
        blob.upload_from_filename(file_path)
        
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"File uploaded to GCS: {gcs_uri}")
        
        return gcs_uri
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available, using local path")
        return file_path
    except Exception as e:
        logger.error(f"Failed to upload to GCS: {e}")
        return None


def generate_signed_url(gcs_uri: str, expires_in: int = 900) -> Optional[str]:
    """Generate a signed URL for downloading a file from GCS.
    
    Args:
        gcs_uri: GCS URI of the file (gs://bucket/name).
        expires_in: Time-to-live in seconds for the URL (default 15 minutes).
        
    Returns:
        Signed URL for downloading the file, or None if generation failed.
    """
    logger = logging.getLogger(__name__)
    
    if not gcs_uri.startswith("gs://"):
        # Local file, return local download URL
        filename = os.path.basename(gcs_uri)
        return f"/download/{filename}"
    
    try:
        from google.cloud import storage
        
        # Parse GCS URI
        bucket_name = gcs_uri.split("/")[2]
        blob_name = "/".join(gcs_uri.split("/")[3:])
        
        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Generate signed URL
        expiration = datetime.utcnow() + timedelta(seconds=expires_in)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET"
        )
        
        logger.info(f"Generated signed URL for {gcs_uri}")
        return signed_url
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available")
        return None
    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        return None


def delete_from_gcs(gcs_uri: str) -> bool:
    """Delete a file from Google Cloud Storage.
    
    Args:
        gcs_uri: GCS URI of the file to delete.
        
    Returns:
        True if deletion was successful, False otherwise.
    """
    logger = logging.getLogger(__name__)
    
    if not gcs_uri.startswith("gs://"):
        # Local file, try to delete it
        try:
            os.remove(gcs_uri)
            logger.info(f"Deleted local file: {gcs_uri}")
            return True
        except OSError as e:
            logger.error(f"Failed to delete local file: {e}")
            return False
    
    try:
        from google.cloud import storage
        
        # Parse GCS URI
        bucket_name = gcs_uri.split("/")[2]
        blob_name = "/".join(gcs_uri.split("/")[3:])
        
        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Delete the blob
        blob.delete()
        
        logger.info(f"Deleted file from GCS: {gcs_uri}")
        return True
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available")
        return False
    except Exception as e:
        logger.error(f"Failed to delete from GCS: {e}")
        return False


def get_file_size(gcs_uri: str) -> Optional[int]:
    """Get the size of a file in bytes.
    
    Args:
        gcs_uri: GCS URI or local path of the file.
        
    Returns:
        File size in bytes, or None if unable to determine.
    """
    logger = logging.getLogger(__name__)
    
    if not gcs_uri.startswith("gs://"):
        # Local file
        try:
            return os.path.getsize(gcs_uri)
        except OSError as e:
            logger.error(f"Failed to get local file size: {e}")
            return None
    
    try:
        from google.cloud import storage
        
        # Parse GCS URI
        bucket_name = gcs_uri.split("/")[2]
        blob_name = "/".join(gcs_uri.split("/")[3:])
        
        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Get blob properties
        blob.reload()
        return blob.size
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available")
        return None
    except Exception as e:
        logger.error(f"Failed to get GCS file size: {e}")
        return None
