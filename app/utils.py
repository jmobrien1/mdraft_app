"""
Utility functions for mdraft.

This module contains helper functions for validating uploaded files
using their magic numbers, generating signed download URLs, and
retrieving correlation IDs from requests.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Iterable, Optional

import filetype

# Allowed MIME types for uploaded documents.  Only PDFs and DOCX files
# are supported in the initial MVP.  Additional types may be added
# later as conversion engines are integrated.
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def generate_job_id() -> str:
    """Generate a unique identifier for a job.

    Uses UUID4 for randomness.  While database IDs are numeric, job
    identifiers returned to clients can be strings to obfuscate
    internal IDs and make URLs opaque.
    """
    return uuid.uuid4().hex


def is_file_allowed(stream) -> bool:
    """Check whether the uploaded file's MIME type is allowed.

    This function reads a small portion of the file stream to detect
    its MIME type using the `filetype` library.  The stream's
    position is reset after detection so the calling code can read
    from the beginning.  Only files whose detected MIME type is in
    ALLOWED_MIME_TYPES are accepted.

    Args:
        stream: A file-like object supporting read() and seek().

    Returns:
        True if the file is of an allowed type; False otherwise.
    """
    position = stream.tell()
    sample = stream.read(261)
    stream.seek(position)
    kind = filetype.guess(sample)
    if kind is None:
        return False
    return kind.mime in ALLOWED_MIME_TYPES


def generate_download_url(local_path: str, expires_in: int = 900) -> str:
    """Generate a temporary download URL for a file stored locally.

    In production the application would generate a signed URL via the
    Google Cloud Storage client.  For development purposes, this
    function constructs a pseudo-URL that includes a simple expiry
    timestamp.  Because the local server can serve files directly
    without authentication, this function primarily demonstrates the
    signed URL concept.

    Args:
        local_path: Absolute path to the file on disk.
        expires_in: Time-to-live in seconds for the URL (default 15 minutes).

    Returns:
        A string representing a pseudo-URL with an expiry timestamp.
    """
    expiry = int(time.time()) + expires_in
    filename = os.path.basename(local_path)
    # In a real implementation, you would use something like
    # blob.generate_signed_url().  Here we include the expiry for demo.
    return f"/download/{filename}?expires={expiry}"


def get_correlation_id(environ: dict) -> str:
    """Retrieve the correlation ID from the request environment.

    If the HTTP_X_REQUEST_ID header is present in the environment, use
    it; otherwise return a randomly generated UUID.
    """
    return environ.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)