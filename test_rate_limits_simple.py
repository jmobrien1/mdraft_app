#!/usr/bin/env python3
"""
Simple test script to verify rate limiting functionality.

This script tests the rate limiting system by making requests to the endpoints
and verifying that 429 responses are returned when limits are exceeded.
"""

import requests
import time
import json
from typing import Dict, Any


def test_rate_limiting(base_url: str = "http://localhost:5000") -> Dict[str, Any]:
    """
    Test rate limiting functionality on the application.
    
    Args:
        base_url: Base URL of the application to test
        
    Returns:
        Dictionary with test results
    """
    results = {
        "passed": 0,
        "failed": 0,
        "tests": []
    }
    
    def add_test(name: str, passed: bool, details: str = ""):
        """Add a test result."""
        test_result = {
            "name": name,
            "passed": passed,
            "details": details
        }
        results["tests"].append(test_result)
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    print("Testing rate limiting functionality...")
    
    # Test 1: Index endpoint rate limiting (50 per minute)
    print("\n1. Testing index endpoint rate limiting...")
    try:
        # Make 51 requests to exceed the 50 per minute limit
        responses = []
        for i in range(51):
            response = requests.get(f"{base_url}/")
            responses.append(response.status_code)
            if i % 10 == 0:
                print(f"  Made {i+1} requests...")
        
        # Check that the 51st request returns 429
        if responses[-1] == 429:
            add_test("Index endpoint rate limiting", True, 
                    f"429 returned after {len(responses)} requests")
        else:
            add_test("Index endpoint rate limiting", False, 
                    f"Expected 429, got {responses[-1]}")
            
    except Exception as e:
        add_test("Index endpoint rate limiting", False, f"Error: {str(e)}")
    
    # Test 2: Login endpoint rate limiting (10 per minute)
    print("\n2. Testing login endpoint rate limiting...")
    try:
        # Make 11 login attempts to exceed the 10 per minute limit
        responses = []
        for i in range(11):
            response = requests.post(f"{base_url}/auth/login", data={
                "email": "test@example.com",
                "password": "wrongpassword"
            })
            responses.append(response.status_code)
            if i % 5 == 0:
                print(f"  Made {i+1} login attempts...")
        
        # Check that the 11th request returns 429
        if responses[-1] == 429:
            add_test("Login endpoint rate limiting", True, 
                    f"429 returned after {len(responses)} login attempts")
        else:
            add_test("Login endpoint rate limiting", False, 
                    f"Expected 429, got {responses[-1]}")
            
    except Exception as e:
        add_test("Login endpoint rate limiting", False, f"Error: {str(e)}")
    
    # Test 3: Upload endpoint rate limiting (20 per minute)
    print("\n3. Testing upload endpoint rate limiting...")
    try:
        # Make 21 upload attempts to exceed the 20 per minute limit
        responses = []
        for i in range(21):
            response = requests.post(f"{base_url}/upload", data={
                "file": ("test content", "test.txt")
            })
            responses.append(response.status_code)
            if i % 5 == 0:
                print(f"  Made {i+1} upload attempts...")
        
        # Check that the 21st request returns 429
        if responses[-1] == 429:
            add_test("Upload endpoint rate limiting", True, 
                    f"429 returned after {len(responses)} upload attempts")
        else:
            add_test("Upload endpoint rate limiting", False, 
                    f"Expected 429, got {responses[-1]}")
            
    except Exception as e:
        add_test("Upload endpoint rate limiting", False, f"Error: {str(e)}")
    
    # Test 4: Rate limit headers
    print("\n4. Testing rate limit headers...")
    try:
        response = requests.get(f"{base_url}/")
        headers = response.headers
        
        required_headers = ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
        missing_headers = [h for h in required_headers if h not in headers]
        
        if not missing_headers:
            add_test("Rate limit headers", True, 
                    f"All required headers present: {', '.join(required_headers)}")
        else:
            add_test("Rate limit headers", False, 
                    f"Missing headers: {', '.join(missing_headers)}")
            
    except Exception as e:
        add_test("Rate limit headers", False, f"Error: {str(e)}")
    
    # Test 5: 429 response format
    print("\n5. Testing 429 response format...")
    try:
        # Make enough requests to trigger 429
        for i in range(51):
            response = requests.get(f"{base_url}/")
            if response.status_code == 429:
                break
        
        if response.status_code == 429:
            # Check response format
            try:
                data = response.json()
                if isinstance(data, dict) and ("error" in data or "message" in data):
                    add_test("429 response format", True, 
                            "429 response contains valid JSON with error/message field")
                else:
                    add_test("429 response format", False, 
                            f"429 response JSON format unexpected: {data}")
            except json.JSONDecodeError:
                add_test("429 response format", False, 
                        "429 response is not valid JSON")
        else:
            add_test("429 response format", False, 
                    f"Could not trigger 429 response (got {response.status_code})")
            
    except Exception as e:
        add_test("429 response format", False, f"Error: {str(e)}")
    
    return results


def main():
    """Main function to run the rate limiting tests."""
    import sys
    
    # Get base URL from command line argument or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    print(f"Testing rate limiting on: {base_url}")
    print("=" * 50)
    
    # Run tests
    results = test_rate_limiting(base_url)
    
    # Print results
    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)
    
    for test in results["tests"]:
        status = "✓ PASS" if test["passed"] else "✗ FAIL"
        print(f"{status}: {test['name']}")
        if test["details"]:
            print(f"    {test['details']}")
    
    print(f"\nSummary: {results['passed']} passed, {results['failed']} failed")
    
    if results["failed"] == 0:
        print("🎉 All rate limiting tests passed!")
        return 0
    else:
        print("❌ Some rate limiting tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
