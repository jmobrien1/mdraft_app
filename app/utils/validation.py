"""
Validation utilities for mdraft.

This module provides validation functions for various data types
and API inputs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from flask import request

def validate_file_upload(request) -> Dict[str, Any]:
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
    from .files import is_file_allowed
    
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
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if size == 0:
            return {"valid": False, "error": "File is empty"}
        
        # Check against maximum size (50MB default)
        max_size = 50 * 1024 * 1024  # 50MB
        if size > max_size:
            return {"valid": False, "error": f"File too large. Maximum size: {max_size // (1024*1024)}MB"}
            
    except Exception as e:
        return {"valid": False, "error": f"Error reading file: {str(e)}"}
    
    return {"valid": True, "file": file}

def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email is valid, False otherwise
    """
    if not email:
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid, False otherwise
    """
    if not url:
        return False
    
    # Basic URL regex pattern
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))

def validate_json_schema(data: Dict[str, Any], required_fields: List[str], 
                        optional_fields: List[str] = None) -> Dict[str, Any]:
    """
    Validate JSON data against a schema.
    
    Args:
        data: JSON data to validate
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Dictionary with validation result:
        {
            "valid": bool,
            "errors": List[str] (if not valid)
        }
    """
    errors = []
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
        elif data[field] is None:
            errors.append(f"Required field cannot be null: {field}")
    
    # Check for unknown fields
    if optional_fields:
        allowed_fields = set(required_fields + optional_fields)
        unknown_fields = set(data.keys()) - allowed_fields
        if unknown_fields:
            errors.append(f"Unknown fields: {', '.join(unknown_fields)}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }

def validate_integer_range(value: Any, min_val: int = None, max_val: int = None) -> bool:
    """
    Validate that a value is an integer within a specified range.
    
    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        
    Returns:
        True if value is valid, False otherwise
    """
    try:
        int_val = int(value)
    except (ValueError, TypeError):
        return False
    
    if min_val is not None and int_val < min_val:
        return False
    
    if max_val is not None and int_val > max_val:
        return False
    
    return True

def validate_string_length(value: str, min_length: int = None, max_length: int = None) -> bool:
    """
    Validate string length.
    
    Args:
        value: String to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        
    Returns:
        True if string length is valid, False otherwise
    """
    if not isinstance(value, str):
        return False
    
    length = len(value)
    
    if min_length is not None and length < min_length:
        return False
    
    if max_length is not None and length > max_length:
        return False
    
    return True

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    from werkzeug.utils import secure_filename
    return secure_filename(filename)

def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format.
    
    Args:
        api_key: API key to validate
        
    Returns:
        True if API key format is valid, False otherwise
    """
    if not api_key:
        return False
    
    # API keys should be non-empty strings
    if not isinstance(api_key, str):
        return False
    
    # Remove whitespace
    api_key = api_key.strip()
    
    # Check minimum length
    if len(api_key) < 10:
        return False
    
    return True

def validate_request_headers(request, required_headers: List[str] = None) -> Dict[str, Any]:
    """
    Validate request headers.
    
    Args:
        request: Flask request object
        required_headers: List of required header names
        
    Returns:
        Dictionary with validation result
    """
    errors = []
    
    if required_headers:
        for header in required_headers:
            if header not in request.headers:
                errors.append(f"Missing required header: {header}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
