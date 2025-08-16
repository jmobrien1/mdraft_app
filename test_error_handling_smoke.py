#!/usr/bin/env python3
"""
Smoke test for unified error handling system.

This script tests the error handling in the actual application
to ensure it works correctly in production.
"""
import json
import requests
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_error_handling(base_url="http://localhost:5000"):
    """Test error handling endpoints."""
    print(f"Testing error handling at {base_url}")
    print("=" * 50)
    
    # Test cases: (endpoint, expected_status, expected_error)
    test_cases = [
        ("/api/nonexistent", 404, "not_found"),
        ("/api/test", 404, "not_found"),
        ("/api/", 404, "not_found"),
    ]
    
    all_passed = True
    
    for endpoint, expected_status, expected_error in test_cases:
        url = f"{base_url}{endpoint}"
        print(f"\nTesting {endpoint}...")
        
        try:
            response = requests.get(url, timeout=10)
            
            # Check status code
            if response.status_code != expected_status:
                print(f"  ❌ Expected status {expected_status}, got {response.status_code}")
                all_passed = False
                continue
            
            # Check content type
            if not response.headers.get('content-type', '').startswith('application/json'):
                print(f"  ❌ Expected JSON response, got {response.headers.get('content-type')}")
                all_passed = False
                continue
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                print(f"  ❌ Invalid JSON response: {response.text[:100]}")
                all_passed = False
                continue
            
            # Check response structure
            required_fields = ['error', 'detail', 'request_id']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"  ❌ Missing required fields: {missing_fields}")
                print(f"  Response: {data}")
                all_passed = False
                continue
            
            # Check error code
            if data['error'] != expected_error:
                print(f"  ❌ Expected error '{expected_error}', got '{data['error']}'")
                all_passed = False
                continue
            
            # Check request ID
            if data['request_id'] == 'unknown':
                print(f"  ⚠️  Request ID is 'unknown' (may be expected in some cases)")
            
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Error: {data['error']}")
            print(f"  ✅ Request ID: {data['request_id']}")
            print(f"  ✅ Detail: {data['detail'][:50]}...")
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Request failed: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All error handling tests passed!")
        return True
    else:
        print("❌ Some error handling tests failed!")
        return False

if __name__ == "__main__":
    # Allow custom base URL via command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    success = test_error_handling(base_url)
    sys.exit(0 if success else 1)
