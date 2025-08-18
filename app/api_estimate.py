"""
API endpoints for document estimation and analysis.

This module provides endpoints for estimating document properties
like page count, word count, and processing time before conversion.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.utils.csrf import csrf_exempt_for_api
from app.utils.files import is_file_allowed, get_file_size
from app.utils.validation import validate_file_upload

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("estimate", __name__, url_prefix="/api")

def _get_pdf_page_count(file_path: str) -> Optional[int]:
    """Get page count from PDF file with graceful fallback."""
    try:
        import pypdf
        with open(file_path, 'rb') as file:
            reader = pypdf.PdfReader(file)
            return len(reader.pages)
    except ImportError:
        logger.debug("pypdf not available for PDF page counting")
        return None
    except Exception as e:
        logger.warning(f"Failed to get PDF page count: {e}")
        return None

def _estimate_processing_time(file_size: int, file_type: str, page_count: Optional[int] = None) -> Dict[str, Any]:
    """Estimate processing time based on file properties."""
    # Base processing time in seconds
    base_time = 5.0
    
    # Adjust for file size (rough estimate: 1MB = 2 seconds)
    size_factor = max(1.0, file_size / (1024 * 1024) * 2)
    
    # Adjust for file type complexity
    type_factors = {
        'application/pdf': 1.2,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 1.0,
        'application/msword': 1.1,
        'text/plain': 0.5,
    }
    type_factor = type_factors.get(file_type, 1.0)
    
    # Adjust for page count if available
    page_factor = 1.0
    if page_count:
        page_factor = max(1.0, page_count / 10)  # 10 pages = baseline
    
    estimated_time = base_time * size_factor * type_factor * page_factor
    
    return {
        "estimated_seconds": round(estimated_time, 1),
        "estimated_minutes": round(estimated_time / 60, 1),
        "confidence": "medium" if page_count else "low"
    }

@bp.post("/estimate")
@csrf_exempt_for_api
def estimate_document():
    """
    Estimate document properties and processing time.
    
    This endpoint analyzes uploaded files to provide estimates for:
    - Page count (for PDFs)
    - Word count (approximate)
    - Processing time
    - File size validation
    
    Returns:
        JSON with estimation results
    """
    try:
        # Validate file upload
        validation_result = validate_file_upload(request)
        if not validation_result["valid"]:
            return jsonify({"error": validation_result["error"]}), 400
        
        file = request.files["file"]
        filename = secure_filename(file.filename or "upload.bin")
        
        # Save to temporary file for analysis
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Get file properties
            file_size = get_file_size(temp_path)
            file_type = file.content_type or "application/octet-stream"
            
            # Validate file size
            max_size = current_app.config.get("MAX_FILE_SIZE", 50 * 1024 * 1024)  # 50MB default
            if file_size > max_size:
                return jsonify({
                    "error": f"File too large. Maximum size: {max_size // (1024*1024)}MB"
                }), 413
            
            # Get page count for PDFs
            page_count = None
            if file_type == "application/pdf":
                page_count = _get_pdf_page_count(temp_path)
            
            # Estimate processing time
            time_estimate = _estimate_processing_time(file_size, file_type, page_count)
            
            # Estimate word count (rough approximation)
            word_count = None
            try:
                with open(temp_path, 'rb') as f:
                    content = f.read(8192)  # Read first 8KB for estimation
                    text_content = content.decode('utf-8', errors='ignore')
                    word_count = len(text_content.split())
                    # Scale up based on file size
                    if file_size > 8192:
                        word_count = int(word_count * (file_size / 8192))
            except Exception as e:
                logger.debug(f"Could not estimate word count: {e}")
            
            result = {
                "filename": filename,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "file_type": file_type,
                "page_count": page_count,
                "estimated_word_count": word_count,
                "processing_estimate": time_estimate,
                "status": "ready_for_conversion"
            }
            
            # Add warnings if page counting failed
            if file_type == "application/pdf" and page_count is None:
                result["warnings"] = ["PDF page counting unavailable - install pypdf for accurate estimates"]
            
            return jsonify(result), 200
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {e}")
                
    except Exception as e:
        logger.exception("Error in document estimation")
        return jsonify({"error": "Estimation failed"}), 500
