#!/usr/bin/env python3
"""
Production 500 Error Diagnostic Script

This script helps identify the source of internal server errors by:
1. Testing all major endpoints
2. Checking for specific error patterns
3. Validating configuration
4. Testing database connectivity
"""

import os
import sys
import requests
import json
from datetime import datetime

def test_endpoint(url, name, expected_status=200, method="GET"):
    """Test an endpoint and return results."""
    try:
        if method == "POST":
            # Send empty JSON for POST requests
            response = requests.post(url, json={}, timeout=10)
        else:
            response = requests.get(url, timeout=10)
        
        return {
            "name": name,
            "url": url,
            "method": method,
            "status_code": response.status_code,
            "expected": expected_status,
            "success": response.status_code == expected_status,
            "response_time": response.elapsed.total_seconds(),
            "content_length": len(response.content),
            "content_preview": response.text[:200] if response.text else "No content"
        }
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "method": method,
            "status_code": None,
            "expected": expected_status,
            "success": False,
            "error": str(e),
            "response_time": None,
            "content_length": 0,
            "content_preview": f"Error: {e}"
        }

def test_api_endpoints(base_url):
    """Test all API endpoints."""
    endpoints = [
        ("/health/simple", "Health Simple", 200, "GET"),
        ("/health", "Health Full", 200, "GET"),
        ("/", "Homepage", 200, "GET"),
        ("/api/estimate", "API Estimate", 200, "POST"),  # Changed to POST
        ("/api/convert", "API Convert", 422, "POST"),   # Changed to POST
        ("/api/agents/compliance-matrix/proposals", "API Proposals", 200, "GET"),
        ("/favicon.ico", "Favicon", 200, "GET"),
    ]
    
    results = []
    for path, name, expected, method in endpoints:
        url = f"{base_url}{path}"
        result = test_endpoint(url, name, expected, method)
        results.append(result)
        print(f"Testing {name} ({method}): {result['status_code']} (expected {expected})")
        if not result['success']:
            print(f"  Error: {result.get('error', 'Unexpected status code')}")
            print(f"  Content: {result['content_preview']}")
    
    return results

def check_environment():
    """Check environment variables and configuration."""
    env_vars = [
        "DATABASE_URL",
        "GCS_BUCKET_NAME", 
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
        "STORAGE_BACKEND",
        "FLASK_ENV",
        "SECRET_KEY"
    ]
    
    print("\n=== Environment Variables ===")
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "SECRET" in var or "CREDENTIALS" in var or "PASSWORD" in var:
                masked = value[:10] + "..." if len(value) > 10 else "***"
                print(f"{var}: {masked}")
            else:
                print(f"{var}: {value}")
        else:
            print(f"{var}: NOT SET")

def main():
    """Main diagnostic function."""
    print("=== Production 500 Error Diagnostic ===")
    print(f"Timestamp: {datetime.now()}")
    
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "https://mdraft-app.onrender.com"
    print(f"Testing base URL: {base_url}")
    
    # Check environment
    check_environment()
    
    # Test endpoints
    print(f"\n=== Endpoint Tests ===")
    results = test_api_endpoints(base_url)
    
    # Summary
    print(f"\n=== Summary ===")
    successful = sum(1 for r in results if r['success'])
    total = len(results)
    print(f"Successful: {successful}/{total}")
    
    # Show failures
    failures = [r for r in results if not r['success']]
    if failures:
        print(f"\n=== Failures ===")
        for failure in failures:
            print(f"❌ {failure['name']}: {failure['status_code']} (expected {failure['expected']})")
            if 'error' in failure:
                print(f"   Error: {failure['error']}")
            print(f"   Content: {failure['content_preview']}")
    
    # Recommendations
    print(f"\n=== Recommendations ===")
    if any(r['name'] == 'API Convert' and r['status_code'] == 503 for r in results):
        print("🔧 PDF backend missing - install pdfminer.six, PyMuPDF, or pypdf")
    
    if any(r['name'] == 'API Proposals' and r['status_code'] == 500 for r in results):
        print("🔧 Database schema issue - check ingestion_status column exists")
    
    if any(r['status_code'] == 500 for r in results):
        print("🔧 Internal server error detected - check application logs for details")
    
    return len(failures) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
