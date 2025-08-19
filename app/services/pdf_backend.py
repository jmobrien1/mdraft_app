"""
PDF Backend Service for mdraft.

This module provides a unified interface for PDF text extraction using pdfminer.six.
"""
import logging

logger = logging.getLogger(__name__)


def validate_pdf_backend():
    """Validate PDF backend availability and return status."""
    try:
        from pdfminer.high_level import extract_text  # noqa: F401
        return {
            "available": True,
            "backend": "pdfminer",
            "error": None,
            "recommendation": None
        }
    except Exception as e:
        return {
            "available": False,
            "backend": None,
            "error": f"pdfminer.six not available: {str(e)}",
            "recommendation": "Install pdfminer.six: pip install pdfminer.six==20231228"
        }


def extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using pdfminer.six."""
    backend = validate_pdf_backend()
    
    if not backend["available"]:
        raise RuntimeError(backend["error"])
    
    try:
        from pdfminer.high_level import extract_text
        return extract_text(path) or ""
    except Exception as e:
        logger.exception(f"PDF text extraction failed with pdfminer.six")
        raise RuntimeError(f"PDF extraction failed: {str(e)}")


def get_pdf_info(path: str) -> dict:
    """Get basic information about a PDF file."""
    backend = validate_pdf_backend()
    
    if not backend["available"]:
        raise RuntimeError(backend["error"])
    
    try:
        # pdfminer doesn't provide easy page count, so we'll extract text and count lines
        text = extract_text_from_pdf(path)
        lines = text.split('\n')
        
        return {
            "pages": "unknown",  # pdfminer doesn't provide page count easily
            "lines": len(lines),
            "backend": "pdfminer"
        }
    except Exception as e:
        logger.exception(f"PDF info extraction failed with pdfminer.six")
        raise RuntimeError(f"PDF info extraction failed: {str(e)}")
