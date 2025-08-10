#!/usr/bin/env python3
"""
End-to-end validation script for mdraft application.

This script tests the complete workflow:
1. Upload a test document
2. Check job status
3. Wait for processing
4. Download the result
"""
import os
import sys
import time
import tempfile
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def create_test_pdf():
    """Create a simple test PDF file."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        # Create a temporary PDF file
        fd, temp_path = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        
        # Create a simple PDF
        c = canvas.Canvas(temp_path, pagesize=letter)
        c.drawString(100, 750, "Test Document for mdraft")
        c.drawString(100, 700, "This is a test PDF file created for validation.")
        c.drawString(100, 650, "It should be converted to Markdown format.")
        c.save()
        
        return temp_path
    except ImportError:
        print("⚠️  reportlab not available, creating text file instead")
        # Fallback to text file
        fd, temp_path = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        
        with open(temp_path, 'w') as f:
            f.write("Test Document for mdraft\n")
            f.write("This is a test file created for validation.\n")
            f.write("It should be converted to Markdown format.\n")
        
        return temp_path

def test_health_check(base_url):
    """Test the health check endpoint."""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_upload(base_url, file_path):
    """Test file upload."""
    print(f"📤 Testing file upload: {os.path.basename(file_path)}")
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{base_url}/upload", files=files, timeout=30)
        
        if response.status_code == 202:
            data = response.json()
            job_id = data.get('job_id')
            status = data.get('status')
            print(f"✅ Upload successful - Job ID: {job_id}, Status: {status}")
            return job_id
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def test_job_status(base_url, job_id, max_wait=60):
    """Test job status checking and wait for completion."""
    print(f"⏳ Monitoring job {job_id}...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{base_url}/jobs/{job_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                print(f"📊 Job status: {status}")
                
                if status == 'completed':
                    download_url = data.get('download_url')
                    if download_url:
                        print(f"✅ Job completed! Download URL: {download_url}")
                        return download_url
                    else:
                        print("⚠️  Job completed but no download URL")
                        return None
                elif status == 'failed':
                    print("❌ Job failed")
                    return None
                elif status in ['queued', 'processing']:
                    print("⏳ Job still processing...")
                    time.sleep(2)
                    continue
                else:
                    print(f"⚠️  Unknown status: {status}")
                    return None
            else:
                print(f"❌ Status check failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Status check error: {e}")
            return None
    
    print("⏰ Timeout waiting for job completion")
    return None

def test_download(base_url, download_url):
    """Test file download."""
    print(f"📥 Testing download: {download_url}")
    try:
        if download_url.startswith('http'):
            # GCS signed URL
            response = requests.get(download_url, timeout=30)
        else:
            # Local URL
            response = requests.get(f"{base_url}{download_url}", timeout=30)
        
        if response.status_code == 200:
            content = response.text
            print(f"✅ Download successful - {len(content)} characters")
            print(f"📄 Content preview: {content[:200]}...")
            return True
        else:
            print(f"❌ Download failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def main():
    """Run the complete validation test."""
    print("🧪 Starting mdraft E2E validation...")
    
    # Configuration
    base_url = "http://localhost:5000"
    
    # Test health check
    if not test_health_check(base_url):
        print("❌ Health check failed, stopping validation")
        return False
    
    # Create test file
    test_file = create_test_pdf()
    print(f"📄 Created test file: {test_file}")
    
    try:
        # Test upload
        job_id = test_upload(base_url, test_file)
        if not job_id:
            print("❌ Upload failed, stopping validation")
            return False
        
        # Test job status and wait for completion
        download_url = test_job_status(base_url, job_id)
        if not download_url:
            print("❌ Job processing failed, stopping validation")
            return False
        
        # Test download
        if not test_download(base_url, download_url):
            print("❌ Download failed")
            return False
        
        print("🎉 All tests passed! mdraft is working correctly.")
        return True
        
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.unlink(test_file)
            print(f"🧹 Cleaned up test file: {test_file}")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
