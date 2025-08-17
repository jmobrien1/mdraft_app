#!/usr/bin/env python3
"""
Health check script for mdraft application.

This script tests the application endpoints to verify they're working correctly.
"""
import os
import sys
import requests
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_health_endpoints(base_url):
    """Test health endpoints."""
    print("=== Health Endpoint Tests ===")
    
    health_endpoints = [
        "/health",
        "/health/simple", 
        "/healthz",
    ]
    
    for endpoint in health_endpoints:
        url = f"{base_url}{endpoint}"
        try:
            print(f"Testing {endpoint}...")
            response = requests.get(url, timeout=10)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}...")
            
            if response.status_code == 200:
                print(f"  ✅ {endpoint} - OK")
            else:
                print(f"  ❌ {endpoint} - Failed (status {response.status_code})")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ {endpoint} - Request failed: {e}")
        except Exception as e:
            print(f"  ❌ {endpoint} - Error: {e}")
    
    print()

def test_homepage(base_url):
    """Test homepage endpoint."""
    print("=== Homepage Test ===")
    
    try:
        print("Testing homepage...")
        response = requests.get(base_url, timeout=10)
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        print(f"  Content-Length: {len(response.content)}")
        
        if response.status_code == 200:
            print(f"  ✅ Homepage - OK")
            if "text/html" in response.headers.get('Content-Type', ''):
                print(f"  ✅ Homepage returns HTML")
            else:
                print(f"  ⚠️  Homepage doesn't return HTML")
        else:
            print(f"  ❌ Homepage - Failed (status {response.status_code})")
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Homepage - Request failed: {e}")
    except Exception as e:
        print(f"  ❌ Homepage - Error: {e}")
    
    print()

def test_home_endpoint(base_url):
    """Test /home endpoint."""
    print("=== /home Endpoint Test ===")
    
    try:
        print("Testing /home endpoint...")
        response = requests.get(f"{base_url}/home", timeout=10)
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200:
            print(f"  ✅ /home - OK")
            if "application/json" in response.headers.get('Content-Type', ''):
                print(f"  ✅ /home returns JSON")
                try:
                    data = response.json()
                    print(f"  Response: {data}")
                except:
                    print(f"  ⚠️  /home response is not valid JSON")
            else:
                print(f"  ⚠️  /home doesn't return JSON")
        else:
            print(f"  ❌ /home - Failed (status {response.status_code})")
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ /home - Request failed: {e}")
    except Exception as e:
        print(f"  ❌ /home - Error: {e}")
    
    print()

def test_error_handling(base_url):
    """Test error handling."""
    print("=== Error Handling Tests ===")
    
    # Test 404
    try:
        print("Testing 404 handling...")
        response = requests.get(f"{base_url}/nonexistent", timeout=10)
        print(f"  404 Status: {response.status_code}")
        if response.status_code == 404:
            print(f"  ✅ 404 handling - OK")
        else:
            print(f"  ⚠️  404 handling - Unexpected status {response.status_code}")
    except Exception as e:
        print(f"  ❌ 404 test failed: {e}")
    
    print()

def main():
    """Run health checks."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/health_check.py <base_url>")
        print("Example: python scripts/health_check.py https://mdraft.onrender.com")
        return 1
    
    base_url = sys.argv[1].rstrip('/')
    print(f"🚀 Testing application at: {base_url}")
    print()
    
    # Test endpoints
    test_health_endpoints(base_url)
    test_homepage(base_url)
    test_home_endpoint(base_url)
    test_error_handling(base_url)
    
    print("🎉 Health check completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
