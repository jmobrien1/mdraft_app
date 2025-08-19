#!/usr/bin/env python3
"""
Comprehensive deployment validation script for mdraft.

This script validates that all the critical fixes have been applied:
1. PDF backend availability
2. Database schema completeness
3. API endpoint functionality
4. GCS import correctness

Usage:
    python scripts/validate_deployment_fixes.py
"""

import os
import sys
import tempfile
import requests
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_pdf_backend():
    """Test PDF backend availability and functionality."""
    print("🔍 Testing PDF backend...")
    
    try:
        from app.services.pdf_backend import validate_pdf_backend, extract_text_from_pdf
        
        # Test backend validation
        backend = validate_pdf_backend()
        if not backend["available"]:
            print(f"❌ PDF backend not available: {backend['error']}")
            return False
        
        print(f"✅ PDF backend available: {backend['backend']}")
        
        # Test text extraction with a simple PDF
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            # Create test PDF
            fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            os.close(fd)
            
            c = canvas.Canvas(temp_path, pagesize=letter)
            c.drawString(100, 750, 'Test PDF for mdraft validation')
            c.drawString(100, 700, 'This is a test document for validation.')
            c.drawString(100, 650, 'If you can read this, PDF extraction is working.')
            c.save()
            
            # Test extraction
            text = extract_text_from_pdf(temp_path)
            if 'Test PDF for mdraft validation' in text:
                print("✅ PDF text extraction working correctly")
                os.unlink(temp_path)
                return True
            else:
                print(f"⚠️  PDF text extraction may have issues. Extracted: {text[:100]}...")
                os.unlink(temp_path)
                return False
                
        except Exception as e:
            print(f"❌ PDF text extraction test failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ PDF backend test failed: {e}")
        return False


def test_database_schema():
    """Test database schema completeness."""
    print("🔍 Testing database schema...")
    
    try:
        from sqlalchemy import create_engine, text
        
        # Get database URL
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("⚠️  DATABASE_URL not set, skipping database test")
            return True
        
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check for required columns in proposal_documents
            required_columns = [
                'ingestion_status',
                'available_sections', 
                'ingestion_error',
                'section_mapping'
            ]
            
            for column in required_columns:
                result = conn.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'proposal_documents' 
                    AND column_name = '{column}'
                """))
                
                if result.fetchone():
                    print(f"✅ {column} column exists")
                else:
                    print(f"❌ {column} column missing")
                    return False
            
            # Check for index
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'proposal_documents' 
                AND indexname = 'ix_proposal_documents_ingestion_status'
            """))
            
            if result.fetchone():
                print("✅ ingestion_status index exists")
            else:
                print("⚠️  ingestion_status index missing (performance may be affected)")
            
            return True
            
    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        return False


def test_api_endpoints():
    """Test critical API endpoints."""
    print("🔍 Testing API endpoints...")
    
    base_url = os.environ.get('TEST_BASE_URL', 'http://localhost:5000')
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print(f"❌ Health endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False
    
    # Test convert endpoint (should not return 503)
    try:
        response = requests.get(f"{base_url}/api/convert", timeout=10)
        if response.status_code == 503:
            print("❌ Convert endpoint still returning 503 - PDF backend issue")
            return False
        elif response.status_code in [200, 404, 405]:  # Acceptable responses
            print("✅ Convert endpoint responding (not 503)")
        else:
            print(f"⚠️  Convert endpoint returned {response.status_code}")
    except Exception as e:
        print(f"⚠️  Convert endpoint test failed: {e}")
    
    return True


def test_gcs_imports():
    """Test GCS import correctness."""
    print("🔍 Testing GCS imports...")
    
    try:
        from google.cloud import storage
        print("✅ google.cloud.storage import working correctly")
        return True
    except ImportError as e:
        print(f"❌ google.cloud.storage import failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️  GCS import test failed: {e}")
        return False


def test_dependency_versions():
    """Test critical dependency versions."""
    print("🔍 Testing dependency versions...")
    
    dependencies = [
        ('pdfminer.six', '20231228'),
    ]
    
    all_good = True
    for package, expected_version in dependencies:
        try:
            if package == 'pdfminer.six':
                import pdfminer
                version = getattr(pdfminer, '__version__', 'unknown')
            
            if version == expected_version:
                print(f"✅ {package} version {version}")
            else:
                print(f"⚠️  {package} version {version} (expected {expected_version})")
                all_good = False
                
        except ImportError:
            print(f"❌ {package} not available")
            all_good = False
    
    return all_good


def main():
    """Run all validation tests."""
    print("🚀 Starting comprehensive deployment validation...")
    print("=" * 60)
    
    tests = [
        ("PDF Backend", test_pdf_backend),
        ("Database Schema", test_database_schema),
        ("API Endpoints", test_api_endpoints),
        ("GCS Imports", test_gcs_imports),
        ("Dependency Versions", test_dependency_versions),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests passed! Deployment is ready.")
        return 0
    else:
        print("⚠️  Some validation tests failed. Please review the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
