"""
Estimate API for mdraft.

This module provides endpoints for estimating page count and cost
for document processing without actually uploading or persisting files.
"""
from __future__ import annotations

import os
import io
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import login_required
from pypdf import PdfReader
from .utils import is_file_allowed
from .utils.authz import allow_session_or_api_key


bp = Blueprint("estimate_api", __name__, url_prefix="/api")


def _get_file_extension(filename: str) -> str:
    """Extract file extension from filename.
    
    Args:
        filename: The filename to extract extension from
        
    Returns:
        The lowercase file extension without dot, or 'unknown' if no extension
    """
    if not filename or '.' not in filename:
        return "unknown"
    
    return filename.rsplit('.', 1)[1].lower()


def _count_pdf_pages(file_data: bytes) -> int:
    """Count pages in a PDF file.
    
    Args:
        file_data: The PDF file data as bytes
        
    Returns:
        Number of pages in the PDF
        
    Raises:
        Exception: If PDF cannot be read
    """
    try:
        pdf_file = io.BytesIO(file_data)
        reader = PdfReader(pdf_file)
        return len(reader.pages)
    except Exception:
        raise Exception("could not read pdf")


def _estimate_pages(file_data: bytes, filename: str) -> int:
    """Estimate the number of pages in a file.
    
    Args:
        file_data: The file data as bytes
        filename: The original filename
        
    Returns:
        Estimated number of pages
    """
    filetype = _get_file_extension(filename)
    
    if filetype == "pdf":
        try:
            return _count_pdf_pages(file_data)
        except Exception:
            # If PDF parsing fails, return 1 as fallback
            return 1
    else:
        # Non-PDF files are estimated as 1 page
        return 1


def _calculate_cost(pages: int) -> str:
    """Calculate the estimated cost for processing.
    
    Args:
        pages: Number of pages to process
        
    Returns:
        Estimated cost as a string decimal
    """
    try:
        from .config import get_config
        config = get_config()
        price_per_page = Decimal(config.billing.PRICE_PER_PAGE_USD)
        total_cost = pages * price_per_page
        # Quantize to 4 decimal places
        return str(total_cost.quantize(Decimal('0.0001')))
    except Exception:
        # Return "0.0000" if calculation fails
        return "0.0000"


@bp.route("/estimate", methods=["POST"])
@login_required
def estimate() -> Any:
    """Estimate pages and cost for a document without uploading.
    
    Returns:
        JSON response with filetype, pages, and estimated cost
    """
    if not allow_session_or_api_key():
        return jsonify({"error": "unauthorized"}), 401
    
    # Validate multipart first
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error":"file_required"}), 400
    
    # Check file size
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size == 0:
        return jsonify({"error":"file_empty"}), 400
    
    # Validate file type
    if not is_file_allowed(file.filename):
        return jsonify({"error":"file_type_not_allowed"}), 400
    
    # Read file into memory
    try:
        file_data = file.read()
    except Exception:
        return jsonify({"error": "could not read file"}), 400
    
    # Check file size against soft cap
    from .config import get_config
    config = get_config()
    max_size_bytes = config.get_file_size_limit("binary")  # Use binary limit as fallback
    if len(file_data) > max_size_bytes:
        max_mb = config.file_sizes.BINARY_MB
        return jsonify({
            "error": f"file too large",
            "detail": f"Maximum file size is {max_mb}MB"
        }), 413
    
    # Get file extension
    filetype = _get_file_extension(file.filename or "unknown")
    
    # Estimate pages
    try:
        pages = _estimate_pages(file_data, file.filename or "unknown")
    except Exception:
        # Fallback to 1 page if estimation fails
        pages = 1
    
    # Calculate cost
    est_cost_usd = _calculate_cost(pages)
    
    return jsonify({
        "filetype": filetype,
        "pages": pages,
        "est_cost_usd": est_cost_usd
    })
