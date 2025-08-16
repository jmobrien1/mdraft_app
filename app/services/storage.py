"""
Storage adapter for mdraft.

This module provides a unified Storage class that abstracts over Google Cloud Storage
and local file system storage. It automatically handles path prefixes and provides
consistent error handling with reliability features.
"""
from __future__ import annotations

import os
import logging
import uuid
import time
from typing import List, Optional, Tuple
from pathlib import Path

from flask import current_app
from .reliability import resilient_call, ReliabilityError, ExternalServiceError


def _get_request_id() -> str:
    """Get current request ID from context or generate new one."""
    try:
        from app.utils.logging import get_correlation_ids
        correlation_ids = get_correlation_ids()
        return correlation_ids.get("request_id") or "unknown"
    except ImportError:
        # Fallback to Flask request context
        try:
            from flask import request
            return request.environ.get('X-Request-ID', 'unknown')
        except RuntimeError:
            return "unknown"


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageAuthError(StorageError):
    """Authentication error for storage operations."""
    pass


class StorageTimeoutError(StorageError):
    """Timeout error for storage operations."""
    pass


class Storage:
    """Unified storage adapter for GCS and local file system with atomic operations."""
    
    def __init__(self) -> None:
        """Initialize storage adapter based on environment configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Read configuration from environment
        self.use_gcs = current_app.config.get('USE_GCS', False)
        self.gcs_bucket_name = current_app.config.get('GCS_BUCKET_NAME')
        self.google_cloud_project = current_app.config.get('GOOGLE_CLOUD_PROJECT')
        
        # Operation timeouts (in seconds)
        self.upload_timeout = current_app.config.get('STORAGE_UPLOAD_TIMEOUT', 300)  # 5 minutes
        self.download_timeout = current_app.config.get('STORAGE_DOWNLOAD_TIMEOUT', 300)  # 5 minutes
        self.delete_timeout = current_app.config.get('STORAGE_DELETE_TIMEOUT', 60)  # 1 minute
        
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
            from google.auth.exceptions import DefaultCredentialsError, RefreshError
            
            self._gcs_client = storage.Client(project=self.google_cloud_project)
            self._gcs_bucket = self._gcs_client.bucket(self.gcs_bucket_name)
            
            # Verify bucket exists and is accessible
            if not self._gcs_bucket.exists():
                raise ValueError(f"GCS bucket '{self.gcs_bucket_name}' does not exist or is not accessible")
            
            self.logger.info(f"Initialized GCS storage with bucket: {self.gcs_bucket_name}")
            
        except ImportError:
            raise ImportError("google-cloud-storage package is required when USE_GCS=True")
        except (DefaultCredentialsError, RefreshError) as e:
            raise StorageAuthError(f"GCS authentication failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GCS storage: {e}")
    
    def _generate_temp_path(self, original_path: str) -> str:
        """Generate a temporary path for atomic operations."""
        # Extract directory and filename
        path_obj = Path(original_path)
        temp_filename = f".tmp_{uuid.uuid4().hex}_{int(time.time())}_{path_obj.name}"
        return str(path_obj.parent / temp_filename)
    
    def write_bytes(self, path: str, data: bytes) -> None:
        """Write bytes to storage at the specified path using atomic operations.
        
        Args:
            path: Relative path where to write the data
            data: Bytes to write
            
        Raises:
            StorageAuthError: If authentication fails
            StorageTimeoutError: If operation times out
            StorageError: If write operation fails
        """
        request_id = _get_request_id()
        temp_path = None
        
        try:
            if self.use_gcs:
                temp_path = self._generate_temp_path(path)
                self._write_bytes_gcs_atomic(path, temp_path, data, request_id)
            else:
                temp_path = self._generate_temp_path(path)
                self._write_bytes_local_atomic(path, temp_path, data, request_id)
                
        except ReliabilityError as e:
            # Map reliability errors to storage errors
            if e.error_type == ExternalServiceError.AUTHENTICATION_ERROR:
                raise StorageAuthError(f"Storage authentication failed: {e}")
            elif e.error_type == ExternalServiceError.TIMEOUT:
                raise StorageTimeoutError(f"Storage operation timed out: {e}")
            else:
                raise StorageError(f"Storage write failed: {e}")
        except Exception as e:
            # Cleanup temp file on any error
            if temp_path and self.use_gcs:
                self._cleanup_temp_file_gcs(temp_path, request_id)
            elif temp_path and not self.use_gcs:
                self._cleanup_temp_file_local(temp_path, request_id)
            
            self.logger.error(f"Failed to write bytes to {path}: {e} request_id={request_id}")
            raise StorageError(f"Storage write failed: {e}")
    
    def _write_bytes_gcs_atomic(self, final_path: str, temp_path: str, data: bytes, request_id: str) -> None:
        """Write bytes to GCS using atomic operations with temp file."""
        def _upload_temp_to_gcs():
            blob = self._gcs_bucket.blob(temp_path)
            
            # Add custom metadata including request ID
            metadata = {
                'request_id': request_id,
                'mdraft_version': '1.0',
                'content_length': str(len(data)),
                'temp_file': 'true',
                'final_path': final_path
            }
            blob.metadata = metadata
            
            blob.upload_from_string(data)
            return True
        
        def _compose_final_blob():
            # Use GCS compose operation to atomically move from temp to final
            temp_blob = self._gcs_bucket.blob(temp_path)
            final_blob = self._gcs_bucket.blob(final_path)
            
            # Verify temp blob exists
            if not temp_blob.exists():
                raise FileNotFoundError(f"Temporary file {temp_path} not found")
            
            # Compose operation (atomic move)
            final_blob.compose([temp_blob])
            
            # Update metadata for final blob
            final_metadata = {
                'request_id': request_id,
                'mdraft_version': '1.0',
                'content_length': str(len(data)),
                'final_path': final_path
            }
            final_blob.metadata = final_metadata
            final_blob.patch()
            
            # Delete temp blob
            temp_blob.delete()
            return True
        
        # Step 1: Upload to temp location
        resilient_call(
            service_name="gcs",
            endpoint="upload_temp",
            func=_upload_temp_to_gcs,
            timeout_sec=self.upload_timeout
        )
        
        # Step 2: Atomically compose to final location
        resilient_call(
            service_name="gcs",
            endpoint="compose",
            func=_compose_final_blob,
            timeout_sec=self.upload_timeout
        )
        
        # Step 3: Verify final blob exists
        if not self._exists_gcs(final_path, request_id):
            raise StorageError(f"Final blob {final_path} not found after atomic write")
        
        self.logger.debug(f"Atomically wrote {len(data)} bytes to GCS: {final_path} request_id={request_id}")
    
    def _write_bytes_local_atomic(self, final_path: str, temp_path: str, data: bytes, request_id: str) -> None:
        """Write bytes to local file system using atomic operations."""
        temp_file_path = self._data_dir / temp_path
        final_file_path = self._data_dir / final_path
        
        # Ensure parent directory exists
        temp_file_path.parent.mkdir(parents=True, exist_ok=True)
        final_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file
        with open(temp_file_path, 'wb') as f:
            f.write(data)
        
        # Atomic rename (this is atomic on most filesystems)
        temp_file_path.rename(final_file_path)
        
        self.logger.debug(f"Atomically wrote {len(data)} bytes to local file: {final_file_path} request_id={request_id}")
    
    def _cleanup_temp_file_gcs(self, temp_path: str, request_id: str) -> None:
        """Clean up temporary GCS file on error."""
        try:
            blob = self._gcs_bucket.blob(temp_path)
            if blob.exists():
                blob.delete()
                self.logger.debug(f"Cleaned up temp GCS file: {temp_path} request_id={request_id}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temp GCS file {temp_path}: {e} request_id={request_id}")
    
    def _cleanup_temp_file_local(self, temp_path: str, request_id: str) -> None:
        """Clean up temporary local file on error."""
        try:
            temp_file_path = self._data_dir / temp_path
            if temp_file_path.exists():
                temp_file_path.unlink()
                self.logger.debug(f"Cleaned up temp local file: {temp_file_path} request_id={request_id}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temp local file {temp_path}: {e} request_id={request_id}")
    
    def read_bytes(self, path: str) -> bytes:
        """Read bytes from storage at the specified path.
        
        Args:
            path: Relative path to read from
            
        Returns:
            Bytes read from storage
            
        Raises:
            FileNotFoundError: If file does not exist
            StorageAuthError: If authentication fails
            StorageTimeoutError: If operation times out
            StorageError: If read operation fails
        """
        request_id = _get_request_id()
        try:
            if self.use_gcs:
                return self._read_bytes_gcs(path, request_id)
            else:
                return self._read_bytes_local(path, request_id)
        except FileNotFoundError:
            raise
        except ReliabilityError as e:
            # Map reliability errors to storage errors
            if e.error_type == ExternalServiceError.AUTHENTICATION_ERROR:
                raise StorageAuthError(f"Storage authentication failed: {e}")
            elif e.error_type == ExternalServiceError.TIMEOUT:
                raise StorageTimeoutError(f"Storage operation timed out: {e}")
            else:
                raise StorageError(f"Storage read failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to read bytes from {path}: {e} request_id={request_id}")
            raise StorageError(f"Storage read failed: {e}")
    
    def _read_bytes_gcs(self, path: str, request_id: str) -> bytes:
        """Read bytes from GCS with reliability features."""
        def _download_from_gcs():
            blob = self._gcs_bucket.blob(path)
            
            if not blob.exists():
                raise FileNotFoundError(f"File not found in GCS: {path}")
            
            return blob.download_as_bytes()
        
        # Use resilient_call for automatic retries and circuit breaker
        data = resilient_call(
            service_name="gcs",
            endpoint="download",
            func=_download_from_gcs,
            timeout_sec=self.download_timeout
        )
        
        self.logger.debug(f"Read {len(data)} bytes from GCS: {path} request_id={request_id}")
        return data
    
    def _read_bytes_local(self, path: str, request_id: str) -> bytes:
        """Read bytes from local file system."""
        file_path = self._data_dir / path
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found locally: {file_path}")
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        self.logger.debug(f"Read {len(data)} bytes from local file: {file_path} request_id={request_id}")
        return data
    
    def exists(self, path: str) -> bool:
        """Check if a file exists in storage.
        
        Args:
            path: Relative path to check
            
        Returns:
            True if file exists, False otherwise
        """
        request_id = _get_request_id()
        try:
            if self.use_gcs:
                return self._exists_gcs(path, request_id)
            else:
                return self._exists_local(path, request_id)
        except Exception as e:
            self.logger.error(f"Failed to check existence of {path}: {e} request_id={request_id}")
            return False
    
    def _exists_gcs(self, path: str, request_id: str) -> bool:
        """Check if file exists in GCS with reliability features."""
        def _check_exists_gcs():
            blob = self._gcs_bucket.blob(path)
            return blob.exists()
        
        # Use resilient_call for automatic retries and circuit breaker
        exists = resilient_call(
            service_name="gcs",
            endpoint="exists",
            func=_check_exists_gcs,
            timeout_sec=30  # Short timeout for existence checks
        )
        
        self.logger.debug(f"Checked existence in GCS: {path} exists={exists} request_id={request_id}")
        return exists
    
    def _exists_local(self, path: str, request_id: str) -> bool:
        """Check if file exists locally."""
        file_path = self._data_dir / path
        exists = file_path.exists()
        self.logger.debug(f"Checked existence locally: {file_path} exists={exists} request_id={request_id}")
        return exists
    
    def list_prefix(self, path: str) -> List[str]:
        """List all files with the given prefix.
        
        Args:
            path: Prefix to filter files by
            
        Returns:
            List of file paths matching the prefix
        """
        request_id = _get_request_id()
        try:
            if self.use_gcs:
                return self._list_prefix_gcs(path, request_id)
            else:
                return self._list_prefix_local(path, request_id)
        except Exception as e:
            self.logger.error(f"Failed to list files with prefix {path}: {e} request_id={request_id}")
            return []
    
    def _list_prefix_gcs(self, prefix: str, request_id: str) -> List[str]:
        """List files with prefix in GCS with reliability features."""
        def _list_blobs_gcs():
            blobs = self._gcs_bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        
        # Use resilient_call for automatic retries and circuit breaker
        file_list = resilient_call(
            service_name="gcs",
            endpoint="list",
            func=_list_blobs_gcs,
            timeout_sec=60  # Reasonable timeout for listing
        )
        
        self.logger.debug(f"Listed {len(file_list)} files with prefix {prefix} in GCS request_id={request_id}")
        return file_list
    
    def _list_prefix_local(self, prefix: str, request_id: str) -> List[str]:
        """List files with prefix locally."""
        prefix_path = self._data_dir / prefix
        file_list = []
        
        if prefix_path.exists():
            for file_path in prefix_path.rglob('*'):
                if file_path.is_file():
                    # Convert to relative path
                    rel_path = str(file_path.relative_to(self._data_dir))
                    file_list.append(rel_path)
        
        self.logger.debug(f"Listed {len(file_list)} files with prefix {prefix} locally request_id={request_id}")
        return file_list
    
    def delete(self, path: str) -> bool:
        """Delete a file from storage.
        
        Args:
            path: Relative path to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        request_id = _get_request_id()
        try:
            if self.use_gcs:
                return self._delete_gcs(path, request_id)
            else:
                return self._delete_local(path, request_id)
        except Exception as e:
            self.logger.error(f"Failed to delete {path}: {e} request_id={request_id}")
            return False
    
    def _delete_gcs(self, path: str, request_id: str) -> bool:
        """Delete file from GCS with reliability features."""
        def _delete_blob_gcs():
            blob = self._gcs_bucket.blob(path)
            if blob.exists():
                blob.delete()
                return True
            return False
        
        # Use resilient_call for automatic retries and circuit breaker
        deleted = resilient_call(
            service_name="gcs",
            endpoint="delete",
            func=_delete_blob_gcs,
            timeout_sec=self.delete_timeout
        )
        
        if deleted:
            self.logger.debug(f"Deleted file from GCS: {path} request_id={request_id}")
        
        return deleted
    
    def _delete_local(self, path: str, request_id: str) -> bool:
        """Delete file locally."""
        file_path = self._data_dir / path
        if file_path.exists():
            file_path.unlink()
            self.logger.debug(f"Deleted local file: {file_path} request_id={request_id}")
            return True
        return False
