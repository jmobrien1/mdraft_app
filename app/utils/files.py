"""
File utility functions for mdraft.

This module provides utility functions for file handling, validation,
and analysis.
"""
from __future__ import annotations

import os
import hashlib
import mimetypes
import uuid
from typing import Optional, List

ALLOWED_EXTENSIONS = {
    'pdf', 'docx', 'doc', 'txt', 'rtf', 'odt', 'pages',
    'md', 'markdown', 'html', 'htm'
}

ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'text/plain',
    'text/rtf',
    'application/vnd.oasis.opendocument.text',
    'text/markdown',
    'text/html',
    'application/x-apple-diskimage'  # .pages files
}

def generate_job_id() -> str:
    """
    Generate a URL-safe unique identifier for a job.
    
    Returns:
        A URL-safe string representation of a UUID4
    """
    return uuid.uuid4().hex

def is_file_allowed(filename: str) -> bool:
    """
    Check if a file is allowed based on its extension.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if the file extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    # Extract extension
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

def is_mime_type_allowed(mime_type: str) -> bool:
    """
    Check if a MIME type is allowed.
    
    Args:
        mime_type: The MIME type to check
        
    Returns:
        True if the MIME type is allowed, False otherwise
    """
    if not mime_type:
        return False
    
    return mime_type.lower() in ALLOWED_MIME_TYPES

def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        OSError: If there's an error reading the file
    """
    return os.path.getsize(file_path)

def get_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate the hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        Hexadecimal hash string
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        OSError: If there's an error reading the file
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()

def get_file_hash_from_stream(stream, algorithm: str = 'sha256') -> str:
    """
    Calculate the hash of a file stream.
    
    Args:
        stream: File-like object to hash
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    # Reset stream position
    stream.seek(0)
    
    for chunk in iter(lambda: stream.read(4096), b""):
        hash_obj.update(chunk)
    
    # Reset stream position
    stream.seek(0)
    
    return hash_obj.hexdigest()

def guess_mime_type(filename: str) -> Optional[str]:
    """
    Guess the MIME type of a file based on its extension.
    
    Args:
        filename: The filename to analyze
        
    Returns:
        MIME type string or None if unknown
    """
    return mimetypes.guess_type(filename)[0]

def get_safe_filename(filename: str) -> str:
    """
    Get a safe filename by removing potentially dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    from werkzeug.utils import secure_filename
    return secure_filename(filename)

def validate_file_upload(request) -> dict:
    """
    Validate a file upload request.
    
    Args:
        request: Flask request object
        
    Returns:
        Dictionary with validation result:
        {
            "valid": bool,
            "error": str (if not valid),
            "file": FileStorage (if valid)
        }
    """
    # Check if file is present
    if 'file' not in request.files:
        return {"valid": False, "error": "No file part"}
    
    file = request.files['file']
    
    # Check if file was selected
    if file.filename == '':
        return {"valid": False, "error": "No selected file"}
    
    # Check if file is allowed
    if not is_file_allowed(file.filename):
        return {"valid": False, "error": "File type not allowed"}
    
    # Check file size
    try:
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size == 0:
            return {"valid": False, "error": "File is empty"}
        
        # Check against maximum size (50MB default)
        max_size = 50 * 1024 * 1024  # 50MB
        if size > max_size:
            return {"valid": False, "error": f"File too large. Maximum size: {max_size // (1024*1024)}MB"}
            
    except Exception as e:
        return {"valid": False, "error": f"Error reading file: {str(e)}"}
    
    return {"valid": True, "file": file}

def get_file_info(file_path: str) -> dict:
    """
    Get comprehensive information about a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file information
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    stat = os.stat(file_path)
    
    return {
        "path": file_path,
        "name": os.path.basename(file_path),
        "size": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": stat.st_mtime,
        "mime_type": guess_mime_type(file_path),
        "sha256": get_file_hash(file_path),
        "extension": os.path.splitext(file_path)[1].lower()
    }
