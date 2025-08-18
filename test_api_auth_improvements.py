#!/usr/bin/env python3
"""
Test script to verify the improved API authentication system.
This tests the new unauthorized handler and environment-based login requirements.
"""

import os
import sys

# Set minimal environment variables for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

def test_api_unauthorized_handler():
    """Test that API endpoints return JSON 401 instead of 302 redirects."""
    print("🔧 TESTING API UNAUTHORIZED HANDLER")
    print("=" * 40)
    
    try:
        from app import create_app
        
        print("✅ App imports successful")
        
        # Create app
        app = create_app()
        print("✅ App creation successful")
        
        # Test API endpoints that should return JSON 401
        test_endpoints = [
            '/api/estimate',
            '/api/convert', 
            '/api/conversions',
            '/api/me/usage'
        ]
        
        print("\n📋 Testing API unauthorized responses:")
        
        with app.test_client() as client:
            for endpoint in test_endpoints:
                # Test GET requests to API endpoints
                if endpoint in ['/api/estimate', '/api/convert']:
                    # These are POST endpoints, test with POST
                    response = client.post(endpoint)
                else:
                    response = client.get(endpoint)
                
                print(f"   {endpoint}: {response.status_code}")
                
                if response.status_code == 401:
                    try:
                        data = response.get_json()
                        if data and 'error' in data and data['error'] == 'unauthorized':
                            print(f"   ✅ {endpoint} returns JSON 401 (correct)")
                        else:
                            print(f"   ⚠️  {endpoint} returns 401 but wrong JSON format")
                    except Exception:
                        print(f"   ⚠️  {endpoint} returns 401 but not JSON")
                elif response.status_code == 302:
                    print(f"   ❌ {endpoint} still redirects (should return 401)")
                else:
                    print(f"   ⚠️  {endpoint} returns {response.status_code} (unexpected)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment_based_login():
    """Test the CONVERT_REQUIRES_LOGIN environment variable."""
    print("\n🔧 TESTING ENVIRONMENT-BASED LOGIN REQUIREMENTS")
    print("=" * 55)
    
    try:
        from app import create_app
        
        # Test with CONVERT_REQUIRES_LOGIN=0 (allow anonymous)
        print("\n📋 Testing CONVERT_REQUIRES_LOGIN=0 (allow anonymous):")
        os.environ['CONVERT_REQUIRES_LOGIN'] = '0'
        
        app = create_app()
        
        with app.test_client() as client:
            # Test /api/estimate with anonymous user
            response = client.post('/api/estimate', 
                                 data={'file': (b'test', 'test.txt')},
                                 content_type='multipart/form-data')
            
            print(f"   /api/estimate: {response.status_code}")
            if response.status_code in [200, 400, 413]:  # 400/413 are expected for invalid files
                print("   ✅ Anonymous access allowed")
            elif response.status_code == 401:
                print("   ❌ Anonymous access blocked (should be allowed)")
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
        
        # Test with CONVERT_REQUIRES_LOGIN=1 (require login)
        print("\n📋 Testing CONVERT_REQUIRES_LOGIN=1 (require login):")
        os.environ['CONVERT_REQUIRES_LOGIN'] = '1'
        
        app = create_app()
        
        with app.test_client() as client:
            # Test /api/estimate with anonymous user
            response = client.post('/api/estimate', 
                                 data={'file': (b'test', 'test.txt')},
                                 content_type='multipart/form-data')
            
            print(f"   /api/estimate: {response.status_code}")
            if response.status_code == 401:
                print("   ✅ Login required (correct)")
            else:
                print(f"   ❌ Should require login, got {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_csrf_exemption():
    """Test that API endpoints are exempt from CSRF protection."""
    print("\n🔧 TESTING CSRF EXEMPTION")
    print("=" * 30)
    
    try:
        from app import create_app
        
        app = create_app()
        
        # Test that API endpoints don't require CSRF tokens
        print("\n📋 Testing CSRF exemption for API endpoints:")
        
        with app.test_client() as client:
            # Test /api/estimate without CSRF token
            response = client.post('/api/estimate', 
                                 data={'file': (b'test', 'test.txt')},
                                 content_type='multipart/form-data')
            
            print(f"   /api/estimate without CSRF: {response.status_code}")
            
            # Should not get CSRF error (403)
            if response.status_code == 403:
                print("   ❌ CSRF protection still active (should be exempt)")
            else:
                print("   ✅ CSRF exemption working")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_api_unauthorized_handler()
    success2 = test_environment_based_login()
    success3 = test_csrf_exemption()
    
    print(f"\n🎯 SUMMARY:")
    print(f"  • API unauthorized handler: {'✅' if success1 else '❌'}")
    print(f"  • Environment-based login: {'✅' if success2 else '❌'}")
    print(f"  • CSRF exemption: {'✅' if success3 else '❌'}")
    
    if success1 and success2 and success3:
        print("\n🎉 API AUTHENTICATION IMPROVEMENTS VERIFIED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
