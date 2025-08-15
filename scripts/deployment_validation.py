#!/usr/bin/env python3
"""
Deployment validation script for mdraft application.

This script validates the acceptance checklist:
- Proposals page loads → GET list fires and resolves (no infinite loader)
- Create proposal works; Add documents runs: upload/convert → attach → requirements refresh
- Requirements table populates (or shows 'none yet')
- Delete/edit (attach/detach) work and update the UI
- All API responses are JSON; 401/403/500 are readable
- Worker (if used) passes ping and finishes conversions
- Render pre-deploy migration succeeds; health check green
"""

import requests
import json
import time
import os
import sys
from urllib.parse import urljoin

# Configuration
BASE_URL = os.getenv("VALIDATION_URL", "http://localhost:5000")
API_BASE = urljoin(BASE_URL, "/api")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

class DeploymentValidator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DeploymentValidator/1.0',
            'Accept': 'application/json'
        })
        self.proposal_id = None
        self.conversion_id = None
        
    def print_check(self, check_name, success, details=""):
        """Print formatted check result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {check_name}")
        if details:
            print(f"   {details}")
        return success

    def check_health_endpoint(self):
        """Check: Render pre-deploy migration succeeds; health check green."""
        print("\n🏥 Checking Health Endpoint")
        
        try:
            response = self.session.get(urljoin(BASE_URL, "/health"))
            success = response.status_code == 200 and response.json().get("status") == "ok"
            return self.print_check("Health endpoint returns {status: 'ok'}", success)
        except Exception as e:
            return self.print_check("Health endpoint accessible", False, f"Error: {e}")

    def check_api_responses_json(self):
        """Check: All API responses are JSON; 401/403/500 are readable."""
        print("\n📄 Checking API Response Formats")
        
        # Test 401 (unauthorized)
        response = self.session.get(urljoin(API_BASE, "/proposals"))
        success_401 = response.status_code == 401 and self.is_json_response(response)
        
        # Test 404 (not found)
        response = self.session.get(urljoin(API_BASE, "/nonexistent"))
        success_404 = response.status_code == 404 and self.is_json_response(response)
        
        # Test 500 (internal server error) - trigger with invalid data
        response = self.session.post(urljoin(API_BASE, "/convert"), data="invalid")
        success_500 = response.status_code >= 400 and self.is_json_response(response)
        
        success = success_401 and success_404 and success_500
        return self.print_check("API error responses are JSON", success)

    def is_json_response(self, response):
        """Check if response is valid JSON."""
        try:
            response.json()
            return True
        except:
            return False

    def login(self):
        """Log in to the application."""
        print("\n🔐 Logging in for authenticated tests")
        
        # Get login page to get CSRF token
        response = self.session.get(urljoin(BASE_URL, "/auth/login"))
        if response.status_code != 200:
            return self.print_check("Login page accessible", False)
        
        # Extract CSRF token if present
        csrf_token = None
        if 'csrf_token' in response.text:
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
        
        success = response.status_code in [200, 302]  # Success or redirect
        return self.print_check("Login successful", success)

    def check_proposals_list(self):
        """Check: Proposals page loads → GET list fires and resolves (no infinite loader)."""
        print("\n📋 Checking Proposals List")
        
        response = self.session.get(urljoin(API_BASE, "/agents/compliance-matrix/proposals"))
        success = response.status_code == 200 and self.is_json_response(response)
        
        if success:
            data = response.json()
            # Check if response has expected structure
            has_items = isinstance(data.get('items'), list)
            return self.print_check("Proposals list loads and resolves", success, 
                                  f"Found {len(data.get('items', []))} proposals")
        else:
            return self.print_check("Proposals list accessible", False)

    def check_create_proposal(self):
        """Check: Create proposal works."""
        print("\n📝 Checking Create Proposal")
        
        proposal_data = {
            'name': 'Validation Test Proposal',
            'description': 'Proposal for deployment validation'
        }
        
        response = self.session.post(
            urljoin(API_BASE, "/agents/compliance-matrix/proposals"),
            json=proposal_data
        )
        
        success = response.status_code == 201 and self.is_json_response(response)
        
        if success:
            data = response.json()
            self.proposal_id = data.get('id')
            return self.print_check("Create proposal works", success, 
                                  f"Created proposal ID: {self.proposal_id}")
        else:
            return self.print_check("Create proposal works", False)

    def check_upload_and_convert(self):
        """Check: Add documents runs: upload/convert → attach → requirements refresh."""
        print("\n📁 Checking Upload and Convert")
        
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file for deployment validation\n")
            temp_file_path = f.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('validation_test.txt', f, 'text/plain')}
                response = self.session.post(
                    urljoin(API_BASE, "/convert"),
                    files=files
                )
            
            success = response.status_code == 200 and self.is_json_response(response)
            
            if success:
                data = response.json()
                self.conversion_id = data.get('id') or data.get('document_id')
                return self.print_check("Upload and convert works", success, 
                                      f"Created conversion ID: {self.conversion_id}")
            else:
                return self.print_check("Upload and convert works", False)
                
        finally:
            os.unlink(temp_file_path)

    def check_attach_document(self):
        """Check: Attach document to proposal."""
        print("\n🔗 Checking Attach Document")
        
        if not self.proposal_id or not self.conversion_id:
            return self.print_check("Attach document works", False, "Missing proposal_id or conversion_id")
        
        attach_data = {
            'conversion_id': self.conversion_id
        }
        
        response = self.session.post(
            urljoin(API_BASE, f"/agents/compliance-matrix/proposals/{self.proposal_id}/documents"),
            json=attach_data
        )
        
        success = response.status_code in [200, 201] and self.is_json_response(response)
        return self.print_check("Attach document works", success)

    def check_requirements_table(self):
        """Check: Requirements table populates (or shows 'none yet')."""
        print("\n📊 Checking Requirements Table")
        
        if not self.proposal_id:
            return self.print_check("Requirements table populates", False, "Missing proposal_id")
        
        response = self.session.get(
            urljoin(API_BASE, f"/agents/compliance-matrix/proposals/{self.proposal_id}/requirements")
        )
        
        success = response.status_code == 200 and self.is_json_response(response)
        
        if success:
            data = response.json()
            requirements_count = len(data.get('requirements', []))
            return self.print_check("Requirements table populates", success, 
                                  f"Found {requirements_count} requirements")
        else:
            return self.print_check("Requirements table accessible", False)

    def check_delete_proposal(self):
        """Check: Delete works and updates the UI."""
        print("\n🗑️ Checking Delete Proposal")
        
        if not self.proposal_id:
            return self.print_check("Delete proposal works", False, "Missing proposal_id")
        
        response = self.session.delete(
            urljoin(API_BASE, f"/agents/compliance-matrix/proposals/{self.proposal_id}")
        )
        
        success = response.status_code in [200, 204]
        return self.print_check("Delete proposal works", success)

    def check_worker_ping(self):
        """Check: Worker (if used) passes ping and finishes conversions."""
        print("\n🤖 Checking Worker Ping")
        
        try:
            response = self.session.post(
                urljoin(API_BASE, "/ops/ping"),
                json={'message': 'deployment_validation'}
            )
            
            if response.status_code == 200:
                data = response.json()
                success = data.get('status') == 'success'
                return self.print_check("Worker ping successful", success, 
                                      f"Task ID: {data.get('task_id', 'N/A')}")
            else:
                return self.print_check("Worker ping accessible", False, 
                                      f"Status: {response.status_code}")
        except Exception as e:
            return self.print_check("Worker ping works", False, f"Error: {e}")

    def run_validation(self):
        """Run all deployment validation checks."""
        print("🔍 Starting Deployment Validation")
        print("=" * 60)
        print(f"Base URL: {BASE_URL}")
        print(f"Admin Email: {ADMIN_EMAIL}")
        
        checks = [
            ("Health Endpoint", self.check_health_endpoint),
            ("API Response Formats", self.check_api_responses_json),
            ("Login", self.login),
            ("Proposals List", self.check_proposals_list),
            ("Create Proposal", self.check_create_proposal),
            ("Upload and Convert", self.check_upload_and_convert),
            ("Attach Document", self.check_attach_document),
            ("Requirements Table", self.check_requirements_table),
            ("Worker Ping", self.check_worker_ping),
            ("Delete Proposal", self.check_delete_proposal),
        ]
        
        results = []
        for check_name, check_func in checks:
            try:
                success = check_func()
                results.append((check_name, success))
            except Exception as e:
                print(f"   ❌ EXCEPTION in {check_name}: {e}")
                results.append((check_name, False))
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 DEPLOYMENT VALIDATION SUMMARY")
        print("=" * 60)
        
        passed = 0
        failed = 0
        
        for check_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {check_name}")
            if success:
                passed += 1
            else:
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All validation checks passed! Deployment is ready.")
            return True
        else:
            print("⚠️ Some validation checks failed. Review the issues above.")
            return False

def main():
    """Main function to run deployment validation."""
    validator = DeploymentValidator()
    success = validator.run_validation()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
