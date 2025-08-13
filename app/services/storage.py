"""
Storage adapter for mdraft.

This module provides a unified Storage class that abstracts over Google Cloud Storage
and local file system storage. It automatically handles path prefixes and provides
consistent error handling.
"""
from __future__ import annotations

import os
import logging
from typing import List, Optional
from pathlib import Path

from flask import current_app


class Storage:
    """Unified storage adapter for GCS and local file system."""
    
    def __init__(self) -> None:
        """Initialize storage adapter based on environment configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Read configuration from environment
        self.use_gcs = current_app.config.get('USE_GCS', False)
        self.gcs_bucket_name = current_app.config.get('GCS_BUCKET_NAME')
        self.google_cloud_project = current_app.config.get('GOOGLE_CLOUD_PROJECT')
        
        # Initialize GCS client if needed
        self._gcs_client = None
        self._gcs_bucket = None
        
        if self.use_gcs:
            if not self.gcs_bucket_name:
                raise ValueError("GCS_BUCKET_NAME must be set when USE_GCS=True")
            self._init_gcs()
        else:
            # Ensure local data directory exists
            self._data_dir = Path("./data")
            self._data_dir.mkdir(exist_ok=True)
            self.logger.info(f"Using local storage at {self._data_dir.absolute()}")
    
    def _init_gcs(self) -> None:
        """Initialize Google Cloud Storage client and bucket."""
        try:
            from google.cloud import storage
            
            self._gcs_client = storage.Client(project=self.google_cloud_project)
            self._gcs_bucket = self._gcs_client.bucket(self.gcs_bucket_name)
            
            # Verify bucket exists and is accessible
            if not self._gcs_bucket.exists():
                raise ValueError(f"GCS bucket '{self.gcs_bucket_name}' does not exist or is not accessible")
            
            self.logger.info(f"Initialized GCS storage with bucket: {self.gcs_bucket_name}")
            
        except ImportError:
            raise ImportError("google-cloud-storage package is required when USE_GCS=True")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GCS storage: {e}")
    
    def write_bytes(self, path: str, data: bytes) -> None:
        """Write bytes to storage at the specified path.
        
        Args:
            path: Relative path where to write the data
            data: Bytes to write
            
        Raises:
            RuntimeError: If write operation fails
        """
        try:
            if self.use_gcs:
                self._write_bytes_gcs(path, data)
            else:
                self._write_bytes_local(path, data)
        except Exception as e:
            self.logger.error(f"Failed to write bytes to {path}: {e}")
            raise RuntimeError(f"Storage write failed: {e}")
    
    def _write_bytes_gcs(self, path: str, data: bytes) -> None:
        """Write bytes to GCS."""
        blob = self._gcs_bucket.blob(path)
        blob.upload_from_string(data)
        self.logger.debug(f"Wrote {len(data)} bytes to GCS: {path}")
    
    def _write_bytes_local(self, path: str, data: bytes) -> None:
        """Write bytes to local file system."""
        file_path = self._data_dir / path
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(data)
        
        self.logger.debug(f"Wrote {len(data)} bytes to local file: {file_path}")
    
    def read_bytes(self, path: str) -> bytes:
        """Read bytes from storage at the specified path.
        
        Args:
            path: Relative path to read from
            
        Returns:
            Bytes read from storage
            
        Raises:
            FileNotFoundError: If file does not exist
            RuntimeError: If read operation fails
        """
        try:
            if self.use_gcs:
                return self._read_bytes_gcs(path)
            else:
                return self._read_bytes_local(path)
        except FileNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to read bytes from {path}: {e}")
            raise RuntimeError(f"Storage read failed: {e}")
    
    def _read_bytes_gcs(self, path: str) -> bytes:
        """Read bytes from GCS."""
        blob = self._gcs_bucket.blob(path)
        
        if not blob.exists():
            raise FileNotFoundError(f"File not found in GCS: {path}")
        
        data = blob.download_as_bytes()
        self.logger.debug(f"Read {len(data)} bytes from GCS: {path}")
        return data
    
    def _read_bytes_local(self, path: str) -> bytes:
        """Read bytes from local file system."""
        file_path = self._data_dir / path
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found locally: {file_path}")
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        self.logger.debug(f"Read {len(data)} bytes from local file: {file_path}")
        return data
    
    def exists(self, path: str) -> bool:
        """Check if a file exists in storage.
        
        Args:
            path: Relative path to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            if self.use_gcs:
                return self._exists_gcs(path)
            else:
                return self._exists_local(path)
        except Exception as e:
            self.logger.error(f"Failed to check existence of {path}: {e}")
            return False
    
    def _exists_gcs(self, path: str) -> bool:
        """Check if file exists in GCS."""
        blob = self._gcs_bucket.blob(path)
        return blob.exists()
    
    def _exists_local(self, path: str) -> bool:
        """Check if file exists locally."""
        file_path = self._data_dir / path
        return file_path.exists()
    
    def list_prefix(self, prefix: str) -> List[str]:
        """List all files with the given prefix.
        
        Args:
            prefix: Prefix to filter files by
            
        Returns:
            List of file paths matching the prefix
        """
        try:
            if self.use_gcs:
                return self._list_prefix_gcs(prefix)
            else:
                return self._list_prefix_local(prefix)
        except Exception as e:
            self.logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []
    
    def _list_prefix_gcs(self, prefix: str) -> List[str]:
        """List files with prefix in GCS."""
        blobs = self._gcs_bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]
    
    def _list_prefix_local(self, prefix: str) -> List[str]:
        """List files with prefix locally."""
        prefix_path = self._data_dir / prefix
        
        if not prefix_path.exists():
            return []
        
        files = []
        for file_path in prefix_path.rglob('*'):
            if file_path.is_file():
                # Convert to relative path from data directory
                relative_path = file_path.relative_to(self._data_dir)
                files.append(str(relative_path))
        
        return files
    
    def delete(self, path: str) -> bool:
        """Delete a file from storage.
        
        Args:
            path: Relative path to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            if self.use_gcs:
                return self._delete_gcs(path)
            else:
                return self._delete_local(path)
        except Exception as e:
            self.logger.error(f"Failed to delete {path}: {e}")
            return False
    
    def _delete_gcs(self, path: str) -> bool:
        """Delete file from GCS."""
        blob = self._gcs_bucket.blob(path)
        if blob.exists():
            blob.delete()
            self.logger.debug(f"Deleted file from GCS: {path}")
            return True
        return False
    
    def _delete_local(self, path: str) -> bool:
        """Delete file locally."""
        file_path = self._data_dir / path
        if file_path.exists():
            file_path.unlink()
            self.logger.debug(f"Deleted local file: {file_path}")
            return True
        return False
