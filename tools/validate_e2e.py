#!/usr/bin/env python3
"""
End-to-end validation script for mdraft application.

This script tests the complete workflow:
1. Health checks for web and worker services
2. Upload a test document
3. Poll job status until completed/failed (with exponential backoff)
4. Download and validate the result

Usage:
    python tools/validate_e2e.py --file samples/sample.pdf
    python tools/validate_e2e.py --web-url http://localhost:5000 --worker-url http://localhost:5001
"""

import os
import sys
import time
import argparse
import requests
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def parse_arguments():
    """Parse command line arguments and environment variables."""
    parser = argparse.ArgumentParser(description="End-to-end validation for mdraft")
    parser.add_argument("--web-url", 
                       default=os.getenv("WEB_BASE_URL", "http://localhost:5000"),
                       help="Web service base URL")
    parser.add_argument("--worker-url", 
                       default=os.getenv("WORKER_BASE_URL", "http://localhost:5001"),
                       help="Worker service base URL")
    parser.add_argument("--file", 
                       default=os.getenv("TEST_FILE"),
                       help="Test file path (optional)")
    parser.add_argument("--timeout", 
                       type=int,
                       default=int(os.getenv("TIMEOUT_SECS", "300")),
                       help="Timeout in seconds")
    
    return parser.parse_args()


def create_test_pdf() -> str:
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
        c.drawString(100, 600, "This document contains multiple lines of text.")
        c.drawString(100, 550, "The conversion should preserve the content structure.")
        c.save()
        
        print(f"📄 Created test PDF: {temp_path}")
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
            f.write("This document contains multiple lines of text.\n")
            f.write("The conversion should preserve the content structure.\n")
        
        print(f"📄 Created test text file: {temp_path}")
        return temp_path


def test_health_check(url: str, service_name: str) -> bool:
    """Test the health check endpoint."""
    print(f"🔍 Testing {service_name} health check: {url}/health")
    start_time = time.time()
    
    try:
        response = requests.get(f"{url}/health", timeout=10)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {service_name} health check passed ({duration:.2f}s)")
            if service_name == "worker" and data.get("service") != "worker":
                print(f"⚠️  Warning: Expected worker service, got {data.get('service')}")
            return True
        else:
            print(f"❌ {service_name} health check failed: {response.status_code} ({duration:.2f}s)")
            return False
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ {service_name} health check error: {e} ({duration:.2f}s)")
        return False


def test_upload(web_url: str, file_path: str) -> Optional[int]:
    """Test file upload and return job ID."""
    print(f"📤 Testing file upload: {os.path.basename(file_path)}")
    start_time = time.time()
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{web_url}/upload", files=files, timeout=30)
        
        duration = time.time() - start_time
        
        if response.status_code == 202:
            data = response.json()
            job_id = data.get('job_id')
            print(f"✅ Upload successful - Job ID: {job_id} ({duration:.2f}s)")
            return job_id
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text} ({duration:.2f}s)")
            return None
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Upload error: {e} ({duration:.2f}s)")
        return None


def poll_job_status(web_url: str, job_id: int, timeout_secs: int) -> Optional[str]:
    """Poll job status until completed/failed with exponential backoff."""
    print(f"⏳ Monitoring job {job_id}...")
    start_time = time.time()
    poll_count = 0
    backoff_seconds = 1
    
    while time.time() - start_time < timeout_secs:
        poll_count += 1
        poll_start = time.time()
        
        try:
            response = requests.get(f"{web_url}/jobs/{job_id}", timeout=10)
            poll_duration = time.time() - poll_start
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                print(f"📊 Poll {poll_count}: Job status: {status} ({poll_duration:.2f}s)")
                
                if status == 'completed':
                    output_signed_url = data.get('output_signed_url')
                    if output_signed_url:
                        total_duration = time.time() - start_time
                        print(f"✅ Job completed! Download URL available ({total_duration:.2f}s)")
                        return output_signed_url
                    else:
                        print("⚠️  Job completed but no download URL")
                        return None
                elif status == 'failed':
                    error_message = data.get('error', 'Unknown error')
                    print(f"❌ Job failed: {error_message}")
                    return None
                elif status in ['queued', 'processing']:
                    print(f"⏳ Job still processing... (backoff: {backoff_seconds}s)")
                    time.sleep(backoff_seconds)
                    # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
                    backoff_seconds = min(backoff_seconds * 2, 30)
                    continue
                else:
                    print(f"⚠️  Unknown status: {status}")
                    return None
            else:
                print(f"❌ Status check failed: {response.status_code}")
                return None
        except Exception as e:
            poll_duration = time.time() - poll_start
            print(f"❌ Status check error: {e} ({poll_duration:.2f}s)")
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)
            continue
    
    print(f"⏰ Timeout waiting for job completion ({timeout_secs}s)")
    return None


