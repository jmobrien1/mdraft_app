"""
Unified storage adapter for mdraft application.

This module provides a storage abstraction that can work with both Google Cloud Storage
and local file system storage. It automatically falls back to local storage when GCS
credentials are not available, ensuring the application remains functional.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, BinaryIO
from werkzeug.utils import secure_filename
from flask import current_app

logger = logging.getLogger(__name__)


class LocalStorage:
    """Local file system storage implementation."""
    
    def __init__(self, base_path: str = "/tmp/uploads"):
        """Initialize local storage with the specified base path."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage initialized at {self.base_path.absolute()}")
    
    def save(self, file_storage, subdir: str = "") -> Dict[str, Any]:
        """Save a file to local storage.
        
        Args:
            file_storage: FileStorage object from Flask request
            subdir: Optional subdirectory within the base path
            
        Returns:
            Dictionary with storage metadata
        """
        # Create subdirectory if specified
        target_dir = self.base_path / subdir if subdir else self.base_path
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate secure filename
        filename = secure_filename(file_storage.filename or "upload.bin")
        file_path = target_dir / filename
        
        # Save the file
        file_storage.save(str(file_path))
        
        logger.info(f"File saved to local storage: {file_path}")
        
        return {
            "backend": "local",
            "path": str(file_path),
            "name": filename,
            "size": file_path.stat().st_size if file_path.exists() else 0
        }
    
    def read_bytes(self, file_path: str) -> bytes:
        """Read file contents as bytes."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(path, 'rb') as f:
            return f.read()
    
    def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        return Path(file_path).exists()
    
    def delete(self, file_path: str) -> bool:
        """Delete a file."""
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted local file: {file_path}")
            return True
        return False


class GCSStorage:
    """Google Cloud Storage implementation."""
    
    def __init__(self, bucket_name: str, credentials_path: str):
        """Initialize GCS storage with bucket and credentials."""
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self._client = None
        self._bucket = None
        self._init_client()
    
    def _init_client(self):
        """Initialize GCS client and bucket."""
        try:
            from google.cloud import storage
            from google.auth.exceptions import DefaultCredentialsError
            
            # Set credentials path
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
            
            self._client = storage.Client()
            self._bucket = self._client.bucket(self.bucket_name)
            
            # Verify bucket exists and is accessible
            if not self._bucket.exists():
                raise ValueError(f"GCS bucket '{self.bucket_name}' does not exist or is not accessible")
            
            logger.info(f"GCS storage initialized with bucket: {self.bucket_name}")
            
        except ImportError:
            raise ImportError("google-cloud-storage package is required for GCS storage")
        except (DefaultCredentialsError, FileNotFoundError) as e:
            raise RuntimeError(f"GCS authentication failed: {e}")
    
    def save(self, file_storage, subdir: str = "") -> Dict[str, Any]:
        """Save a file to GCS.
        
        Args:
            file_storage: FileStorage object from Flask request
            subdir: Optional subdirectory within the bucket
            
        Returns:
            Dictionary with storage metadata
        """
        filename = secure_filename(file_storage.filename or "upload.bin")
        blob_name = f"{subdir}/{filename}" if subdir else filename
        
        blob = self._bucket.blob(blob_name)
        blob.upload_from_file(file_storage.stream, rewind=True)
        
        logger.info(f"File uploaded to GCS: gs://{self.bucket_name}/{blob_name}")
        
        return {
            "backend": "gcs",
            "bucket": self.bucket_name,
            "blob": blob_name,
            "uri": f"gs://{self.bucket_name}/{blob_name}",
            "size": blob.size
        }
    
    def read_bytes(self, gcs_uri: str) -> bytes:
        """Read file contents from GCS URI."""
        # Extract blob name from GCS URI
        if gcs_uri.startswith("gs://"):
            parts = gcs_uri[5:].split("/", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid GCS URI format: {gcs_uri}")
            
            bucket_name, blob_name = parts
            if bucket_name != self.bucket_name:
                raise ValueError(f"GCS URI bucket mismatch: {bucket_name} != {self.bucket_name}")
        else:
            blob_name = gcs_uri
        
        blob = self._bucket.blob(blob_name)
        if not blob.exists():
            raise FileNotFoundError(f"GCS blob not found: {gcs_uri}")
        
        return blob.download_as_bytes()
    
    def exists(self, gcs_uri: str) -> bool:
        """Check if file exists in GCS."""
        if gcs_uri.startswith("gs://"):
            parts = gcs_uri[5:].split("/", 1)
            if len(parts) != 2:
                return False
            bucket_name, blob_name = parts
            if bucket_name != self.bucket_name:
                return False
        else:
            blob_name = gcs_uri
        
        blob = self._bucket.blob(blob_name)
        return blob.exists()
    
    def delete(self, gcs_uri: str) -> bool:
        """Delete a file from GCS."""
        if gcs_uri.startswith("gs://"):
            parts = gcs_uri[5:].split("/", 1)
            if len(parts) != 2:
                return False
            bucket_name, blob_name = parts
            if bucket_name != self.bucket_name:
                return False
        else:
            blob_name = gcs_uri
        
        blob = self._bucket.blob(blob_name)
        if blob.exists():
            blob.delete()
            logger.info(f"Deleted GCS blob: {gcs_uri}")
            return True
        return False


def init_storage(app) -> None:
    """Initialize storage adapter based on configuration.
    
    This function determines the appropriate storage backend based on environment
    variables and configuration. It automatically falls back to local storage
    if GCS credentials are not available.
    """
    backend = (app.config.get("STORAGE_BACKEND") or 
               os.getenv("STORAGE_BACKEND") or 
               "auto").lower()
    
    # Prefer explicit env var for GCP key file (matches GCP SDK)
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/gcp.json")
    
    if backend == "gcs" or (backend == "auto" and os.path.exists(cred_path)):
        try:
            bucket_name = app.config.get("GCS_BUCKET_NAME") or os.getenv("GCS_BUCKET_NAME")
            if not bucket_name:
                raise ValueError("GCS_BUCKET_NAME must be set for GCS storage")
            
            storage = GCSStorage(bucket_name, cred_path)
            app.extensions["storage"] = ("gcs", storage)
            app.logger.info(f"GCS storage initialized (bucket={bucket_name})")
            return
            
        except Exception as e:
            app.logger.warning(f"GCS storage initialization failed; falling back to local: {e}")
    
    # Fallback to local storage
    upload_dir = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    storage = LocalStorage(base_path=upload_dir)
    app.extensions["storage"] = ("local", storage)
    app.logger.info(f"Local storage initialized at {upload_dir}")


def get_storage():
    """Get the current storage adapter from Flask app context."""
    from flask import current_app
    
    storage_info = current_app.extensions.get("storage")
    if not storage_info:
        raise RuntimeError("Storage not initialized. Call init_storage() first.")
    
    return storage_info[1]  # Return the storage instance


def save_file(file_storage, subdir: str = "") -> Dict[str, Any]:
    """Save a file using the configured storage backend."""
    storage = get_storage()
    return storage.save(file_storage, subdir)


def read_file_bytes(file_uri: str) -> bytes:
    """Read file contents as bytes from the configured storage backend."""
    storage = get_storage()
    return storage.read_bytes(file_uri)


def file_exists(file_uri: str) -> bool:
    """Check if a file exists in the configured storage backend."""
    storage = get_storage()
    return storage.exists(file_uri)


def delete_file(file_uri: str) -> bool:
    """Delete a file from the configured storage backend."""
    storage = get_storage()
    return storage.delete(file_uri)
