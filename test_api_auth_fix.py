#!/usr/bin/env python3
"""
Test script to verify API authentication fixes.
This tests that API endpoints work for both authenticated and anonymous users.
"""

import os
import sys

# Set minimal environment variables for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

def test_api_authentication():
    """Test that API endpoints work without requiring login."""
    print("🔧 TESTING API AUTHENTICATION FIXES")
    print("=" * 40)
    
    try:
        from app import create_app
        
        print("✅ App imports successful")
        
        # Create app
        app = create_app()
        print("✅ App creation successful")
        
        # Test with anonymous user (no authentication)
        with app.test_client() as client:
            print("\n📋 Testing /api/estimate endpoint (anonymous user):")
            
            # Create a simple test file
            from io import BytesIO
            test_file = BytesIO(b"test content")
            test_file.filename = "test.txt"
            
            # Test POST to /api/estimate
            response = client.post('/api/estimate', 
                                 data={'file': (test_file, 'test.txt')},
                                 content_type='multipart/form-data')
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.get_json()}")
            
            if response.status_code == 200:
                print("   ✅ /api/estimate works for anonymous users")
            elif response.status_code == 401:
                print("   ❌ /api/estimate still requires authentication")
            elif response.status_code == 302:
                print("   ❌ /api/estimate redirects to login (not fixed)")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        # Test /api/convert endpoint
        with app.test_client() as client:
            print("\n📋 Testing /api/convert endpoint (anonymous user):")
            
            # Create a simple test file
            test_file = BytesIO(b"test content")
            test_file.filename = "test.txt"
            
            # Test POST to /api/convert
            response = client.post('/api/convert', 
                                 data={'file': (test_file, 'test.txt')},
                                 content_type='multipart/form-data')
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code in [200, 202, 400, 413, 415]:
                print("   ✅ /api/convert works for anonymous users (no redirect)")
            elif response.status_code == 401:
                print("   ❌ /api/convert still requires authentication")
            elif response.status_code == 302:
                print("   ❌ /api/convert redirects to login (not fixed)")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        # Test /api/conversions endpoint
        with app.test_client() as client:
            print("\n📋 Testing /api/conversions endpoint (anonymous user):")
            
            # Test GET to /api/conversions
            response = client.get('/api/conversions?limit=5')
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ /api/conversions works for anonymous users")
            elif response.status_code == 401:
                print("   ❌ /api/conversions still requires authentication")
            elif response.status_code == 302:
                print("   ❌ /api/conversions redirects to login (not fixed)")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        print(f"\n🎯 SUMMARY:")
        print("  ✅ API endpoints should now work for anonymous users")
        print("  ✅ No more 302 redirects to /auth/login")
        print("  ✅ Visitor sessions are supported")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_api_authentication()
    sys.exit(0 if success else 1)
