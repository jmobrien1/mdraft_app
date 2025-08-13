# Storage Adapter and Health Endpoints

This document describes the new Storage adapter and health endpoints implemented for the mdraft application.

## Storage Adapter

The `Storage` class in `app/services/storage.py` provides a unified interface for both Google Cloud Storage (GCS) and local file system storage. It automatically handles path prefixes and provides consistent error handling.

### Configuration

The Storage adapter is configured through environment variables:

- `USE_GCS` (bool): Set to `1` to use GCS, otherwise uses local storage
- `GCS_BUCKET_NAME` (str): GCS bucket name (required when USE_GCS=1)
- `GOOGLE_CLOUD_PROJECT` (str): Google Cloud project ID (optional)

### Usage

```python
from app.services import Storage

# Initialize storage adapter
storage = Storage()

# Write data to storage
storage.write_bytes("uploads/job_123/document.pdf", file_data)

# Read data from storage
data = storage.read_bytes("uploads/job_123/document.pdf")

# Check if file exists
if storage.exists("uploads/job_123/document.pdf"):
    # File exists
    pass

# List files with prefix
files = storage.list_prefix("uploads/job_123/")

# Delete file
storage.delete("uploads/job_123/document.pdf")
```

### Path Structure

The Storage adapter automatically handles path prefixes:

- **Uploads**: Files are stored at `uploads/<job_id>/<filename>`
- **Outputs**: Converted files are stored at `outputs/<job_id>/result.md`

### Error Handling

The Storage adapter provides consistent error handling:

- `FileNotFoundError`: Raised when trying to read a non-existent file
- `RuntimeError`: Raised for other storage operation failures
- `ValueError`: Raised for configuration errors
- `ImportError`: Raised when GCS is enabled but the package is not available

## Health Endpoints

The application now provides comprehensive health check endpoints:

### `/healthz` - Fast Health Check

Returns a quick health status without checking external dependencies.

**Response:**
```json
{
  "status": "healthy",
  "service": "mdraft",
  "version": "1.0.0"
}
```

### `/readyz` - Comprehensive Readiness Check

Performs thorough checks including database connectivity, Redis ping, and storage access.

**Response (all healthy):**
```json
{
  "status": "ready",
  "service": "mdraft",
  "version": "1.0.0",
  "checks": {
    "database": true,
    "redis": true,
    "storage": true
  }
}
```

**Response (some checks failed):**
```json
{
  "status": "not_ready",
  "service": "mdraft",
  "version": "1.0.0",
  "checks": {
    "database": false,
    "redis": true,
    "storage": true
  },
  "message": "One or more health checks failed"
}
```

### `/health` - Legacy Health Check

Maintained for backward compatibility. Performs database connectivity check.

## Integration

The Storage adapter has been integrated into the upload and conversion flows:

1. **Upload Flow**: Files are stored using `storage.write_bytes()` at `uploads/<job_id>/<filename>`
2. **Conversion Flow**: Results are stored using `storage.write_bytes()` at `outputs/<job_id>/result.md`
3. **Download Flow**: Files are served through the `/download/<path>` endpoint using `storage.read_bytes()`

## Testing

Comprehensive tests are available in `tests/test_storage.py` and `tests/test_health.py`:

- Local storage mode tests
- GCS mode tests (with mocked dependencies)
- Error handling tests
- Health endpoint tests

Run tests with:
```bash
python3 -m pytest tests/test_storage.py -v
python3 -m pytest tests/test_health.py -v
```

## Migration Notes

The new Storage adapter replaces the previous direct GCS integration:

- Old: Direct calls to `upload_stream_to_gcs()`, `upload_text_to_gcs()`, etc.
- New: Unified `Storage` class with consistent interface

The health endpoints provide better monitoring capabilities:

- `/healthz` for load balancer health checks
- `/readyz` for comprehensive readiness monitoring
- `/health` maintained for backward compatibility
