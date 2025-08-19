"""
PDF Backend Service for mdraft.

This module provides a unified interface for PDF text extraction with multiple
backend options and graceful fallbacks when dependencies are missing.
"""
import logging

logger = logging.getLogger(__name__)


def validate_pdf_backend():
    """Validate PDF backend availability and return status."""
    try:
        import pypdf  # noqa: F401
        return {
            "available": True,
            "backend": "pypdf",
            "error": None,
            "recommendation": None
        }
    except Exception:
        try:
            import fitz  # PyMuPDF  # noqa: F401
            return {
                "available": True,
                "backend": "pymupdf",
                "error": None,
                "recommendation": None
            }
        except Exception:
            try:
                from pdfminer.high_level import extract_text  # noqa: F401
                return {
                    "available": True,
                    "backend": "pdfminer",
                    "error": None,
                    "recommendation": None
                }
            except Exception:
                return {
                    "available": False,
                    "backend": None,
                    "error": "No PDF backend available",
                    "recommendation": "Install one of: pypdf, PyMuPDF, pdfminer.six"
                }


def extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using the best available backend."""
    backend = validate_pdf_backend()
    
    if not backend["available"]:
        raise RuntimeError("No PDF backend available")
    
    try:
        if backend["backend"] == "pypdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        elif backend["backend"] == "pymupdf":
            import fitz
            doc = fitz.open(path)
            text = "\n".join(page.get_text() or "" for page in doc)
            doc.close()
            return text
        elif backend["backend"] == "pdfminer":
            from pdfminer.high_level import extract_text
            return extract_text(path) or ""
        else:
            raise RuntimeError(f"Unknown PDF backend: {backend['backend']}")
    except Exception as e:
        logger.exception(f"PDF text extraction failed with backend {backend['backend']}")
        raise RuntimeError(f"PDF extraction failed: {str(e)}")


def get_pdf_info(path: str) -> dict:
    """Get basic information about a PDF file."""
    backend = validate_pdf_backend()
    
    if not backend["available"]:
        raise RuntimeError("No PDF backend available")
    
    try:
        if backend["backend"] == "pypdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return {
                "pages": len(reader.pages),
                "backend": "pypdf"
            }
        elif backend["backend"] == "pymupdf":
            import fitz
            doc = fitz.open(path)
            info = {
                "pages": len(doc),
                "backend": "pymupdf"
            }
            doc.close()
            return info
        elif backend["backend"] == "pdfminer":
            # pdfminer doesn't provide easy page count, so we'll extract text and count lines
            text = extract_text_from_pdf(path)
            lines = text.split('\n')
            
            return {
                "pages": "unknown",  # pdfminer doesn't provide page count easily
                "lines": len(lines),
                "backend": "pdfminer"
            }
        else:
            raise RuntimeError(f"Unknown PDF backend: {backend['backend']}")
    except Exception as e:
        logger.exception(f"PDF info extraction failed with backend {backend['backend']}")
        raise RuntimeError(f"PDF info extraction failed: {str(e)}")
