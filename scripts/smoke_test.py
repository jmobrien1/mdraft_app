#!/usr/bin/env python3
"""
Smoke test for mdraft application.

This script performs a complete end-to-end test:
1. Logs in
2. Creates a proposal
3. Uploads a small text file
4. Attaches the file to the proposal
5. Fetches requirements
6. Deletes the proposal

Prints HTTP status codes and brief JSON responses for each step.
"""

import requests
import json
import time
import os
import sys
from urllib.parse import urljoin

# Configuration
BASE_URL = os.getenv("SMOKE_TEST_URL", "http://localhost:5000")
API_BASE = urljoin(BASE_URL, "/api")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Test data
TEST_PROPOSAL_NAME = "Smoke Test Proposal"
TEST_FILE_CONTENT = "This is a test file for smoke testing.\nIt contains multiple lines.\nEnd of file."

class SmokeTest:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SmokeTest/1.0',
            'Accept': 'application/json'
        })
        self.proposal_id = None
        self.conversion_id = None
        
    def print_response(self, step, response, data=None):
        """Print formatted response information."""
        print(f"\n🔍 {step}")
        print(f"   Status: {response.status_code}")
        if data:
            print(f"   Response: {json.dumps(data, indent=2)}")
        else:
            try:
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
            except:
                print(f"   Response: {response.text[:200]}...")
        
        if response.status_code >= 400:
            print(f"   ❌ FAILED: {step}")
            return False
        else:
            print(f"   ✅ SUCCESS: {step}")
            return True

    def login(self):
        """Log in to the application."""
        print("\n🔐 Step 1: Login")
        
        # Get login page to get CSRF token
        response = self.session.get(urljoin(BASE_URL, "/auth/login"))
        if response.status_code != 200:
            return self.print_response("Get login page", response)
        
        # Extract CSRF token if present
        csrf_token = None
        if 'csrf_token' in response.text:
            # Simple extraction - in production you'd use BeautifulSoup
            import re
            match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
            if match:
                csrf_token = match.group(1)
        
        # Login
        login_data = {
            'email': ADMIN_EMAIL,
            'password': ADMIN_PASSWORD
        }
        if csrf_token:
            login_data['csrf_token'] = csrf_token
            
        response = self.session.post(
            urljoin(BASE_URL, "/auth/login"),
            data=login_data,
            allow_redirects=True
        )
        
        return self.print_response("Login", response)

    def create_proposal(self):
        """Create a new proposal."""
        print("\n📝 Step 2: Create Proposal")
        
        proposal_data = {
            'name': TEST_PROPOSAL_NAME,
            'description': 'Smoke test proposal for testing purposes'
        }
        
        response = self.session.post(
            urljoin(API_BASE, "/agents/compliance-matrix/proposals"),
            json=proposal_data
        )
        
        success = self.print_response("Create proposal", response)
        if success and response.status_code == 201:
            data = response.json()
            self.proposal_id = data.get('id')
            print(f"   Created proposal ID: {self.proposal_id}")
        
        return success

    def upload_file(self):
        """Upload a small text file."""
        print("\n📁 Step 3: Upload File")
        
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_FILE_CONTENT)
            temp_file_path = f.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('smoke_test.txt', f, 'text/plain')}
                response = self.session.post(
                    urljoin(API_BASE, "/convert"),
                    files=files
                )
            
            success = self.print_response("Upload file", response)
            if success and response.status_code == 200:
                data = response.json()
                self.conversion_id = data.get('id') or data.get('document_id')
                print(f"   Created conversion ID: {self.conversion_id}")
            
            return success
            
        finally:
            # Clean up temp file
            os.unlink(temp_file_path)

    def attach_file_to_proposal(self):
        """Attach the uploaded file to the proposal."""
        print("\n🔗 Step 4: Attach File to Proposal")
        
        if not self.proposal_id or not self.conversion_id:
            print("   ❌ FAILED: Missing proposal_id or conversion_id")
            return False
        
        attach_data = {
            'conversion_id': self.conversion_id
        }
        
        response = self.session.post(
            urljoin(API_BASE, f"/agents/compliance-matrix/proposals/{self.proposal_id}/documents"),
            json=attach_data
        )
        
        return self.print_response("Attach file to proposal", response)

    def fetch_requirements(self):
        """Fetch requirements for the proposal."""
        print("\n📋 Step 5: Fetch Requirements")
        
        if not self.proposal_id:
            print("   ❌ FAILED: Missing proposal_id")
            return False
        
        response = self.session.get(
            urljoin(API_BASE, f"/agents/compliance-matrix/proposals/{self.proposal_id}/requirements")
        )
        
        return self.print_response("Fetch requirements", response)

    def delete_proposal(self):
        """Delete the test proposal."""
        print("\n🗑️ Step 6: Delete Proposal")
        
        if not self.proposal_id:
            print("   ❌ FAILED: Missing proposal_id")
            return False
        
        response = self.session.delete(
            urljoin(API_BASE, f"/agents/compliance-matrix/proposals/{self.proposal_id}")
        )
        
        return self.print_response("Delete proposal", response)

    def test_health_endpoint(self):
        """Test the health endpoint."""
        print("\n🏥 Step 0: Health Check")
        
        response = self.session.get(urljoin(BASE_URL, "/health"))
        return self.print_response("Health check", response)

    def test_worker_ping(self):
        """Test worker connectivity if available."""
        print("\n🤖 Step 7: Worker Ping Test")
        
        try:
            response = self.session.post(
                urljoin(API_BASE, "/ops/ping"),
                json={'message': 'smoke_test'}
            )
            return self.print_response("Worker ping", response)
        except Exception as e:
            print(f"   ⚠️ Worker ping failed: {e}")
            return True  # Not critical for smoke test

    def run_all_tests(self):
        """Run the complete smoke test suite."""
        print("🧪 Starting Smoke Test")
        print("=" * 50)
        print(f"Base URL: {BASE_URL}")
        print(f"Admin Email: {ADMIN_EMAIL}")
        
        tests = [
            ("Health Check", self.test_health_endpoint),
            ("Login", self.login),
            ("Create Proposal", self.create_proposal),
            ("Upload File", self.upload_file),
            ("Attach File", self.attach_file_to_proposal),
            ("Fetch Requirements", self.fetch_requirements),
            ("Worker Ping", self.test_worker_ping),
            ("Delete Proposal", self.delete_proposal),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                success = test_func()
                results.append((test_name, success))
            except Exception as e:
                print(f"   ❌ EXCEPTION in {test_name}: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 SMOKE TEST SUMMARY")
        print("=" * 50)
        
        passed = 0
        failed = 0
        
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if success:
                passed += 1
            else:
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All tests passed! Deployment looks good.")
            return True
        else:
            print("⚠️ Some tests failed. Check the logs above.")
            return False

def main():
    """Main function to run the smoke test."""
    smoke_test = SmokeTest()
    success = smoke_test.run_all_tests()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
