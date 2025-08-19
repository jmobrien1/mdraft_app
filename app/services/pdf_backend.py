"""
PDF Backend Service for mdraft.

This module provides a unified interface for PDF text extraction with multiple
backend options and graceful fallbacks when dependencies are missing.
"""
import logging
from typing import Optional, List
from flask import current_app

logger = logging.getLogger(__name__)


def pick_pdf_backend() -> Optional[str]:
    """Detect available PDF backends in order of preference."""
    backends = [
        ("pypdf", _check_pypdf),
        ("pymupdf", _check_pymupdf),
        ("pdfminer", _check_pdfminer),
    ]
    
    for name, checker in backends:
        try:
            if checker():
                logger.info(f"PDF backend available: {name}")
                return name
        except Exception as e:
            logger.debug(f"PDF backend {name} not available: {e}")
    
    logger.warning("No PDF backend available")
    return None


def _check_pypdf() -> bool:
    """Check if pypdf is available."""
    try:
        from pypdf import PdfReader
        return True
    except ImportError:
        return False


def _check_pymupdf() -> bool:
    """Check if PyMuPDF is available."""
    try:
        import fitz
        return True
    except ImportError:
        return False


def _check_pdfminer() -> bool:
    """Check if pdfminer is available."""
    try:
        from pdfminer.high_level import extract_text
        return True
    except ImportError:
        return False


def extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using the best available backend."""
    backend = pick_pdf_backend()
    
    if not backend:
        raise RuntimeError("No PDF backend available")
    
    try:
        if backend == "pypdf":
            return _extract_with_pypdf(path)
        elif backend == "pymupdf":
            return _extract_with_pymupdf(path)
        elif backend == "pdfminer":
            return _extract_with_pdfminer(path)
        else:
            raise RuntimeError(f"Unknown PDF backend: {backend}")
    except Exception as e:
        logger.exception(f"PDF text extraction failed with backend {backend}")
        raise RuntimeError(f"PDF extraction failed: {str(e)}")


def _extract_with_pypdf(path: str) -> str:
    """Extract text using pypdf backend."""
    from pypdf import PdfReader
    
    reader = PdfReader(path)
    pages = []
    
    for page_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            pages.append(text)
        except Exception as e:
            logger.warning(f"Error extracting text from page {page_num}: {e}")
            pages.append("")
    
    return "\n".join(pages)


def _extract_with_pymupdf(path: str) -> str:
    """Extract text using PyMuPDF backend."""
    import fitz
    
    doc = fitz.open(path)
    pages = []
    
    for page_num in range(len(doc)):
        try:
            page = doc.load_page(page_num)
            text = page.get_text() or ""
            pages.append(text)
        except Exception as e:
            logger.warning(f"Error extracting text from page {page_num}: {e}")
            pages.append("")
    
    doc.close()
    return "\n".join(pages)


def _extract_with_pdfminer(path: str) -> str:
    """Extract text using pdfminer backend."""
    from pdfminer.high_level import extract_text
    
    text = extract_text(path) or ""
    return text


def get_pdf_info(path: str) -> dict:
    """Get basic information about a PDF file."""
    backend = pick_pdf_backend()
    
    if not backend:
        raise RuntimeError("No PDF backend available")
    
    try:
        if backend == "pypdf":
            return _get_info_with_pypdf(path)
        elif backend == "pymupdf":
            return _get_info_with_pymupdf(path)
        elif backend == "pdfminer":
            return _get_info_with_pdfminer(path)
        else:
            raise RuntimeError(f"Unknown PDF backend: {backend}")
    except Exception as e:
        logger.exception(f"PDF info extraction failed with backend {backend}")
        raise RuntimeError(f"PDF info extraction failed: {str(e)}")


def _get_info_with_pypdf(path: str) -> dict:
    """Get PDF info using pypdf backend."""
    from pypdf import PdfReader
    
    reader = PdfReader(path)
    return {
        "pages": len(reader.pages),
        "backend": "pypdf"
    }


def _get_info_with_pymupdf(path: str) -> dict:
    """Get PDF info using PyMuPDF backend."""
    import fitz
    
    doc = fitz.open(path)
    info = {
        "pages": len(doc),
        "backend": "pymupdf"
    }
    doc.close()
    return info


def _get_info_with_pdfminer(path: str) -> dict:
    """Get PDF info using pdfminer backend."""
    # pdfminer doesn't provide easy page count, so we'll extract text and count lines
    text = _extract_with_pdfminer(path)
    lines = text.split('\n')
    
    return {
        "pages": "unknown",  # pdfminer doesn't provide page count easily
        "lines": len(lines),
        "backend": "pdfminer"
    }


def validate_pdf_backend() -> dict:
    """Validate PDF backend availability and return status."""
    backend = pick_pdf_backend()
    
    if not backend:
        return {
            "available": False,
            "backend": None,
            "error": "No PDF backend available",
            "recommendation": "Install pypdf: pip install pypdf"
        }
    
    return {
        "available": True,
        "backend": backend,
        "error": None,
        "recommendation": None
    }
