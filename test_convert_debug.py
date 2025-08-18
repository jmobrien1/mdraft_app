#!/usr/bin/env python3
"""
Debug script to test the /api/convert endpoint and identify the 500 error.
"""
import os
import sys
import tempfile
import requests
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_convert_endpoint():
    """Test the /api/convert endpoint to identify the 500 error."""
    
    # Get the base URL from environment or use default
    base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5000")
    
    print(f"Testing conversion endpoint at: {base_url}")
    
    # Create a simple test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test document for conversion debugging.")
        test_file_path = f.name
    
    try:
        # Test 1: Estimate endpoint (should work)
        print("\n1. Testing /api/estimate endpoint...")
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = requests.post(f"{base_url}/api/estimate", files=files, timeout=30)
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        # Test 2: Convert endpoint (should fail with 500)
        print("\n2. Testing /api/convert endpoint...")
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = requests.post(f"{base_url}/api/convert", files=files, timeout=30)
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}...")
        
        if response.status_code == 500:
            print("\n3. 500 Error Details:")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'unknown')}")
                print(f"   Message: {error_data.get('message', 'no message')}")
                print(f"   Request ID: {error_data.get('request_id', 'no request id')}")
            except Exception as e:
                print(f"   Could not parse error response: {e}")
                print(f"   Raw response: {response.text}")
        
    except Exception as e:
        print(f"Test failed with exception: {e}")
    
    finally:
        # Clean up test file
        try:
            os.unlink(test_file_path)
        except Exception:
            pass

if __name__ == "__main__":
    test_convert_endpoint()
