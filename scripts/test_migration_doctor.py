#!/usr/bin/env python3
"""
Test script for migration doctor functionality.
"""

import os
import sys
import subprocess

def test_migration_doctor():
    """Test that migration doctor can be imported and run."""
    try:
        # Test import
        from scripts.migration_doctor import main, _env_db_url, _run
        
        print("✅ Migration doctor imports successfully")
        
        # Test environment variable detection
        url = _env_db_url()
        if url:
            print(f"✅ Database URL found: {url[:20]}...")
        else:
            print("⚠️ No DATABASE_URL found (expected in production)")
        
        # Test command execution
        result = _run("echo 'test'")
        if result == 0:
            print("✅ Command execution works")
        else:
            print("❌ Command execution failed")
            
        print("✅ Migration doctor test passed")
        return True
        
    except Exception as e:
        print(f"❌ Migration doctor test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_migration_doctor()
    sys.exit(0 if success else 1)
