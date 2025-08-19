"""
PDF Backend Service for mdraft.

This module provides a unified interface for PDF text extraction with multiple
backend options and graceful fallbacks when dependencies are missing.
"""
import logging

logger = logging.getLogger(__name__)


def validate_pdf_backend():
    """Validate PDF backend availability and return status."""
    backends = [
        ("pdfminer.six", _test_pdfminer),
        ("PyMuPDF", _test_pymupdf),
        ("pypdf", _test_pypdf),
    ]
    
    for backend_name, test_func in backends:
        try:
            version = test_func()
            return {
                "available": True,
                "backend": backend_name,
                "version": version,
                "error": None,
                "recommendation": None
            }
        except Exception as e:
            logger.debug(f"{backend_name} not available: {e}")
            continue
    
    return {
        "available": False,
        "backend": None,
        "version": None,
        "error": "No PDF backend available",
        "recommendation": "Install one of: pdfminer.six, PyMuPDF, pypdf"
    }


def _test_pdfminer():
    """Test pdfminer.six availability and return version."""
    from pdfminer.high_level import extract_text
    import pdfminer
    return getattr(pdfminer, "__version__", "unknown")


def _test_pymupdf():
    """Test PyMuPDF availability and return version."""
    import fitz
    return getattr(fitz, "version", ["unknown"])[0] if hasattr(fitz, "version") else getattr(fitz, "__version__", "unknown")


def _test_pypdf():
    """Test pypdf availability and return version."""
    import pypdf
    return getattr(pypdf, "__version__", "unknown")


def extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using the best available backend."""
    # Try pdfminer.six first (best text quality)
    try:
        return _extract_with_pdfminer(path)
    except Exception as e:
        logger.debug(f"pdfminer.six extraction failed: {e}")
    
    # Try PyMuPDF second (fast and accurate)
    try:
        return _extract_with_pymupdf(path)
    except Exception as e:
        logger.debug(f"PyMuPDF extraction failed: {e}")
    
    # Try pypdf last (lightweight fallback)
    try:
        return _extract_with_pypdf(path)
    except Exception as e:
        logger.debug(f"pypdf extraction failed: {e}")
    
    # All backends failed
    raise RuntimeError("No PDF text backend available. Install pdfminer.six, PyMuPDF, or pypdf")


def _extract_with_pdfminer(path: str) -> str:
    """Extract text using pdfminer.six."""
    from pdfminer.high_level import extract_text
    return extract_text(path) or ""


def _extract_with_pymupdf(path: str) -> str:
    """Extract text using PyMuPDF."""
    import fitz
    doc = fitz.open(path)
    try:
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        return text.strip()
    finally:
        doc.close()


def _extract_with_pypdf(path: str) -> str:
    """Extract text using pypdf."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()


def get_pdf_info(path: str) -> dict:
    """Get basic information about a PDF file."""
    backend = validate_pdf_backend()
    
    if not backend["available"]:
        raise RuntimeError(backend["error"])
    
    try:
        if backend["backend"] == "pdfminer.six":
            # pdfminer doesn't provide easy page count, so we'll extract text and count lines
            text = extract_text_from_pdf(path)
            lines = text.split('\n')
            return {
                "pages": "unknown",
                "lines": len(lines),
                "backend": "pdfminer.six"
            }
        elif backend["backend"] == "PyMuPDF":
            import fitz
            doc = fitz.open(path)
            try:
                return {
                    "pages": len(doc),
                    "backend": "PyMuPDF"
                }
            finally:
                doc.close()
        elif backend["backend"] == "pypdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return {
                "pages": len(reader.pages),
                "backend": "pypdf"
            }
        else:
            raise RuntimeError(f"Unknown PDF backend: {backend['backend']}")
    except Exception as e:
        logger.exception(f"PDF info extraction failed with backend {backend['backend']}")
        raise RuntimeError(f"PDF info extraction failed: {str(e)}")
