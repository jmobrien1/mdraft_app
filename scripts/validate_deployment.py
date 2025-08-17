#!/usr/bin/env python3
"""
Deployment Validation Script

This script validates that the production deployment fixes are working correctly.
Run this after deploying to production to ensure everything is functioning.
"""

import requests
import sys
import time
from urllib.parse import urljoin

def test_endpoint(base_url, endpoint, expected_status=200, description=""):
    """Test a specific endpoint and return success status."""
    url = urljoin(base_url, endpoint)
    try:
        print(f"Testing {description or endpoint}...")
        response = requests.get(url, timeout=30)
        if response.status_code == expected_status:
            print(f"✅ {description or endpoint}: {response.status_code}")
            return True
        else:
            print(f"❌ {description or endpoint}: Expected {expected_status}, got {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ {description or endpoint}: Request failed - {e}")
        return False

def main():
    """Run deployment validation tests."""
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "https://mdraft.onrender.com"
    
    print(f"🔍 DEPLOYMENT VALIDATION")
    print(f"Testing: {base_url}")
    print("=" * 50)
    
    # Test endpoints
    tests = [
        ("/health/simple", 200, "Health Check"),
        ("/test", 200, "Test Route"),
        ("/debug", 200, "Debug Route"),
        ("/", 200, "Homepage"),
    ]
    
    results = []
    for endpoint, expected_status, description in tests:
        success = test_endpoint(base_url, endpoint, expected_status, description)
        results.append((description, success))
        time.sleep(1)  # Small delay between requests
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Deployment is successful.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
