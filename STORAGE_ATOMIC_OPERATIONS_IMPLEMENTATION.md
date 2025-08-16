# Storage Atomic Operations Implementation

## Overview

This document summarizes the implementation of atomic uploads/downloads with proper error handling and auth error surfacing for the GCS storage service in the mdraft application.

## Key Features Implemented

### 1. Atomic Operations
- **Write to temp names, then compose/rename to final key**: All write operations now use a two-phase commit approach
  - Phase 1: Write data to a temporary location with unique naming
  - Phase 2: Atomically move/rename to the final location
- **GCS Implementation**: Uses GCS compose operation for atomic moves
- **Local Implementation**: Uses filesystem atomic rename operations

### 2. Per-Operation Timeouts
- **Configurable timeouts**: Each operation type has its own timeout
  - `STORAGE_UPLOAD_TIMEOUT`: 300 seconds (5 minutes) for uploads
  - `STORAGE_DOWNLOAD_TIMEOUT`: 300 seconds (5 minutes) for downloads  
  - `STORAGE_DELETE_TIMEOUT`: 60 seconds (1 minute) for deletions
- **Short timeouts for metadata operations**: 30 seconds for existence checks, 60 seconds for listing

### 3. Cleanup on Failures
- **Automatic cleanup**: On any failure after partial write, temporary files are automatically cleaned up
- **Graceful cleanup failures**: Cleanup failures are logged but don't prevent error propagation
- **No orphaned blobs**: Ensures no temporary files remain in storage

### 4. Auth Error Surfacing
- **Distinct auth error detection**: GCS authentication failures are detected and surfaced as `StorageAuthError`
- **Clear error hierarchy**: 
  - `StorageError`: Base storage exception
  - `StorageAuthError`: Authentication/authorization failures
  - `StorageTimeoutError`: Operation timeout failures
- **Proper error mapping**: Reliability errors are mapped to appropriate storage exceptions

### 5. Final Verification
- **Never return success if final blob absent**: After atomic operations, the final blob is verified to exist
- **Fail-fast approach**: If final verification fails, the operation is considered failed

## Implementation Details

### Storage Class Enhancements

#### New Exception Classes
```python
class StorageError(Exception):
    """Base exception for storage operations."""
    pass

class StorageAuthError(StorageError):
    """Authentication error for storage operations."""
    pass

class StorageTimeoutError(StorageError):
    """Timeout error for storage operations."""
    pass
```

#### Atomic Write Operations
```python
def write_bytes(self, path: str, data: bytes) -> None:
    """Write bytes to storage at the specified path using atomic operations."""
    temp_path = self._generate_temp_path(path)
    
    try:
        if self.use_gcs:
            self._write_bytes_gcs_atomic(path, temp_path, data, request_id)
        else:
            self._write_bytes_local_atomic(path, temp_path, data, request_id)
    except Exception as e:
        # Cleanup temp file on any error
        if temp_path and self.use_gcs:
            self._cleanup_temp_file_gcs(temp_path, request_id)
        elif temp_path and not self.use_gcs:
            self._cleanup_temp_file_local(temp_path, request_id)
        raise StorageError(f"Storage write failed: {e}")
```

#### GCS Atomic Operations
```python
def _write_bytes_gcs_atomic(self, final_path: str, temp_path: str, data: bytes, request_id: str) -> None:
    """Write bytes to GCS using atomic operations with temp file."""
    
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
```

### Error Handling Improvements

#### Reliability Error Mapping
```python
except ReliabilityError as e:
    # Map reliability errors to storage errors
    if e.error_type == ExternalServiceError.AUTHENTICATION_ERROR:
        raise StorageAuthError(f"Storage authentication failed: {e}")
    elif e.error_type == ExternalServiceError.TIMEOUT:
        raise StorageTimeoutError(f"Storage operation timed out: {e}")
    else:
        raise StorageError(f"Storage write failed: {e}")
```

