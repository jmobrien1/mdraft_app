#!/usr/bin/env python3
"""
Test script for schema guard functionality.
"""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_schema_guard_import():
    """Test that the schema guard can be imported and run."""
    try:
        from scripts.schema_guard import run
        print("✅ Schema guard imports successfully")
        
        # Test the run function (should skip if no DATABASE_URL)
        result = run()
        print(f"✅ Schema guard run() returned: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Schema guard import/run failed: {e}")
        return False

def test_schema_guard_module():
    """Test that the schema guard can be run as a module."""
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, "-m", "scripts.schema_guard"
        ], capture_output=True, text=True)
        
        print(f"✅ Schema guard module execution: {result.returncode}")
        if result.stdout:
            print(f"   stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"   stderr: {result.stderr.strip()}")
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Schema guard module test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Schema Guard...")
    
    success1 = test_schema_guard_import()
    success2 = test_schema_guard_module()
    
    if success1 and success2:
        print("✅ All schema guard tests passed!")
        sys.exit(0)
    else:
        print("❌ Some schema guard tests failed!")
        sys.exit(1)
