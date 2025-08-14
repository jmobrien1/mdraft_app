#!/usr/bin/env python3
"""
Test script for anonymous proposal functionality.

This script tests the anonymous proposal creation, file upload, and compliance matrix
functionality to ensure it works correctly for both anonymous and authenticated users.
"""
import requests
import json
import time
import os
from typing import Optional, Dict, Any

# Configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:5000")
TEST_FILES_DIR = "samples"


def make_request(method: str, endpoint: str, data: Optional[Dict] = None, 
                files: Optional[Dict] = None, cookies: Optional[Dict] = None) -> Dict[str, Any]:
    """Make an HTTP request and return the response."""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, cookies=cookies)
        elif method.upper() == "POST":
            if files:
                response = requests.post(url, data=data, files=files, cookies=cookies)
            else:
                response = requests.post(url, json=data, cookies=cookies)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return {
            "status_code": response.status_code,
            "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "cookies": dict(response.cookies)
        }
    except Exception as e:
        return {
            "status_code": 0,
            "error": str(e),
            "cookies": {}
        }


def test_session_bootstrap():
    """Test session bootstrap endpoint."""
    print("🔧 Testing session bootstrap...")
    
    result = make_request("GET", "/api/session/bootstrap")
    
    if result["status_code"] == 200:
        print("✅ Session bootstrap successful")
        return result["cookies"]
    else:
        print(f"❌ Session bootstrap failed: {result}")
        return {}


def test_create_proposal_anonymous(cookies: Dict):
    """Test creating a proposal as anonymous user."""
    print("📝 Testing anonymous proposal creation...")
    
    data = {
        "name": "Test Anonymous Proposal",
        "description": "A test proposal created by anonymous user"
    }
    
    result = make_request("POST", "/api/agents/compliance-matrix/proposals", data=data, cookies=cookies)
    
    if result["status_code"] == 201:
        print("✅ Anonymous proposal creation successful")
        proposal_data = result["data"]
        print(f"   Proposal ID: {proposal_data.get('id')}")
        print(f"   Is anonymous: {proposal_data.get('is_anonymous')}")
        return proposal_data.get("id")
    else:
        print(f"❌ Anonymous proposal creation failed: {result}")
        return None


def test_upload_file_anonymous(proposal_id: int, cookies: Dict):
    """Test uploading a file to anonymous proposal."""
    print("📤 Testing anonymous file upload...")
    
    # Create a simple test file
    test_file_path = os.path.join(TEST_FILES_DIR, "test_rfp.txt")
    os.makedirs(TEST_FILES_DIR, exist_ok=True)
    
    with open(test_file_path, "w") as f:
        f.write("This is a test RFP document for anonymous proposal testing.")
    
    try:
        with open(test_file_path, "rb") as f:
            files = {"file": ("test_rfp.txt", f, "text/plain")}
            data = {"document_type": "main_rfp"}
            
            result = make_request("POST", f"/api/agents/compliance-matrix/proposals/{proposal_id}/documents", 
                                data=data, files=files, cookies=cookies)
        
        if result["status_code"] == 201:
            print("✅ Anonymous file upload successful")
            return True
        else:
            print(f"❌ Anonymous file upload failed: {result}")
            return False
            
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


def test_run_compliance_matrix_anonymous(proposal_id: int, cookies: Dict):
    """Test running compliance matrix on anonymous proposal."""
    print("🔍 Testing anonymous compliance matrix...")
    
    data = {
        "proposal_id": proposal_id,
        "target_sections": ["C"],
        "force_reprocess": False
    }
    
    result = make_request("POST", "/api/agents/compliance-matrix/run", data=data, cookies=cookies)
    
    if result["status_code"] == 200:
        print("✅ Anonymous compliance matrix successful")
        matrix_data = result["data"]
        print(f"   Total requirements: {matrix_data.get('total_requirements', 0)}")
        return True
    else:
        print(f"❌ Anonymous compliance matrix failed: {result}")
        return False


def test_list_proposals_anonymous(cookies: Dict):
    """Test listing proposals as anonymous user."""
    print("📋 Testing anonymous proposal listing...")
    
    result = make_request("GET", "/api/agents/compliance-matrix/proposals", cookies=cookies)
    
    if result["status_code"] == 200:
        print("✅ Anonymous proposal listing successful")
        proposals_data = result["data"]
        proposals = proposals_data.get("proposals", [])
        print(f"   Found {len(proposals)} proposals")
        
        for prop in proposals:
            print(f"   - {prop.get('name')} (ID: {prop.get('id')}, Anonymous: {prop.get('is_anonymous')})")
        
        return True
    else:
        print(f"❌ Anonymous proposal listing failed: {result}")
        return False


def test_usage_endpoint_anonymous(cookies: Dict):
    """Test usage endpoint for anonymous user."""
    print("📊 Testing anonymous usage endpoint...")
    
    result = make_request("GET", "/api/me/usage", cookies=cookies)
    
    if result["status_code"] == 200:
        print("✅ Anonymous usage endpoint successful")
        usage_data = result["data"]
        print(f"   Plan: {usage_data.get('plan')}")
        print(f"   Authenticated: {usage_data.get('authenticated')}")
        return True
    else:
        print(f"❌ Anonymous usage endpoint failed: {result}")
        return False


def test_isolation():
    """Test that anonymous users cannot access each other's proposals."""
    print("🔒 Testing proposal isolation...")
    
    # Create two different anonymous sessions
    cookies1 = test_session_bootstrap()
    cookies2 = test_session_bootstrap()
    
    if not cookies1 or not cookies2:
        print("❌ Failed to create test sessions")
        return False
    
    # Create proposal with session 1
    proposal_id1 = test_create_proposal_anonymous(cookies1)
    if not proposal_id1:
        print("❌ Failed to create proposal for session 1")
        return False
    
    # Try to access proposal with session 2
    result = make_request("GET", f"/api/agents/compliance-matrix/proposals/{proposal_id1}/requirements", cookies=cookies2)
    
    if result["status_code"] == 404:
        print("✅ Proposal isolation working correctly")
        return True
    else:
        print(f"❌ Proposal isolation failed: {result}")
        return False


def main():
    """Run all tests."""
    print("🚀 Starting anonymous proposal tests...")
    print(f"   Base URL: {BASE_URL}")
    print()
    
    # Test session bootstrap
    cookies = test_session_bootstrap()
    if not cookies:
        print("❌ Cannot proceed without session")
        return 1
    
    print()
    
    # Test proposal creation
    proposal_id = test_create_proposal_anonymous(cookies)
    if not proposal_id:
        print("❌ Cannot proceed without proposal")
        return 1
    
    print()
    
    # Test file upload
    if not test_upload_file_anonymous(proposal_id, cookies):
        print("⚠️  File upload failed, but continuing...")
    
    print()
    
    # Test compliance matrix
    if not test_run_compliance_matrix_anonymous(proposal_id, cookies):
        print("⚠️  Compliance matrix failed, but continuing...")
    
    print()
    
    # Test proposal listing
    test_list_proposals_anonymous(cookies)
    
    print()
    
    # Test usage endpoint
    test_usage_endpoint_anonymous(cookies)
    
    print()
    
    # Test isolation
    test_isolation()
    
    print()
    print("✅ All tests completed!")
    return 0


if __name__ == "__main__":
    exit(main())
