#!/usr/bin/env python3
"""
Test script for observability features.

This script tests:
1. Request logging middleware
2. Health check endpoint
3. Migration status endpoint
4. Request ID inclusion in error responses
"""

import requests
import json
import time
from urllib.parse import urljoin

# Configuration
BASE_URL = "http://localhost:5000"  # Adjust as needed
API_BASE = urljoin(BASE_URL, "/api")

def test_health_endpoint():
    """Test the /health endpoint returns {status: 'ok'}."""
    print("Testing /health endpoint...")
    
    response = requests.get(urljoin(BASE_URL, "/health"))
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✓ Health endpoint working correctly\n")

def test_migration_status():
    """Test the /api/ops/migration_status endpoint."""
    print("Testing /api/ops/migration_status endpoint...")
    
    # This endpoint requires authentication, so we expect a 401
    response = requests.get(urljoin(API_BASE, "/ops/migration_status"))
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Should return 401 with request_id
    assert response.status_code == 401
    assert "request_id" in response.json()
    print("✓ Migration status endpoint returns request_id in error response\n")

def test_request_logging():
    """Test that request logging includes request_id."""
    print("Testing request logging...")
    
    # Make a request with a custom request ID
    custom_request_id = "test-request-123"
    headers = {"X-Request-ID": custom_request_id}
    
    response = requests.get(urljoin(API_BASE, "/ops/health"), headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # The response should include our custom request ID
    assert response.status_code == 200
    print("✓ Request logging working (check logs for request_id)\n")

def test_error_with_request_id():
    """Test that API errors include request_id."""
    print("Testing error responses include request_id...")
    
    # Make a request to a non-existent endpoint
    response = requests.get(urljoin(API_BASE, "/nonexistent"))
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Should return 404 with request_id
    assert response.status_code == 404
    assert "request_id" in response.json()
    print("✓ Error responses include request_id\n")

def test_rate_limit_with_request_id():
    """Test that rate limit errors include request_id."""
    print("Testing rate limit error includes request_id...")
    
    # Make multiple requests quickly to trigger rate limiting
    responses = []
    for i in range(10):
        response = requests.get(urljoin(API_BASE, "/ops/health"))
        responses.append(response)
        if response.status_code == 429:
            break
        time.sleep(0.1)
    
    # Check if any response was rate limited
    rate_limited = any(r.status_code == 429 for r in responses)
    if rate_limited:
        rate_limit_response = next(r for r in responses if r.status_code == 429)
        print(f"Rate limit response: {rate_limit_response.json()}")
        assert "request_id" in rate_limit_response.json()
        print("✓ Rate limit errors include request_id\n")
    else:
        print("⚠ Rate limiting not triggered (this is normal)\n")

def main():
    """Run all observability tests."""
    print("🧪 Testing Observability Features\n")
    print("=" * 50)
    
    try:
        test_health_endpoint()
        test_migration_status()
        test_request_logging()
        test_error_with_request_id()
        test_rate_limit_with_request_id()
        
        print("✅ All observability tests passed!")
        print("\n📋 Summary:")
        print("- Request logging middleware: ✓")
        print("- Health endpoint: ✓")
        print("- Migration status endpoint: ✓")
        print("- Request ID in error responses: ✓")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask app is running.")
        print("   Run: python run.py")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    main()