#### GCS Auth Error Detection
```python
def _init_gcs(self) -> None:
    """Initialize Google Cloud Storage client and bucket."""
    try:
        from google.cloud import storage
        from google.auth.exceptions import DefaultCredentialsError, RefreshError
        
        self._gcs_client = storage.Client(project=self.google_cloud_project)
        # ... initialization code ...
        
    except ImportError:
        raise ImportError("google-cloud-storage package is required when USE_GCS=True")
    except (DefaultCredentialsError, RefreshError) as e:
        raise StorageAuthError(f"GCS authentication failed: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize GCS storage: {e}")
```

## Testing Strategy

### Comprehensive Test Coverage

#### 1. Atomic Operations Testing
- **Success scenarios**: Verify atomic operations complete successfully
- **Failure scenarios**: Test cleanup on various failure points
- **Verification**: Ensure no orphaned blobs remain

#### 2. Error Handling Testing
- **Auth errors**: Test GCS authentication failure detection
- **Timeout errors**: Test operation timeout handling
- **Network errors**: Test connection and server error handling
- **Cleanup failures**: Test graceful handling of cleanup failures

#### 3. Edge Cases
- **Partial failures**: Test cleanup when operations fail mid-way
- **Final verification failures**: Test when final blob verification fails
- **Temp file generation**: Test unique temporary path generation

### Test Categories

#### Local Storage Tests
- Atomic write operations with cleanup
- Error handling for local filesystem operations
- Verification of no orphaned temporary files

#### GCS Storage Tests
- Atomic operations using GCS compose
- Auth error detection and surfacing
- Timeout handling for all operations
- Cleanup verification on failures

#### Error Mapping Tests
- Reliability error to storage error mapping
- Auth error surfacing
- Timeout error surfacing
- Connection error handling

#### Atomic Operations Tests
- Temporary path generation
- Cleanup on partial failures
- No orphaned blobs verification
- Cleanup failure handling

## Configuration

### Environment Variables
```bash
# Storage timeouts (in seconds)
STORAGE_UPLOAD_TIMEOUT=300      # 5 minutes for uploads
STORAGE_DOWNLOAD_TIMEOUT=300    # 5 minutes for downloads
STORAGE_DELETE_TIMEOUT=60       # 1 minute for deletions

# GCS configuration
USE_GCS=true
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_CLOUD_PROJECT=your-project-id
```

## Benefits

### 1. Data Integrity
- **Atomic operations**: Prevents partial writes and data corruption
- **Final verification**: Ensures operations complete successfully
- **No orphaned files**: Automatic cleanup prevents storage bloat

### 2. Reliability
- **Timeout handling**: Prevents hanging operations
- **Retry logic**: Built-in retry with exponential backoff
- **Circuit breaker**: Prevents cascading failures

### 3. Observability
- **Clear error types**: Distinct error classes for different failure modes
- **Request tracking**: All operations include request IDs for tracing
- **Comprehensive logging**: Detailed logs for debugging and monitoring

### 4. Security
- **Auth error detection**: Clear identification of authentication issues
- **Secure error messages**: No sensitive information in error messages
- **Proper exception handling**: Prevents information leakage

## Acceptance Criteria Met

✅ **Write to temp names, then compose/rename to final key**: Implemented for both GCS and local storage

✅ **Ensure per-op timeouts**: Configurable timeouts for all operation types

✅ **On failure after partial write, attempt cleanup**: Automatic cleanup with graceful failure handling

✅ **Never return success if final blob absent**: Final verification step ensures data integrity

✅ **Detect GCS auth failures distinctly**: Clear auth error detection and surfacing

✅ **Tests simulate network/auth failures**: Comprehensive test coverage for all failure scenarios

✅ **Verify no orphaned blobs**: Tests confirm cleanup prevents orphaned files

## Future Enhancements

1. **Metrics and monitoring**: Add metrics for operation success/failure rates
2. **Compression support**: Add optional compression for large files
3. **Encryption**: Add client-side encryption support
4. **Multi-region**: Support for multi-region GCS buckets
5. **Lifecycle management**: Automatic cleanup of old temporary files
