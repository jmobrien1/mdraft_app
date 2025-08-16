#!/usr/bin/env python3
"""
Simple test script to validate concurrent upload behavior.

This script performs concurrent uploads of the same file to test
the atomic and idempotent upload functionality.
"""

import os
import tempfile
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def create_test_file():
    """Create a test file for uploading."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("This is a test file for concurrent upload testing.\n" * 100)
        f.flush()
        return f.name

def upload_file(file_path, base_url="http://localhost:5000"):
    """Upload a file and return the response."""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'text/plain')}
            response = requests.post(f"{base_url}/api/upload", files=files)
            return {
                'status_code': response.status_code,
                'data': response.json() if response.status_code < 500 else None,
                'error': str(response.text) if response.status_code >= 500 else None
            }
    except Exception as e:
        return {
            'status_code': 0,
            'data': None,
            'error': str(e)
        }

def test_concurrent_uploads(num_uploads=5, base_url="http://localhost:5000"):
    """Test concurrent uploads of the same file."""
    print(f"Testing {num_uploads} concurrent uploads...")
    
    # Create test file
    test_file = create_test_file()
    try:
        # Perform concurrent uploads
        with ThreadPoolExecutor(max_workers=num_uploads) as executor:
            futures = [executor.submit(upload_file, test_file, base_url) for _ in range(num_uploads)]
            responses = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful_responses = [r for r in responses if r['status_code'] in [200, 202]]
        failed_responses = [r for r in responses if r['status_code'] not in [200, 202]]
        
        print(f"Successful uploads: {len(successful_responses)}")
        print(f"Failed uploads: {len(failed_responses)}")
        
        if failed_responses:
            print("Failed responses:")
            for r in failed_responses:
                print(f"  Status: {r['status_code']}, Error: {r['error']}")
        
        # Check for duplicate conversion IDs
        conversion_ids = set()
        for response in successful_responses:
            if response['data'] and 'conversion_id' in response['data']:
                conversion_ids.add(response['data']['conversion_id'])
        
        print(f"Unique conversion IDs: {len(conversion_ids)}")
        print(f"Conversion IDs: {list(conversion_ids)}")
        
        # Check response notes
        notes = []
        for response in successful_responses:
            if response['data'] and 'note' in response['data']:
                notes.append(response['data']['note'])
        
        print(f"Response notes: {notes}")
        
        # Determine if test passed
        if len(conversion_ids) == 1:
            print("✅ SUCCESS: Only one conversion was created (idempotency working)")
            return True
        else:
            print("❌ FAILURE: Multiple conversions were created (idempotency broken)")
            return False
            
    finally:
        # Clean up test file
        try:
            os.unlink(test_file)
        except:
            pass

def test_sequential_uploads(base_url="http://localhost:5000"):
    """Test sequential uploads to verify basic functionality."""
    print("Testing sequential uploads...")
    
    test_file = create_test_file()
    try:
        # First upload
        response1 = upload_file(test_file, base_url)
        print(f"First upload: {response1['status_code']}")
        if response1['data']:
            print(f"  Conversion ID: {response1['data'].get('conversion_id')}")
            print(f"  Status: {response1['data'].get('status')}")
            print(f"  Note: {response1['data'].get('note')}")
        
        # Second upload (should be duplicate)
        response2 = upload_file(test_file, base_url)
        print(f"Second upload: {response2['status_code']}")
        if response2['data']:
            print(f"  Conversion ID: {response2['data'].get('conversion_id')}")
            print(f"  Status: {response2['data'].get('status')}")
            print(f"  Note: {response2['data'].get('note')}")
        
        # Check if same conversion ID
        if (response1['data'] and response2['data'] and 
            response1['data'].get('conversion_id') == response2['data'].get('conversion_id')):
            print("✅ SUCCESS: Sequential uploads returned same conversion ID")
            return True
        else:
            print("❌ FAILURE: Sequential uploads returned different conversion IDs")
            return False
            
    finally:
        try:
            os.unlink(test_file)
        except:
            pass

if __name__ == "__main__":
    import sys
    
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    print(f"Testing upload endpoint at: {base_url}")
    print("=" * 50)
    
    # Test sequential uploads first
    sequential_success = test_sequential_uploads(base_url)
    print()
    
    # Test concurrent uploads
    concurrent_success = test_concurrent_uploads(5, base_url)
    print()
    
    # Summary
    if sequential_success and concurrent_success:
        print("🎉 ALL TESTS PASSED: Upload idempotency is working correctly!")
        sys.exit(0)
    else:
        print("💥 SOME TESTS FAILED: Upload idempotency needs attention.")
        sys.exit(1)
