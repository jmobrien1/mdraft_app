"""
Text loading service for mdraft.

This module provides text extraction functionality for various document types,
including PDF, TXT, and MD files. It uses the Storage adapter to read files
and provides consistent text extraction across the application.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Optional

from flask import current_app

from .storage import Storage
from ..models import Job
from ..models_conversion import Conversion
from .. import db


def get_rfp_text(document_id: str) -> str:
    """
    Retrieve and extract text from an RFP document.
    
    This function uses the exact same path as the markdown endpoint:
    GET /api/conversions/<id>/markdown
    
    Args:
        document_id: The document ID (conversion ID as string)
        
    Returns:
        The extracted text content as string, or empty string on failure
    """
    logger = logging.getLogger(__name__)
    
    # Add a clear log of what path/key it tried
    current_app.logger.info("get_rfp_text: attempting fetch for document_id=%r", document_id)
    
    try:
        # Use the exact same path as the markdown endpoint
        conv = Conversion.query.get(document_id)
        if conv is None:
            current_app.logger.warning("get_rfp_text: conversion not found for document_id=%r", document_id)
            return ""
        
        # Get the markdown content (same as the endpoint)
        text = conv.markdown or ""
        
        # Apply truncation for safety
        truncate_limit = int(os.getenv("MDRAFT_TRUNCATE_CHARS", "250000"))
        if len(text) > truncate_limit:
            original_len = len(text)
            text = text[:truncate_limit]
            current_app.logger.info("get_rfp_text: truncated to %d chars (was %d)", truncate_limit, original_len)
        
        current_app.logger.info("get_rfp_text: success document_id=%r len=%d", document_id, len(text))
        return text
        
    except Exception as e:
        current_app.logger.exception("get_rfp_text: failed for document_id=%r: %s", document_id, e)
        return ""


def get_rfp_text_legacy(document_id: str) -> Optional[str]:
    """
    Legacy text loading function (kept for backward compatibility).
    
    This function loads the original file by document_id and extracts text
    based on the file type. It supports PDF (using pypdf), TXT, and MD files.
    
    Args:
        document_id: The document ID (job ID as string)
        
    Returns:
        The extracted text content as string, or None if document not found
        
    Raises:
        ValueError: If document ID format is invalid or unsupported file type
    """
    logger = logging.getLogger(__name__)
    
    # Add a clear log of what path/key it tried
    current_app.logger.info("get_rfp_text_legacy: attempting fetch for document_id=%r", document_id)
    
    try:
        job_id = int(document_id)
    except ValueError:
        raise ValueError("Invalid document ID format")
    
    # Get job from database
    job = db.session.get(Job, job_id)
    if job is None:
        return None
    
    # Try to get extracted text from output_uri first (canonical text accessor)
    if job.output_uri:
        try:
            storage = Storage()
            if storage.exists(job.output_uri):
                file_data = storage.read_bytes(job.output_uri)
                text = file_data.decode('utf-8')
                if text.strip():
                    logger.info(f"Retrieved text from output_uri for job {job_id}")
                    return text
        except Exception as e:
            logger.warning(f"Failed to read output_uri for job {job_id}: {e}")
    
    # Fallback: read original file and extract text based on file type
    if job.gcs_uri:
        try:
            storage = Storage()
            if storage.exists(job.gcs_uri):
                file_data = storage.read_bytes(job.gcs_uri)
                return _extract_text_from_bytes(file_data, job.filename, logger)
        except Exception as e:
            logger.error(f"Failed to read original file for job {job_id}: {e}")
    
    # If we get here, no text content is available
    return None


def _extract_text_from_bytes(file_data: bytes, filename: str, logger: logging.Logger) -> str:
    """
    Extract text from file bytes based on file type.
    
    Args:
        file_data: Raw file bytes
        filename: Original filename for type detection
        logger: Logger instance for recording extraction steps
        
    Returns:
        Extracted text as string
        
    Raises:
        ValueError: If file type is not supported
    """
    filename_lower = filename.lower()
    
    # Handle PDF files using pypdf
    if filename_lower.endswith('.pdf'):
        try:
            from PyPDF2 import PdfReader
            pdf_stream = io.BytesIO(file_data)
            reader = PdfReader(pdf_stream)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            logger.info(f"Successfully extracted text from PDF: {len(text)} characters")
            return text.strip()
        except ImportError:
            logger.warning("PyPDF2 not available for PDF extraction")
            raise ValueError("PDF text extraction not available (PyPDF2 not installed)")
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise ValueError("Failed to extract text from PDF file")
    
    # Handle text files (TXT, MD)
    elif filename_lower.endswith(('.txt', '.md')):
        try:
            text = file_data.decode('utf-8')
            logger.info(f"Successfully decoded text file: {len(text)} characters")
            return text
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode text file as UTF-8: {e}")
            raise ValueError("Text file encoding not supported (UTF-8 required)")
    
    # Handle other file types - return empty string and let callers 400
    else:
        logger.warning(f"Unsupported file type for text extraction: {filename}")
        return ""
