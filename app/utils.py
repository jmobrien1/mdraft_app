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
import logging
import zipfile
from typing import Iterable, Optional
from io import BytesIO

import filetype

# Allowed MIME types for uploaded documents.  PDFs, DOCX files, and plain text
# are supported.  Additional types may be added later as conversion engines
# are integrated.
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Allowed file extensions as a secondary check when magic detection is inconclusive
ALLOWED_EXTENSIONS: set[str] = {
    ".pdf",
    ".doc",
    ".docx",
}


def generate_job_id() -> str:
    """Generate a unique identifier for a job.

    Uses UUID4 for randomness.  While database IDs are numeric, job
    identifiers returned to clients can be strings to obfuscate
    internal IDs and make URLs opaque.
    """
    return uuid.uuid4().hex


def is_file_allowed(stream, filename: str = "") -> bool:
    """Check whether the uploaded file's MIME type is allowed.

    This function performs robust file type detection using magic numbers
    and file extensions. It includes special handling for DOCX files which
    may be detected as ZIP files by magic number detection.

    Args:
        stream: A file-like object supporting read() and seek().
        filename: Optional filename for extension-based validation.

    Returns:
        True if the file is of an allowed type; False otherwise.
    """
    logger = logging.getLogger(__name__)
    
    # Always reset stream position before and after detection
    stream.seek(0)
    sample = stream.read(261)
    stream.seek(0)
    
    # Get file extension (lowercase)
    file_ext = os.path.splitext(filename)[1].lower() if filename else ""
    
    # Magic number detection
    kind = filetype.guess(sample)
    magic_mime = kind.mime if kind else None
    
    logger.info(f"File validation - Magic MIME: {magic_mime}, Extension: {file_ext}")
    
    # Primary check: Magic MIME is in allowed types
    if magic_mime in ALLOWED_MIME_TYPES:
        logger.info(f"File accepted via magic MIME match: {magic_mime}")
        return True
    
    # Special handling for DOCX files
    if file_ext == ".docx":
        # Check if magic reports application/zip (DOCX is a ZIP container)
        if magic_mime == "application/zip":
            logger.info("DOCX detected via ZIP magic number")
            return _validate_docx_structure(sample, stream, logger)
        
        # Check if magic is None but stream begins with ZIP signature
        if magic_mime is None and len(sample) >= 2 and sample[:2] == b'PK':
            logger.info("DOCX detected via ZIP signature (PK)")
            return _validate_docx_structure(sample, stream, logger)
    
    # Secondary check: Extension is allowed when magic is inconclusive
    if file_ext in ALLOWED_EXTENSIONS and magic_mime is None:
        logger.info(f"File accepted via extension match (magic inconclusive): {file_ext}")
        return True
    
    logger.info(f"File rejected - Magic: {magic_mime}, Extension: {file_ext}")
    return False


def _validate_docx_structure(sample: bytes, stream, logger) -> bool:
    """Validate that a ZIP file contains DOCX structure.
    
    This function checks if the ZIP file contains the expected DOCX
    structure by looking for 'word/document.xml' entry.
    
    Args:
        sample: Initial bytes from the file stream
        stream: File stream (will be reset after validation)
        logger: Logger instance for recording validation steps
        
    Returns:
        True if DOCX structure is valid, False otherwise
    """
    try:
        # Create a BytesIO object from the sample for ZIP validation
        zip_data = BytesIO(sample)
        
        # Try to open as ZIP and check for DOCX structure
        with zipfile.ZipFile(zip_data) as zip_file:
            # Check if 'word/document.xml' exists in the ZIP
            if 'word/document.xml' in zip_file.namelist():
                logger.info("DOCX structure validated - found word/document.xml")
                return True
            else:
                logger.info("ZIP file does not contain DOCX structure")
                return False
                
    except zipfile.BadZipFile:
        logger.info("File is not a valid ZIP archive")
        return False
    except Exception as e:
        logger.warning(f"Error validating DOCX structure: {e}")
        return False


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