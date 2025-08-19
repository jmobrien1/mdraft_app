#!/usr/bin/env python3
"""
Simple test script to verify PDF backends are working.
This avoids importing the app module to prevent conflicts.
"""
import sys

def test_pdf_backends():
    """Test each PDF backend individually."""
    print("=== PDF Backend Test ===")
    print(f"Python version: {sys.version}")
    
    backends = [
        ("pdfminer.six", "from pdfminer.high_level import extract_text"),
        ("PyMuPDF", "import fitz"),
        ("pypdf", "from pypdf import PdfReader"),
    ]
    
    working_backends = []
    
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
            
            working_backends.append(backend_name)
                
        except ImportError as e:
            print(f"❌ {backend_name} import failed: {e}")
        except Exception as e:
            print(f"❌ {backend_name} error: {e}")
    
    print(f"\n=== Summary ===")
    if working_backends:
        print(f"✅ Working backends: {', '.join(working_backends)}")
        print(f"✅ PDF processing should work!")
    else:
        print(f"❌ No PDF backends available")
        print(f"❌ PDF processing will fail")
    
    return len(working_backends) > 0

if __name__ == "__main__":
    success = test_pdf_backends()
    sys.exit(0 if success else 1)
