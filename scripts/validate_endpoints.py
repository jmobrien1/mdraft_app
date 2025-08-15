#!/usr/bin/env python3
"""
Quick validation script to verify API endpoints are correct.

This script tests that the smoke test endpoints match the actual API structure.
"""

import requests
import json
from urllib.parse import urljoin

# Configuration
BASE_URL = "http://localhost:5000"  # Adjust as needed
API_BASE = urljoin(BASE_URL, "/api")

def test_endpoint(method, path, expected_status=401, data=None):
    """Test an API endpoint."""
    url = urljoin(API_BASE, path)
    print(f"\n🔍 Testing {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)
        else:
            print(f"   ❌ Unknown method: {method}")
            return False
        
        print(f"   Status: {response.status_code} (expected: {expected_status})")
        
        if response.status_code == expected_status:
            print(f"   ✅ PASS: {method} {path}")
            return True
        else:
            print(f"   ❌ FAIL: Expected {expected_status}, got {response.status_code}")
            try:
                print(f"   Response: {response.json()}")
            except:
                print(f"   Response: {response.text[:100]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def main():
    """Test all the endpoints used in smoke tests."""
    print("🔍 Validating API Endpoints")
    print("=" * 50)
    
    tests = [
        # Health endpoints (should work without auth)
        ("GET", "health", 200),
        ("GET", "readyz", 200),
        ("GET", "ops/health", 200),
        
        # API endpoints (should require auth - 401)
        ("GET", "agents/compliance-matrix/proposals", 401),
        ("POST", "agents/compliance-matrix/proposals", 401, {"name": "test", "description": "test"}),
        ("POST", "convert", 401),
        ("POST", "ops/ping", 401, {"message": "test"}),
        ("GET", "ops/migration_status", 401),
    ]
    
    passed = 0
    failed = 0
    
    for method, path, expected_status, *args in tests:
        data = args[0] if args else None
        if test_endpoint(method, path, expected_status, data):
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All endpoint validations passed!")
        print("✅ Smoke test endpoints are correctly configured.")
        return True
    else:
        print("⚠️ Some endpoint validations failed.")
        print("❌ Check the API endpoint configurations.")
        return False

if __name__ == "__main__":
    main()
