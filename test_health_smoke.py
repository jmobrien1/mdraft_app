#!/usr/bin/env python3
"""
Smoke test for health endpoints.

This script tests the health check endpoints to verify they work correctly
in a real environment. Run this after starting the application.
"""
import requests
import json
import time
from typing import Dict, Any


def test_healthz(base_url: str = "http://localhost:5000") -> bool:
    """Test /healthz endpoint."""
    print("Testing /healthz endpoint...")
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/healthz", timeout=5)
        duration = time.time() - start_time
        
        print(f"  Status: {response.status_code}")
        print(f"  Duration: {duration:.3f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            print("  ✅ /healthz endpoint is healthy")
            return True
        else:
            print(f"  ❌ /healthz endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ /healthz endpoint failed: {e}")
        return False


def test_readyz(base_url: str = "http://localhost:5000") -> bool:
    """Test /readyz endpoint."""
    print("\nTesting /readyz endpoint...")
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/readyz", timeout=10)
        duration = time.time() - start_time
        
        print(f"  Status: {response.status_code}")
        print(f"  Duration: {duration:.3f}s")
        
        if response.status_code in [200, 503]:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            
            if response.status_code == 200:
                print("  ✅ /readyz endpoint reports ready")
                return True
            else:
                print("  ⚠️  /readyz endpoint reports not ready")
                if 'failed_checks' in data:
                    print(f"  Failed checks: {', '.join(data['failed_checks'])}")
                return False
        else:
            print(f"  ❌ /readyz endpoint returned unexpected status {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ /readyz endpoint failed: {e}")
        return False


def test_legacy_health(base_url: str = "http://localhost:5000") -> bool:
    """Test legacy /health endpoint."""
    print("\nTesting legacy /health endpoint...")
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/health", timeout=5)
        duration = time.time() - start_time
        
        print(f"  Status: {response.status_code}")
        print(f"  Duration: {duration:.3f}s")
        
        if response.status_code in [200, 503]:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            
            if response.status_code == 200:
                print("  ✅ Legacy /health endpoint is healthy")
                return True
            else:
                print("  ⚠️  Legacy /health endpoint reports unhealthy")
                return False
        else:
            print(f"  ❌ Legacy /health endpoint returned unexpected status {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Legacy /health endpoint failed: {e}")
        return False


def main():
    """Run all health endpoint tests."""
    print("=== Health Endpoint Smoke Test ===\n")
    
    # Test all endpoints
    healthz_ok = test_healthz()
    readyz_ok = test_readyz()
    legacy_ok = test_legacy_health()
    
    # Summary
    print("\n=== Test Summary ===")
    print(f"  /healthz: {'✅ PASS' if healthz_ok else '❌ FAIL'}")
    print(f"  /readyz:  {'✅ PASS' if readyz_ok else '❌ FAIL'}")
    print(f"  /health:  {'✅ PASS' if legacy_ok else '❌ FAIL'}")
    
    if healthz_ok and readyz_ok and legacy_ok:
        print("\n🎉 All health endpoints are working correctly!")
        return 0
    else:
        print("\n⚠️  Some health endpoints are not working correctly.")
        return 1


if __name__ == "__main__":
    import sys
    
    # Allow custom base URL
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    print(f"Testing health endpoints at: {base_url}")
    
    exit_code = main()
    sys.exit(exit_code)
