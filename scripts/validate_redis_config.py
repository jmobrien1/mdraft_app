#!/usr/bin/env python3
"""
Redis Configuration Validation Script

This script validates that the new Redis service is properly configured
and working correctly.
"""

import os
import sys
import redis
from urllib.parse import urlparse

def validate_redis_url(url, name):
    """Validate a Redis URL and test connection."""
    if not url:
        print(f"❌ {name}: NOT SET")
        return False
    
    # Clean the URL
    clean_url = url.strip()
    if clean_url != url:
        print(f"⚠️  {name}: Had trailing whitespace, cleaned")
    
    try:
        # Parse the URL
        parsed = urlparse(clean_url)
        print(f"✅ {name}: URL format valid")
        print(f"   Scheme: {parsed.scheme}")
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        
        # Test connection
        client = redis.from_url(
            clean_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        client.ping()
        print(f"✅ {name}: Connection successful")
        
        # Test basic operations
        test_key = f"test_{name.lower()}"
        client.set(test_key, "test_value", ex=60)
        value = client.get(test_key)
        client.delete(test_key)
        
        if value == "test_value":
            print(f"✅ {name}: Read/write operations successful")
            return True
        else:
            print(f"❌ {name}: Read/write operations failed")
            return False
            
    except Exception as e:
        print(f"❌ {name}: Connection failed - {e}")
        print(f"   URL: {clean_url[:50]}...")
        return False

def main():
    """Validate all Redis configurations."""
    print("🔍 REDIS CONFIGURATION VALIDATION")
    print("=" * 50)
    
    # Check environment variables
    redis_configs = [
        ("REDIS_URL", os.getenv("REDIS_URL")),
        ("SESSION_REDIS_URL", os.getenv("SESSION_REDIS_URL")),
        ("FLASK_LIMITER_STORAGE_URI", os.getenv("FLASK_LIMITER_STORAGE_URI"))
    ]
    
    all_valid = True
    for name, url in redis_configs:
        print(f"\n--- Testing {name} ---")
        if not validate_redis_url(url, name):
            all_valid = False
    
    # Test Flask-Limiter configuration
    print(f"\n--- Testing Flask-Limiter Configuration ---")
    try:
        from flask import Flask
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        limiter_url = os.getenv("FLASK_LIMITER_STORAGE_URI", "memory://")
        if limiter_url and limiter_url != "memory://":
            clean_url = limiter_url.strip()
            limiter = Limiter(
                app=app,
                key_func=get_remote_address,
                storage_uri=clean_url,
                default_limits=["100 per minute"]
            )
            print("✅ Flask-Limiter with Redis: Configuration successful")
        else:
            print("⚠️  Flask-Limiter: Using memory storage (no Redis URL)")
            
    except Exception as e:
        print(f"❌ Flask-Limiter configuration failed: {e}")
        all_valid = False
    
    # Summary
    print(f"\n" + "=" * 50)
    if all_valid:
        print("🎉 All Redis configurations are valid!")
        print("✅ Your new Redis service is working correctly")
    else:
        print("⚠️  Some Redis configurations have issues")
        print("Check the errors above and fix them")
    
    return 0 if all_valid else 1

if __name__ == "__main__":
    sys.exit(main())
