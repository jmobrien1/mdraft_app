#!/usr/bin/env python3
"""
Test script to verify cookie hardening implementation.

This script tests the visitor session cookie attributes and session configuration
to ensure they meet security requirements.
"""

import os
import sys
import requests
from urllib.parse import urlparse

def test_cookie_attributes(base_url="http://localhost:5000"):
    """Test that visitor session cookies have proper security attributes."""
    
    print("Testing cookie hardening implementation...")
    print(f"Target URL: {base_url}")
    print("-" * 50)
    
    # Test 1: Check visitor session cookie creation
    print("1. Testing visitor session cookie creation...")
    try:
        response = requests.get(f"{base_url}/", allow_redirects=False)
        
        # Check if visitor session cookie is set
        visitor_cookie = response.cookies.get("visitor_session_id")
        if visitor_cookie:
            print(f"   ✓ Visitor session cookie created: {visitor_cookie[:8]}...")
            
            # Check cookie attributes
            cookie_info = response.cookies.get_dict()
            print(f"   Cookie info: {cookie_info}")
            
            # Verify security attributes
            secure = getattr(response.cookies.get("visitor_session_id"), 'secure', False)
            httponly = getattr(response.cookies.get("visitor_session_id"), 'has_nonstandard_attr', lambda x: False)('HttpOnly')
            samesite = getattr(response.cookies.get("visitor_session_id"), 'has_nonstandard_attr', lambda x: None)('SameSite')
            
            print(f"   Secure: {secure}")
            print(f"   HttpOnly: {httponly}")
            print(f"   SameSite: {samesite}")
            
            if secure and httponly and samesite == "Lax":
                print("   ✓ Cookie security attributes are properly set")
            else:
                print("   ✗ Cookie security attributes are missing or incorrect")
                return False
        else:
            print("   ✗ No visitor session cookie found")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Failed to connect to {base_url}: {e}")
        return False
    
    # Test 2: Check session configuration
    print("\n2. Testing session configuration...")
    try:
        # Try to access a protected endpoint to see session behavior
        response = requests.get(f"{base_url}/auth/login", allow_redirects=False)
        
        # Check for session cookie
        session_cookie = response.cookies.get("session")
        if session_cookie:
            print(f"   ✓ Session cookie found: {session_cookie[:8]}...")
        else:
            print("   ℹ No session cookie (this is normal for unauthenticated requests)")
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Failed to test session: {e}")
        return False
    
    print("\n3. Testing environment configuration...")
    
    # Check environment variables
    env_vars = [
        "SESSION_BACKEND",
        "REDIS_URL", 
        "VISITOR_SESSION_TTL_DAYS",
        "SECRET_KEY"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "NOT_SET")
        if var == "SECRET_KEY" and value != "NOT_SET":
            print(f"   ✓ {var}: {'*' * len(value)} (set)")
        elif var == "SECRET_KEY":
            print(f"   ⚠ {var}: NOT_SET (using default)")
        else:
            print(f"   ℹ {var}: {value}")
    
    print("\n" + "=" * 50)
    print("Cookie hardening test completed!")
    print("\nRecommendations:")
    print("- Ensure SESSION_BACKEND=redis is set for production")
    print("- Set REDIS_URL for Redis session storage")
    print("- Verify SECRET_KEY is properly set")
    print("- Test in HTTPS environment for Secure cookie validation")
    
    return True

def main():
    """Main test function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:5000"
    
    success = test_cookie_attributes(base_url)
    
    if success:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
