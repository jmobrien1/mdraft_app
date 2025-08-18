#!/usr/bin/env python3
"""
Debug script to test upload functionality
"""

import requests
import os

def test_upload():
    """Test the upload endpoint with detailed error reporting."""
    
    # Create a test file
    test_content = "This is a test file for debugging upload issues."
    with open("debug_test.txt", "w") as f:
        f.write(test_content)
    
    try:
        # Test the upload
        url = "http://localhost:10000/api/convert"
        files = {"file": ("debug_test.txt", open("debug_test.txt", "rb"), "text/plain")}
        
        print(f"Uploading to: {url}")
        print(f"File: debug_test.txt ({len(test_content)} bytes)")
        
        response = requests.post(url, files=files, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code != 200:
            print(f"❌ Upload failed with status {response.status_code}")
        else:
            print("✅ Upload successful!")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        # Clean up
        if os.path.exists("debug_test.txt"):
            os.remove("debug_test.txt")

if __name__ == "__main__":
    test_upload()
