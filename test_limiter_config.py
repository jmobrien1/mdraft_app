#!/usr/bin/env python3
"""
Test script to verify Flask-Limiter configuration.
Run this to check if the rate limiter is properly configured with Redis storage.
"""

import os
import sys

# Set minimal environment variables for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

def test_limiter_configuration():
    """Test the rate limiter configuration."""
    print("🔧 TESTING FLASK-LIMITER CONFIGURATION")
    print("=" * 50)
    
    # Check environment variable
    storage_uri = os.getenv("FLASK_LIMITER_STORAGE_URI")
    print(f"📋 FLASK_LIMITER_STORAGE_URI: {storage_uri or 'NOT_SET'}")
    
    try:
        from app import create_app
        from app.extensions import limiter
        
        print("✅ App imports successful")
        
        # Create app
        app = create_app()
        print("✅ App creation successful")
        
        # Check limiter configuration
        print(f"📋 Limiter storage URI: {getattr(limiter, 'storage_uri', 'NOT_SET')}")
        print(f"📋 Limiter default limits: {getattr(limiter, 'default_limits', 'NOT_SET')}")
        print(f"📋 Limiter initialized: {hasattr(limiter, '_storage')}")
        
        # Test limiter functionality
        with app.app_context():
            try:
                # Try to access limiter storage
                if hasattr(limiter, '_storage'):
                    print("✅ Limiter storage is configured")
                    
                    # Test a simple rate limit
                    from flask_limiter.util import get_remote_address
                    key = get_remote_address()
                    print(f"📋 Test rate limit key: {key}")
                    
                    # Check if we can access the storage
                    if hasattr(limiter._storage, 'get'):
                        print("✅ Limiter storage has get method")
                    else:
                        print("⚠️  Limiter storage missing get method")
                        
                else:
                    print("❌ Limiter storage not configured")
                    
            except Exception as e:
                print(f"❌ Error testing limiter: {e}")
        
        print()
        print("🎯 SUMMARY:")
        if storage_uri and storage_uri.startswith('redis://'):
            print("  ✅ Redis storage URI configured")
            if hasattr(limiter, '_storage'):
                print("  ✅ Limiter storage initialized")
                print("  ✅ Rate limiter should work with Redis")
            else:
                print("  ❌ Limiter storage not initialized")
        elif storage_uri == 'memory://' or not storage_uri:
            print("  ⚠️  Using memory storage (not recommended for production)")
            print("  💡 Set FLASK_LIMITER_STORAGE_URI to use Redis")
        else:
            print(f"  ❓ Unknown storage URI: {storage_uri}")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_limiter_configuration()
    sys.exit(0 if success else 1)
