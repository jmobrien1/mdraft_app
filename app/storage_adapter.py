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


class Storage:
    """Unified storage interface for mdraft application."""
    
    backend_name = "base"
    
    def save(self, key: str, stream) -> Dict[str, Any]:
        """Save a stream to storage with the given key."""
        raise NotImplementedError
    
    def open(self, key: str) -> BinaryIO:
        """Open a file stream for the given key."""
        raise NotImplementedError
    
    def exists(self, key: str) -> bool:
        """Check if a file exists with the given key."""
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        """Delete a file with the given key."""
        raise NotImplementedError


class LocalStorage(Storage):
    """Local file system storage implementation."""
    
    backend_name = "local"
    
    def __init__(self, base_path: str = "/tmp/uploads"):
        """Initialize local storage with the specified base path."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage initialized at {self.base_path.absolute()}")
    
    def save(self, key: str, stream) -> Dict[str, Any]:
        """Save a stream to local storage.
        
        Args:
            key: Storage key (filename)
            stream: File-like object to save
            
        Returns:
            Dictionary with storage metadata
        """
        file_path = self.base_path / key
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the stream
        with open(file_path, 'wb') as f:
            if hasattr(stream, 'read'):
                # File-like object
                while True:
                    chunk = stream.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
            else:
                # Assume it's bytes or string
                f.write(stream)
        
        logger.info(f"File saved to local storage: {file_path}")
        
        return {
            "backend": "local",
            "path": str(file_path),
            "key": key,
            "size": file_path.stat().st_size if file_path.exists() else 0
        }
    
    def open(self, key: str) -> BinaryIO:
        """Open a file stream for the given key."""
        file_path = self.base_path / key
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return open(file_path, 'rb')
    
    def exists(self, key: str) -> bool:
        """Check if file exists."""
        return (self.base_path / key).exists()
    
    def delete(self, key: str) -> bool:
        """Delete a file."""
        file_path = self.base_path / key
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted local file: {file_path}")
            return True
        return False
    
    # Legacy method for backward compatibility
    def save_file_storage(self, file_storage, subdir: str = "") -> Dict[str, Any]:
        """Save a FileStorage object to local storage (legacy method)."""
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


class GCSStorage(Storage):
    """Google Cloud Storage implementation."""
    
    backend_name = "gcs"
    
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
    
    def save(self, key: str, stream) -> Dict[str, Any]:
        """Save a stream to GCS.
        
        Args:
            key: Storage key (blob name)
            stream: File-like object to save
            
        Returns:
            Dictionary with storage metadata
        """
        blob = self._bucket.blob(key)
        
        if hasattr(stream, 'read'):
            # File-like object
            blob.upload_from_file(stream, rewind=True)
        else:
            # Assume it's bytes or string
            blob.upload_from_string(stream)
        
        logger.info(f"File uploaded to GCS: gs://{self.bucket_name}/{key}")
        
        return {
            "backend": "gcs",
            "bucket": self.bucket_name,
            "blob": key,
            "uri": f"gs://{self.bucket_name}/{key}",
            "size": blob.size
        }
    
    def open(self, key: str) -> BinaryIO:
        """Open a file stream for the given key."""
        blob = self._bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(f"GCS blob not found: gs://{self.bucket_name}/{key}")
        
        # Return a file-like object that reads from the blob
        return blob.open('rb')
    
    def exists(self, key: str) -> bool:
        """Check if file exists in GCS."""
        blob = self._bucket.blob(key)
        return blob.exists()
    
    def delete(self, key: str) -> bool:
        """Delete a file from GCS."""
        blob = self._bucket.blob(key)
        if blob.exists():
            blob.delete()
            logger.info(f"Deleted GCS blob: gs://{self.bucket_name}/{key}")
            return True
        return False
    
    # Legacy method for backward compatibility
    def save_file_storage(self, file_storage, subdir: str = "") -> Dict[str, Any]:
        """Save a FileStorage object to GCS (legacy method)."""
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


def init_storage(app) -> None:
    """Initialize storage adapter based on configuration.
    
    This function determines the appropriate storage backend based on environment
    variables and configuration. It automatically falls back to local storage
    if GCS credentials are not available.
    """
    backend = (app.config.get("STORAGE_BACKEND") or 
               os.getenv("STORAGE_BACKEND") or 
               "auto").lower()
    
    # Check for GCS credentials in multiple ways
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/gcp.json")
    cred_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    
    # If we have JSON credentials, write them to a temporary file
    if cred_json and not os.path.exists(cred_path):
        try:
            import tempfile
            import json
            
            # Validate JSON
            json.loads(cred_json)
            
            # Write to temporary file
            with open(cred_path, 'w') as f:
                f.write(cred_json)
            
            app.logger.info(f"GCS credentials written to {cred_path}")
        except Exception as e:
            app.logger.warning(f"Failed to write GCS credentials: {e}")
            cred_path = None
    
    if backend == "gcs" or (backend == "auto" and (os.path.exists(cred_path) or cred_json)):
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
    return storage.save_file_storage(file_storage, subdir)


def save_stream(key: str, stream) -> Dict[str, Any]:
    """Save a stream using the configured storage backend."""
    storage = get_storage()
    return storage.save(key, stream)


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
