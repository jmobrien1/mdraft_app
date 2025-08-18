"""
Google Cloud Storage integration for mdraft.

This module provides functions for uploading files to GCS, generating
signed URLs for downloads, and managing file lifecycle. It includes
fallback to local storage for development environments.
"""
from __future__ import annotations

import os
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class LocalStorage:
    def __init__(self, base="/tmp/uploads"):
        self.base = base
        os.makedirs(self.base, exist_ok=True)
    def save(self, file_storage, subdir="uploads"):
        d = os.path.join(self.base, subdir) if subdir else self.base
        os.makedirs(d, exist_ok=True)
        name = secure_filename(file_storage.filename or "upload.bin")
        path = os.path.join(d, name)
        file_storage.save(path)
        return {"backend": "local", "path": path, "name": name}

def init_storage(app):
    """Initialize storage backend with robust fallback to local storage.
    
    This function:
    1. Checks if STORAGE_BACKEND=gcs and GOOGLE_APPLICATION_CREDENTIALS exists
    2. If GCS credentials are available, initializes GCS client and bucket
    3. If GCS is not available or fails, falls back to LocalStorage
    4. Stores the backend info in app.extensions["storage"]
    5. Logs which backend was selected at startup
    """
    backend = (app.config.get("STORAGE_BACKEND") or os.getenv("STORAGE_BACKEND") or "local").lower()
    
    # Check for GCS configuration
    if backend == "gcs":
        # Check for GCS credentials
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/gcp.json")
        
        if not os.path.exists(cred_path):
            app.logger.warning(f"GCS credentials not found at {cred_path}; falling back to local storage")
            app.logger.info("To use GCS, set GOOGLE_APPLICATION_CREDENTIALS environment variable or mount credentials at /etc/secrets/gcp.json")
        else:
            # Check for GCS bucket configuration
            bucket_name = app.config.get("GCS_BUCKET") or os.getenv("GCS_BUCKET_NAME")
            if not bucket_name:
                app.logger.warning("GCS_BUCKET not configured; falling back to local storage")
                app.logger.info("To use GCS, set GCS_BUCKET environment variable")
            else:
                try:
                    # Check if google-cloud-storage is available
                    try:
                        from google.cloud import storage as _gcs
                    except ImportError:
                        app.logger.warning("google-cloud-storage package not installed; falling back to local storage")
                        app.logger.info("To use GCS, install with: pip install google-cloud-storage")
                        raise ImportError("google-cloud-storage not available")
                    
                    # Test credentials and bucket access
                    client = _gcs.Client.from_service_account_json(cred_path)
                    bucket = client.bucket(bucket_name)
                    
                    # Test the connection with a simple operation
                    try:
                        bucket.reload()
                        app.logger.info(f"GCS connection test successful for bucket: {bucket_name}")
                    except Exception as e:
                        app.logger.warning(f"GCS bucket access test failed: {e}")
                        raise
                    
                    app.extensions["storage"] = ("gcs", (client, bucket))
                    app.logger.info(f"Storage backend: GCS (bucket: {bucket_name})")
                    return
                    
                except Exception as e:
                    app.logger.exception(f"GCS initialization failed; falling back to local storage: {e}")
                    app.logger.info("Check GCS credentials, bucket permissions, and network connectivity")
    
    # Fallback to local storage
    local_base = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    app.extensions["storage"] = ("local", LocalStorage(base=local_base))
    app.logger.info(f"Storage backend: LOCAL (base: {local_base})")

# Legacy functions for backward compatibility
def upload_stream_to_gcs(file_stream, filename: str, content_type: str = None) -> str:
    """Legacy function for uploading file stream to GCS.
    
    This function is maintained for backward compatibility with existing code.
    It uses the new storage abstraction internally.
    """
    from flask import current_app
    
    # Get storage backend
    kind, handle = current_app.extensions.get("storage", ("local", None))
    
    if kind == "gcs":
        # Use GCS storage
        client, bucket = handle
        blob_name = secure_filename(filename)
        blob = bucket.blob(f"uploads/{blob_name}")
        blob.upload_from_file(file_stream, rewind=True)
        return f"gs://{bucket.name}/{blob.name}"
    else:
        # Use local storage
        source_ref = handle.save(file_stream)
        return source_ref["path"]

def generate_download_url(local_path: str, expires_in: int = 900) -> str:
    """Generate a temporary download URL for a file stored locally.
    
    This is a legacy function maintained for backward compatibility.
    """
    import time
    expiry = int(time.time()) + expires_in
    filename = os.path.basename(local_path)
    return f"/download/{filename}?expires={expiry}"

def generate_signed_url(gcs_uri: str, expires_in: int = 900) -> str:
    """Generate a signed URL for GCS file download.
    
    This is a legacy function maintained for backward compatibility.
    """
    from flask import current_app
    
    # Get storage backend
    kind, handle = current_app.extensions.get("storage", ("local", None))
    
    if kind == "gcs" and gcs_uri.startswith("gs://"):
        # Use GCS signed URL
        client, bucket = handle
        bucket_name = gcs_uri.split("/")[2]
        blob_name = "/".join(gcs_uri.split("/")[3:])
        
        if bucket.name == bucket_name:
            blob = bucket.blob(blob_name)
            return blob.generate_signed_url(expiration=expires_in)
        else:
            # Different bucket, create new client
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.generate_signed_url(expiration=expires_in)
    else:
        # Fallback to local URL
        return generate_download_url(gcs_uri, expires_in)

def generate_v4_signed_url(gcs_uri: str, expires_in: int = 900) -> str:
    """Generate a v4 signed URL for GCS file download.
    
    This is a legacy function maintained for backward compatibility.
    """
    from flask import current_app
    
    # Get storage backend
    kind, handle = current_app.extensions.get("storage", ("local", None))
    
    if kind == "gcs" and gcs_uri.startswith("gs://"):
        # Use GCS v4 signed URL
        client, bucket = handle
        bucket_name = gcs_uri.split("/")[2]
        blob_name = "/".join(gcs_uri.split("/")[3:])
        
        if bucket.name == bucket_name:
            blob = bucket.blob(blob_name)
            return blob.generate_signed_url(expiration=expires_in, version="v4")
        else:
            # Different bucket, create new client
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.generate_signed_url(expiration=expires_in, version="v4")
    else:
        # Fallback to local URL
        return generate_download_url(gcs_uri, expires_in)
