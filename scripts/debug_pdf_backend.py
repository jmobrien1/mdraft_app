#!/usr/bin/env python3
"""
Debug script to test PDF backend availability.
Run this in production to see what's happening with PDF backends.
"""
import sys
import traceback

def test_pdf_backends():
    """Test each PDF backend individually."""
    import sys
    print("=== PDF Backend Debug ===")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path[:3]}...")
    
    backends = [
        ("pdfminer.six", "from pdfminer.high_level import extract_text"),
        ("PyMuPDF", "import fitz"),
        ("pypdf", "from pypdf import PdfReader"),
    ]
    
    for backend_name, import_statement in backends:
        print(f"\n--- Testing {backend_name} ---")
        try:
            exec(import_statement)
            print(f"✅ {backend_name} import successful")
            
            # Try to get version
            if backend_name == "pdfminer.six":
                import pdfminer
                version = getattr(pdfminer, "__version__", "unknown")
                print(f"   Version: {version}")
            elif backend_name == "PyMuPDF":
                import fitz
                version = getattr(fitz, "version", ["unknown"])[0] if hasattr(fitz, "version") else getattr(fitz, "__version__", "unknown")
                print(f"   Version: {version}")
            elif backend_name == "pypdf":
                import pypdf
                version = getattr(pypdf, "__version__", "unknown")
                print(f"   Version: {version}")
                
        except ImportError as e:
            print(f"❌ {backend_name} import failed: {e}")
        except Exception as e:
            print(f"❌ {backend_name} error: {e}")
            traceback.print_exc()
    
    print("\n--- Testing PDF Backend Service ---")
    try:
        # Add the current directory to Python path to avoid conflicts
        import sys
        import os
        sys.path.insert(0, os.path.join(os.getcwd(), '..'))
        
        from app.services.pdf_backend import validate_pdf_backend
        result = validate_pdf_backend()
        print(f"PDF Backend Service Result: {result}")
    except Exception as e:
        print(f"❌ PDF Backend Service error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_backends()
