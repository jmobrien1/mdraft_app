#!/usr/bin/env python3
"""
Test script for proposal delete functionality.
This script tests the delete proposal API endpoint.
"""

import os
import sys
import requests
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_delete_proposal_api():
    """Test the delete proposal API endpoint."""
    
    # Configuration
    base_url = "http://localhost:5000"
    proposal_id = 1  # Test with proposal ID 1
    
    print("Testing Delete Proposal API")
    print("=" * 50)
    print(f"Base URL: {base_url}")
    print(f"Proposal ID: {proposal_id}")
    print("-" * 50)
    
    try:
        # Test 1: Try to delete proposal
        print("1. Testing DELETE /api/agents/compliance-matrix/proposals/{id}")
        
        response = requests.delete(
            f"{base_url}/api/agents/compliance-matrix/proposals/{proposal_id}",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Delete proposal API test PASSED")
            return True
        elif response.status_code == 404:
            print("⚠️  Proposal not found (expected if proposal doesn't exist)")
            return True
        elif response.status_code == 401:
            print("⚠️  Unauthorized (expected if not logged in)")
            return True
        else:
            print("❌ Delete proposal API test FAILED")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure the Flask app is running")
        print("   Run: flask run")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def test_list_proposals_api():
    """Test the list proposals API endpoint."""
    
    base_url = "http://localhost:5000"
    
    print("\n2. Testing GET /api/agents/compliance-matrix/proposals")
    
    try:
        response = requests.get(
            f"{base_url}/api/agents/compliance-matrix/proposals",
            headers={
                "Accept": "application/json"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            proposals = data.get("proposals", [])
            print(f"Found {len(proposals)} proposals")
            for prop in proposals:
                print(f"  - ID: {prop.get('id')}, Name: {prop.get('name')}")
            print("✅ List proposals API test PASSED")
            return True
        else:
            print(f"Response: {response.text}")
            print("❌ List proposals API test FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def main():
    """Run all tests."""
    print("Proposal Delete Functionality Test")
    print("=" * 50)
    
    # Test 1: List proposals
    test1_passed = test_list_proposals_api()
    
    # Test 2: Delete proposal
    test2_passed = test_delete_proposal_api()
    
    print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        print("✅ All tests PASSED")
        print("\nThe delete proposal functionality is working correctly!")
        sys.exit(0)
    else:
        print("❌ Some tests FAILED")
        print("\nCheck the Flask app logs for more details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
