#!/usr/bin/env python3
"""
Test GCS connection and bucket access.
Run this in production to verify GCS is working.
"""
import os
import sys

def test_gcs_connection():
    """Test GCS connection and bucket access."""
    print("=== GCS Connection Test ===")
    
    # Check environment variables
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    storage_backend = os.getenv("STORAGE_BACKEND")
    
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS_JSON: {'Set' if creds_json else 'Not set'}")
    print(f"GCS_BUCKET_NAME: {bucket_name}")
    print(f"STORAGE_BACKEND: {storage_backend}")
    
    # Check if credentials file exists or JSON is provided
    if creds_path and os.path.exists(creds_path):
        print(f"✅ Credentials file exists: {creds_path}")
    elif creds_json:
        print(f"✅ JSON credentials provided via environment variable")
        # Write JSON to temporary file for testing
        try:
            import json
            json.loads(creds_json)  # Validate JSON
            with open(creds_path, 'w') as f:
                f.write(creds_json)
            print(f"✅ JSON credentials written to {creds_path}")
        except Exception as e:
            print(f"❌ Failed to write JSON credentials: {e}")
            return False
    else:
        print(f"❌ No credentials found (file: {creds_path}, JSON: {'Set' if creds_json else 'Not set'})")
        return False
    
    # Test GCS import
    try:
        from google.cloud import storage
        print("✅ google.cloud.storage import successful")
    except ImportError as e:
        print(f"❌ google.cloud.storage import failed: {e}")
        return False
    
    # Test GCS client creation
    try:
        client = storage.Client()
        print("✅ GCS client created successfully")
    except Exception as e:
        print(f"❌ GCS client creation failed: {e}")
        return False
    
    # Test bucket access
    if bucket_name:
        try:
            bucket = client.bucket(bucket_name)
            if bucket.exists():
                print(f"✅ Bucket '{bucket_name}' exists and accessible")
                
                # List a few blobs to test access
                blobs = list(bucket.list_blobs(max_results=5))
                print(f"✅ Bucket access confirmed - found {len(blobs)} blobs")
                
                return True
            else:
                print(f"❌ Bucket '{bucket_name}' does not exist")
                return False
        except Exception as e:
            print(f"❌ Bucket access failed: {e}")
            return False
    else:
        print("❌ GCS_BUCKET_NAME not set")
        return False

if __name__ == "__main__":
    success = test_gcs_connection()
    if success:
        print("\n🎉 GCS connection test PASSED")
        sys.exit(0)
    else:
        print("\n❌ GCS connection test FAILED")
        sys.exit(1)
