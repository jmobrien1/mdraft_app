#!/usr/bin/env python3
"""
Test script to verify pip-tools workflow
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Error: {e.stderr}")
        return False

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if Path(filepath).exists():
        print(f"✅ {description} exists")
        return True
    else:
        print(f"❌ {description} not found")
        return False

def main():
    print("🧪 Testing pip-tools workflow...")
    print("=" * 40)
    
    # Check if pip-tools is installed
    if not run_command("pip-compile --version", "Checking pip-compile availability"):
        print("💡 Install pip-tools: pip install pip-tools")
        return False
    
    # Test compiling requirements.in
    if check_file_exists("requirements.in", "requirements.in file"):
        if run_command("pip-compile requirements.in --dry-run", "Testing requirements.in compilation"):
            print("✅ requirements.in can be compiled successfully")
        else:
            print("❌ requirements.in compilation failed")
            return False
    
    # Test compiling requirements-dev.in
    if check_file_exists("requirements-dev.in", "requirements-dev.in file"):
        if run_command("pip-compile requirements-dev.in --dry-run", "Testing requirements-dev.in compilation"):
            print("✅ requirements-dev.in can be compiled successfully")
        else:
            print("❌ requirements-dev.in compilation failed")
            return False
    
    print("\n" + "=" * 40)
    print("🎉 pip-tools workflow test completed!")
    print("\n💡 Next steps:")
    print("  make lock        # Generate locked requirements.txt")
    print("  make lock-dev    # Generate locked requirements-dev.txt")
    print("  make security-scan # Run security validation")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