def test_download(download_url: str) -> bool:
    """Test file download and validate content."""
    print(f"📥 Testing download: {download_url[:100]}...")
    start_time = time.time()
    
    try:
        response = requests.get(download_url, timeout=30)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            content = response.text
            content_length = len(content)
            
            if content_length > 0:
                print(f"✅ Download successful - {content_length} characters ({duration:.2f}s)")
                print(f"📄 Content preview: {content[:200]}...")
                return True
            else:
                print(f"❌ Download successful but content is empty ({duration:.2f}s)")
                return False
        else:
            print(f"❌ Download failed: {response.status_code} ({duration:.2f}s)")
            return False
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Download error: {e} ({duration:.2f}s)")
        return False


def main():
    """Run the complete validation test."""
    args = parse_arguments()
    
    print("🧪 Starting mdraft E2E validation...")
    print(f"🌐 Web URL: {args.web_url}")
    print(f"⚙️  Worker URL: {args.worker_url}")
    print(f"⏱️  Timeout: {args.timeout}s")
    
    overall_start_time = time.time()
    
    # Step 1: Health checks
    print("\n" + "="*60)
    print("STEP 1: Health Checks")
    print("="*60)
    
    if not test_health_check(args.web_url, "Web"):
        print("❌ Web health check failed, stopping validation")
        return False
    
    if not test_health_check(args.worker_url, "Worker"):
        print("❌ Worker health check failed, stopping validation")
        return False
    
    # Step 2: Prepare test file
    print("\n" + "="*60)
    print("STEP 2: Test File Preparation")
    print("="*60)
    
    if args.file and os.path.exists(args.file):
        test_file = args.file
        print(f"📄 Using provided test file: {test_file}")
    else:
        test_file = create_test_pdf()
        print(f"📄 Using generated test file: {test_file}")
    
    try:
        # Step 3: Upload test file
        print("\n" + "="*60)
        print("STEP 3: File Upload")
        print("="*60)
        
        job_id = test_upload(args.web_url, test_file)
        if not job_id:
            print("❌ Upload failed, stopping validation")
            return False
        
        # Step 4: Poll job status
        print("\n" + "="*60)
        print("STEP 4: Job Processing")
        print("="*60)
        
        download_url = poll_job_status(args.web_url, job_id, args.timeout)
        if not download_url:
            print("❌ Job processing failed, stopping validation")
            return False
        
        # Step 5: Download and validate result
        print("\n" + "="*60)
        print("STEP 5: Result Download")
        print("="*60)
        
        if not test_download(download_url):
            print("❌ Download failed")
            return False
        
        # Success!
        overall_duration = time.time() - overall_start_time
        print("\n" + "="*60)
        print("🎉 VALIDATION PASSED!")
        print("="*60)
        print(f"⏱️  Total duration: {overall_duration:.2f}s")
        print(f"📊 Job ID: {job_id}")
        print(f"🔗 Download URL: {download_url[:100]}...")
        print("✅ mdraft is working correctly!")
        
        return True
        
    finally:
        # Cleanup generated test file
        if not args.file and os.path.exists(test_file):
            os.unlink(test_file)
            print(f"🧹 Cleaned up generated test file: {test_file}")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
