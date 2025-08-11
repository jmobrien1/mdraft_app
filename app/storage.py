"""
Google Cloud Storage integration for mdraft.

This module provides functions for uploading files to GCS, generating
signed URLs for downloads, and managing file lifecycle. It includes
fallback to local storage for development environments.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

from flask import current_app


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    """Parse a GCS URI into bucket and blob components.
    
    Args:
        uri: GCS URI in the format gs://bucket/blob
        
    Returns:
        Tuple of (bucket_name, blob_name)
        
    Raises:
        ValueError: If the URI is not a valid GCS URI
    """
    if not uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI format: {uri}")
    
    # Remove gs:// prefix
    path = uri[5:]
    
    # Split into bucket and blob
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid GCS URI format: {uri}")
    
    bucket_name, blob_name = parts
    return bucket_name, blob_name


def download_from_gcs(bucket_name: str, blob_name: str, local_filename: str) -> str:
    """Download a file from Google Cloud Storage to local storage.
    
    Args:
        bucket_name: Name of the GCS bucket.
        blob_name: Name of the file in GCS.
        local_filename: Name to give the local file.
        
    Returns:
        Local path to the downloaded file.
    """
    logger = logging.getLogger(__name__)
    
    try:
        from google.cloud import storage
        import tempfile
        
        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, local_filename)
        
        # Download the file
        blob.download_to_filename(local_path)
        
        logger.info(f"Downloaded gs://{bucket_name}/{blob_name} to {local_path}")
        return local_path
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available")
        raise ImportError("Google Cloud Storage client not available")
    except Exception as e:
        logger.error(f"Failed to download from GCS: {e}")
        raise


def upload_stream_to_gcs(file_stream, bucket_name: str, blob_name: str) -> Optional[str]:
    """Upload a file stream directly to Google Cloud Storage.
    
    Args:
        file_stream: File-like object to upload (e.g., from request.files['file'])
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
        
        # Upload the file stream directly
        blob.upload_from_file(file_stream)
        
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"File stream uploaded to GCS: {gcs_uri}")
        
        return gcs_uri
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available, using local path")
        return None
    except Exception as e:
        logger.error(f"Failed to upload stream to GCS: {e}")
        return None


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


def upload_text_to_gcs(bucket_name: str, blob_name: str, text: str, content_type: str = "text/markdown") -> str:
    """Upload text content to Google Cloud Storage.
    
    Args:
        bucket_name: Name of the GCS bucket.
        blob_name: Name to give the file in GCS.
        text: Text content to upload.
        content_type: MIME type for the content (default: text/markdown).
        
    Returns:
        GCS URI of the uploaded file.
    """
    logger = logging.getLogger(__name__)
    
    try:
        from google.cloud import storage
        
        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Set content type
        blob.content_type = content_type
        
        # Upload the text content
        blob.upload_from_string(text, content_type=content_type)
        
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"Text uploaded to GCS: {gcs_uri} ({len(text)} characters)")
        
        return gcs_uri
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available")
        raise ImportError("Google Cloud Storage client not available")
    except Exception as e:
        logger.error(f"Failed to upload text to GCS: {e}")
        raise


def generate_v4_signed_url(bucket: str, blob: str, method: str = "GET", minutes: int = 15, 
                          response_content_disposition: Optional[str] = None,
                          response_content_type: Optional[str] = None) -> Optional[str]:
    """Generate a V4 signed URL for a GCS object.
    
    Args:
        bucket: Name of the GCS bucket.
        blob: Name of the blob in GCS.
        method: HTTP method for the signed URL (default: GET).
        minutes: Time-to-live in minutes for the URL (default: 15 minutes).
        response_content_disposition: Content-Disposition header for the response (e.g., "attachment; filename=file.md").
        response_content_type: Content-Type header for the response (e.g., "text/markdown").
        
    Returns:
        V4 signed URL for the GCS object, or None if generation failed.
    """
    logger = logging.getLogger(__name__)
    
    try:
        from google.cloud import storage
        
        # Initialize GCS client
        client = storage.Client()
        bucket_obj = client.bucket(bucket)
        blob_obj = bucket_obj.blob(blob)
        
        # Generate V4 signed URL
        expiration = datetime.utcnow() + timedelta(minutes=minutes)
        
        # Build query parameters for response headers
        query_parameters = {}
        if response_content_disposition:
            query_parameters['response-content-disposition'] = response_content_disposition
        if response_content_type:
            query_parameters['response-content-type'] = response_content_type
        
        signed_url = blob_obj.generate_signed_url(
            version="v4",
            expiration=expiration,
            method=method,
            query_parameters=query_parameters
        )
        
        logger.info(f"Generated V4 signed URL for gs://{bucket}/{blob} (method: {method}, expires: {minutes}m)")
        return signed_url
        
    except ImportError:
        logger.warning("Google Cloud Storage client not available")
        return None
    except Exception as e:
        logger.error(f"Failed to generate V4 signed URL for gs://{bucket}/{blob}: {e}")
        return None


def generate_download_url(bucket_name: str, blob_name: str, expires_minutes: int = 15) -> Optional[str]:
    """Generate a V4 signed URL for downloading a file from GCS.
    
    Args:
        bucket_name: Name of the GCS bucket.
        blob_name: Name of the file in GCS.
        expires_minutes: Time-to-live in minutes for the URL (default 15 minutes).
        
    Returns:
        V4 signed URL for downloading the file, or None if generation failed.
    """
    return generate_v4_signed_url(bucket_name, blob_name, "GET", expires_minutes)


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
