#!/usr/bin/env python3
"""
Test script to verify mdraft application setup.

This script tests the basic functionality of the mdraft application
including database connectivity, file upload simulation, and job processing.
"""
import os
import sys
import tempfile
import requests
import time
from pathlib import Path

def test_database_connection():
    """Test database connectivity."""
    print("Testing database connection...")
    try:
        from app import create_app, db
        app = create_app()
        with app.app_context():
            db.session.execute("SELECT 1")
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_file_validation():
    """Test file type validation."""
    print("Testing file validation...")
    try:
        from app.utils import is_file_allowed
        from io import BytesIO
        
        # Test PDF file
        if is_file_allowed("test.pdf"):
            print("✅ PDF file validation working")
        else:
            print("❌ PDF file validation failed")
            return False
            
        # Test invalid file
        if not is_file_allowed("test.invalid"):
            print("✅ Invalid file rejection working")
        else:
            print("❌ Invalid file rejection failed")
            return False
            
        return True
    except Exception as e:
        print(f"❌ File validation test failed: {e}")
        return False

def test_app_startup():
    """Test that the Flask app can start without errors."""
    print("Testing Flask app startup...")
    try:
        from app import create_app
        app = create_app()
        print("✅ Flask app created successfully")
        return True
    except Exception as e:
        print(f"❌ Flask app creation failed: {e}")
        return False

def test_api_endpoints():
    """Test basic API endpoints."""
    print("Testing API endpoints...")
    try:
        from app import create_app
        app = create_app()
        
        with app.test_client() as client:
            # Test root endpoint
            response = client.get('/')
            if response.status_code == 200:
                print("✅ Root endpoint working")
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return False
            
            # Test health endpoint
            response = client.get('/health')
            if response.status_code == 200:
                print("✅ Health endpoint working")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
                return False
                
        return True
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        return False

def test_environment_variables():
    """Test that required environment variables are set."""
    print("Testing environment variables...")
    
    required_vars = ['SECRET_KEY']
    optional_vars = ['GCS_BUCKET_NAME', 'DOCAI_PROCESSOR_ID', 'CLOUD_TASKS_QUEUE_ID']
    
    missing_required = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_required.append(var)
    
    if missing_required:
        print(f"❌ Missing required environment variables: {missing_required}")
        return False
    
    print("✅ Required environment variables set")
    
    # Check optional variables
    missing_optional = []
    for var in optional_vars:
        if not os.environ.get(var):
            missing_optional.append(var)
    
    if missing_optional:
        print(f"⚠️  Missing optional environment variables (Google Cloud features disabled): {missing_optional}")
    else:
        print("✅ All Google Cloud environment variables set")
    
    return True

def test_directory_structure():
    """Test that required directories exist."""
    print("Testing directory structure...")
    
    base_dir = Path(__file__).parent
    required_dirs = ['uploads', 'processed']
    
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            print(f"✅ Directory {dir_name} exists")
        else:
            print(f"❌ Directory {dir_name} missing")
            return False
    
    return True

def main():
    """Run all tests."""
    print("🧪 Running mdraft setup tests...\n")
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Directory Structure", test_directory_structure),
        ("Database Connection", test_database_connection),
        ("File Validation", test_file_validation),
        ("Flask App Startup", test_app_startup),
        ("API Endpoints", test_api_endpoints),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your mdraft setup is ready.")
        print("\nNext steps:")
        print("1. Run 'flask db upgrade' to create database tables")
        print("2. Run 'python run.py' to start the application")
        print("3. Visit http://localhost:5000 to test the API")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
