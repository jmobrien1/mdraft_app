"""
Comprehensive file upload validation with content-sniffing and security checks.

This module provides robust file validation that goes beyond simple extension
checks to include magic number detection, size limits, and security validations.
"""

import os
import logging
import mimetypes
import zipfile
from typing import Optional, Tuple, Dict, Any
from io import BytesIO
from dataclasses import dataclass
from enum import Enum

import filetype


class ValidationError(Enum):
    """Enumeration of validation error types."""
    FILE_TYPE_NOT_ALLOWED = "file_type_not_allowed"
    FILE_TOO_LARGE = "file_too_large"
    DOUBLE_EXTENSION = "double_extension"
    CONTENT_MISMATCH = "content_mismatch"
    EMPTY_FILE = "empty_file"
    MALFORMED_FILE = "malformed_file"
    VIRUS_DETECTED = "virus_detected"


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    error: Optional[ValidationError] = None
    mime_type: Optional[str] = None
    file_size: int = 0
    category: Optional[str] = None
    details: Optional[str] = None


class FileValidator:
    """Comprehensive file validator with content-sniffing and security checks."""
    
    # Allowed MIME types grouped by category
    ALLOWED_MIME_TYPES = {
        "pdf": {
            "application/pdf"
        },
        "office": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
            "application/msword",  # .doc
            "application/vnd.ms-powerpoint",  # .ppt
            "application/vnd.ms-excel",  # .xls
        },
        "text": {
            "text/plain",
            "text/markdown",
            "text/csv",
            "text/rtf",
            "application/json",
            "application/xml",
            "text/xml",
        }
    }
    
    # Size limits in bytes per category - will be set from config
    SIZE_LIMITS = {}
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the file validator."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Import config and set size limits
        from ..config import get_config
        config = get_config()
        
        self.SIZE_LIMITS = {
            "pdf": config.get_file_size_limit("pdf"),
            "office": config.get_file_size_limit("office"),
            "text": config.get_file_size_limit("text"),
        }
        
        # Build reverse lookup for MIME to category
        self.mime_to_category = {}
        for category, mimes in self.ALLOWED_MIME_TYPES.items():
            for mime in mimes:
                self.mime_to_category[mime] = category
    
    # Allowed file extensions (for secondary validation)
    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".doc", ".docx",
        ".ppt", ".pptx", 
        ".xls", ".xlsx",
        ".txt", ".md", ".csv", ".rtf", ".json", ".xml"
    }
    
    # Denied extensions (security risk)
    DENIED_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".vbs", ".js",
        ".jar", ".war", ".ear", ".apk", ".dmg", ".deb", ".rpm", ".msi",
        ".sh", ".py", ".php", ".asp", ".aspx", ".jsp", ".pl", ".rb",
        ".dll", ".so", ".dylib", ".sys", ".drv", ".ocx", ".cpl",
        ".lnk", ".url", ".reg", ".inf", ".ini", ".cfg", ".conf"
    }
    
    # Magic number signatures for additional validation
    MAGIC_SIGNATURES = {
        b"%PDF": "application/pdf",
        b"PK\x03\x04": "application/zip",  # ZIP files (DOCX, PPTX, XLSX)
        b"PK\x05\x06": "application/zip",  # ZIP files (empty)
        b"PK\x07\x08": "application/zip",  # ZIP files (spanned)
    }
    

    
    def validate_file(self, 
                     stream, 
                     filename: str = "", 
                     correlation_id: Optional[str] = None) -> ValidationResult:
        """
        Comprehensive file validation with content-sniffing and security checks.
        
        Args:
            stream: File-like object supporting read() and seek()
            filename: Original filename for extension validation
            correlation_id: Optional correlation ID for logging
            
        Returns:
            ValidationResult with validation status and details
        """
        log_prefix = f"[{correlation_id}] " if correlation_id else ""
        
        try:
            # Reset stream position
            stream.seek(0)
            
            # Check for empty file
            sample = stream.read(261)  # Read enough for magic detection
            if not sample:
                self.logger.warning(f"{log_prefix}Empty file rejected")
                return ValidationResult(
                    is_valid=False,
                    error=ValidationError.EMPTY_FILE,
                    file_size=0
                )
            
            # Get file size
            stream.seek(0, os.SEEK_END)
            file_size = stream.tell()
            stream.seek(0)
            
            # Validate filename and extension
            ext_result = self._validate_filename(filename)
            if not ext_result.is_valid:
                self.logger.warning(f"{log_prefix}Filename validation failed: {ext_result.error}")
                return ext_result
            
            # Content-sniffing validation
            content_result = self._validate_content(sample, filename, file_size)
            if not content_result.is_valid:
                self.logger.warning(f"{log_prefix}Content validation failed: {content_result.error}")
                return content_result
            
            # Size validation
            if content_result.category:
                size_limit = self.SIZE_LIMITS.get(content_result.category)
                if size_limit and file_size > size_limit:
                    self.logger.warning(
                        f"{log_prefix}File too large: {file_size} bytes > {size_limit} bytes "
                        f"(category: {content_result.category})"
                    )
                    return ValidationResult(
                        is_valid=False,
                        error=ValidationError.FILE_TOO_LARGE,
                        mime_type=content_result.mime_type,
                        file_size=file_size,
                        category=content_result.category,
                        details=f"File size {file_size} exceeds limit {size_limit} ({size_limit // (1024*1024)}MB) for {content_result.category}"
                    )
            
            # Special validation for Office documents
            if content_result.mime_type == "application/zip":
                office_result = self._validate_office_structure(sample, stream)
                if not office_result.is_valid:
                    self.logger.warning(f"{log_prefix}Office document validation failed: {office_result.error}")
                    return office_result
                content_result = office_result
            
            # Antivirus scanning (if enabled)
            try:
                from ..services.antivirus import scan_file
                from ..config import get_config
                
                config = get_config()
                if config.antivirus.MODE != "off":
                    # Save to temporary file for scanning
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        stream.seek(0)
                        tmp.write(stream.read())
                        tmp_path = tmp.name
                    
                    try:
                        scan_result = scan_file(tmp_path, correlation_id)
                        
                        if scan_result.result.value == "infected":
                            self.logger.warning(
                                f"{log_prefix}Virus detected: {scan_result.virus_name}"
                            )
                            return ValidationResult(
                                is_valid=False,
                                error=ValidationError.VIRUS_DETECTED,
                                details=f"Virus detected: {scan_result.virus_name}"
                            )
                        elif scan_result.result.value == "error" and config.antivirus.AV_REQUIRED:
                            self.logger.error(
                                f"{log_prefix}Antivirus scan failed: {scan_result.error_message}"
                            )
                            return ValidationResult(
                                is_valid=False,
                                error=ValidationError.MALFORMED_FILE,
                                details=f"Antivirus scan failed: {scan_result.error_message}"
                            )
                        elif scan_result.potential_macro:
                            self.logger.info(
                                f"{log_prefix}Potential macro detected in Office document"
                            )
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                            
            except Exception as e:
                self.logger.warning(f"{log_prefix}Antivirus scan error (continuing): {e}")
            
            self.logger.info(
                f"{log_prefix}File validation passed: {filename} "
                f"({content_result.mime_type}, {file_size} bytes, {content_result.category})"
            )
            
            return ValidationResult(
                is_valid=True,
                mime_type=content_result.mime_type,
                file_size=file_size,
                category=content_result.category
            )
            
        except Exception as e:
            self.logger.exception(f"{log_prefix}File validation error: {e}")
            return ValidationResult(
                is_valid=False,
                error=ValidationError.MALFORMED_FILE,
                details=str(e)
            )
    
    def _validate_filename(self, filename: str) -> ValidationResult:
        """Validate filename for security issues."""
        if not filename:
            return ValidationResult(is_valid=True)  # No filename is OK
        
        # Check for double extensions
        parts = filename.split('.')
        if len(parts) > 2:
            # Check if any part looks like a denied extension
            for part in parts[1:]:  # Skip the first part (filename)
                if f".{part.lower()}" in self.DENIED_EXTENSIONS:
                    return ValidationResult(
                        is_valid=False,
                        error=ValidationError.DOUBLE_EXTENSION,
                        details=f"Double extension detected with denied extension: .{part}"
                    )
        
        # Check for denied extensions
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in self.DENIED_EXTENSIONS:
            return ValidationResult(
                is_valid=False,
                error=ValidationError.FILE_TYPE_NOT_ALLOWED,
                details=f"Denied extension: {file_ext}"
            )
        
        return ValidationResult(is_valid=True)
    
    def _validate_content(self, sample: bytes, filename: str, file_size: int) -> ValidationResult:
        """Validate file content using magic numbers and signatures."""
        # Primary: Use filetype library for magic detection
        kind = filetype.guess(sample)
        magic_mime = kind.mime if kind else None
        
        # Secondary: Check custom magic signatures
        custom_mime = None
        for signature, mime in self.MAGIC_SIGNATURES.items():
            if sample.startswith(signature):
                custom_mime = mime
                break
        
        # Use the most specific MIME type
        detected_mime = magic_mime or custom_mime
        
        # Get category from MIME type
        category = self.mime_to_category.get(detected_mime) if detected_mime else None
        
        # If no MIME detected, try extension-based validation
        if not detected_mime:
            # For double extensions, use the first one for validation
            if '.' in filename:
                first_ext = '.' + filename.split('.')[1].lower()
            else:
                first_ext = os.path.splitext(filename)[1].lower()
            
            if first_ext in self.ALLOWED_EXTENSIONS:
                # For allowed extensions without MIME detection, be conservative
                # Allow text files and PDF files in this case
                if first_ext in {".txt", ".md", ".csv", ".json", ".xml"}:
                    # Map specific extensions to their MIME types
                    if first_ext == ".json":
                        detected_mime = "application/json"
                    elif first_ext == ".xml":
                        detected_mime = "application/xml"
                    else:
                        detected_mime = "text/plain"
                    category = "text"
                elif first_ext == ".pdf":
                    detected_mime = "application/pdf"
                    category = "pdf"
                elif first_ext in {".docx", ".pptx", ".xlsx"}:
                    # Office documents - we'll need to validate the structure later
                    detected_mime = "application/zip"  # Office docs are ZIP files
                    category = "office"
                else:
                    return ValidationResult(
                        is_valid=False,
                        error=ValidationError.CONTENT_MISMATCH,
                        details=f"Extension {first_ext} allowed but content type not detected"
                    )
        elif not filename and detected_mime:
            # No filename but we detected a MIME type - check if it's allowed
            category = self.mime_to_category.get(detected_mime)
            if not category:
                return ValidationResult(
                    is_valid=False,
                    error=ValidationError.FILE_TYPE_NOT_ALLOWED,
                    details=f"Unsupported file type: {detected_mime}"
                )
        elif not filename and not detected_mime:
            # No filename and no MIME detection - try to detect as text if it looks like text
            try:
                # Check if content looks like text (printable ASCII/UTF-8)
                sample_str = sample.decode('utf-8', errors='ignore')
                if sample_str.isprintable() or all(ord(c) < 128 for c in sample_str):
                    detected_mime = "text/plain"
                    category = "text"
            except (UnicodeDecodeError, AttributeError):
                pass
        
        # If still no MIME detected and no filename, try text detection
        if not detected_mime and not filename:
            try:
                # Check if content looks like text (printable ASCII/UTF-8)
                sample_str = sample.decode('utf-8', errors='ignore')
                if sample_str.isprintable() or all(ord(c) < 128 for c in sample_str):
                    detected_mime = "text/plain"
                    category = "text"
            except (UnicodeDecodeError, AttributeError):
                pass
        
        # Special handling for ZIP files (Office documents)
        if detected_mime == "application/zip":
            # Check if we have a filename to determine if it's an Office document
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in {".docx", ".pptx", ".xlsx"}:
                # Likely an Office document - let the caller validate structure
                return ValidationResult(
                    is_valid=True,
                    mime_type=detected_mime,
                    category="office"  # Will be refined by Office validation
                )
            else:
                # ZIP file but not an Office document
                return ValidationResult(
                    is_valid=False,
                    error=ValidationError.CONTENT_MISMATCH,
                    details="ZIP file does not contain Office document structure"
                )
        
        if not detected_mime or not category:
            return ValidationResult(
                is_valid=False,
                error=ValidationError.FILE_TYPE_NOT_ALLOWED,
                details=f"Unsupported file type: {detected_mime or 'unknown'}"
            )
        
        return ValidationResult(
            is_valid=True,
            mime_type=detected_mime,
            category=category
        )
    
    def _validate_office_structure(self, sample: bytes, stream) -> ValidationResult:
        """Validate Office document structure for ZIP-based files."""
        try:
            # Check for Office document structure in ZIP
            zip_data = BytesIO(sample)
            
            with zipfile.ZipFile(zip_data) as zip_file:
                file_list = zip_file.namelist()
                
                # Check for DOCX structure
                if 'word/document.xml' in file_list:
                    return ValidationResult(
                        is_valid=True,
                        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        category="office"
                    )
                
                # Check for PPTX structure
                if 'ppt/presentation.xml' in file_list:
                    return ValidationResult(
                        is_valid=True,
                        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        category="office"
                    )
                
                # Check for XLSX structure
                if 'xl/workbook.xml' in file_list:
                    return ValidationResult(
                        is_valid=True,
                        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        category="office"
                    )
                
                # Generic ZIP file - not an Office document
                return ValidationResult(
                    is_valid=False,
                    error=ValidationError.CONTENT_MISMATCH,
                    details="ZIP file does not contain Office document structure"
                )
                
        except zipfile.BadZipFile:
            return ValidationResult(
                is_valid=False,
                error=ValidationError.MALFORMED_FILE,
                details="Invalid ZIP archive"
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error=ValidationError.MALFORMED_FILE,
                details=f"Error validating Office structure: {e}"
            )


# Global validator instance
_validator = None


def get_validator() -> FileValidator:
    """Get the global file validator instance."""
    global _validator
    if _validator is None:
        _validator = FileValidator()
    return _validator


def validate_upload_file(stream, 
                        filename: str = "", 
                        correlation_id: Optional[str] = None) -> ValidationResult:
    """
    Convenience function for file validation.
    
    Args:
        stream: File-like object
        filename: Original filename
        correlation_id: Optional correlation ID for logging
        
    Returns:
        ValidationResult with validation status
    """
    validator = get_validator()
    return validator.validate_file(stream, filename, correlation_id)
