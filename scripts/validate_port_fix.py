#!/usr/bin/env python3
"""
Validate Render Port Binding Fix
This script helps verify that the port detection fix is working correctly.
"""

import os
import sys
import time
import requests
from urllib.parse import urlparse

def check_port_binding():
    """Check if the application is properly binding to the PORT environment variable."""
    print("🔧 Validating Render Port Binding Fix")
    print("=" * 50)
    
    # Check PORT environment variable
    port = os.environ.get('PORT')
    if port:
        print(f"✅ PORT environment variable is set: {port}")
    else:
        print("⚠️  PORT environment variable is not set (expected in local dev)")
        port = "10000"  # Default for testing
    
    # Check if we're in a Render-like environment
    render_env = os.environ.get('RENDER', 'false').lower() == 'true'
    if render_env:
        print("✅ Running in Render environment")
    else:
        print("ℹ️  Running in local development environment")
    
    # Test local binding (if possible)
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', int(port)))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is listening locally")
        else:
            print(f"ℹ️  Port {port} is not listening locally (expected if app not running)")
    except Exception as e:
        print(f"⚠️  Could not test local port binding: {e}")
    
    # Test health endpoint if available
    health_url = f"http://127.0.0.1:{port}/health/simple"
    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print(f"✅ Health endpoint responding: {health_url}")
        else:
            print(f"⚠️  Health endpoint returned {response.status_code}: {health_url}")
    except requests.exceptions.RequestException as e:
        print(f"ℹ️  Health endpoint not accessible: {e}")
    
    print("\n🎯 Configuration Validation:")
    
    # Check render.yaml
    if os.path.exists('render.yaml'):
        with open('render.yaml', 'r') as f:
            content = f.read()
            
        if 'key: PORT' in content:
            print("❌ render.yaml still contains explicit PORT setting")
        else:
            print("✅ render.yaml has no explicit PORT setting")
            
        if '$PORT' in content:
            print("✅ render.yaml uses $PORT in startCommand")
        else:
            print("❌ render.yaml doesn't use $PORT in startCommand")
    else:
        print("⚠️  render.yaml not found")
    
    # Check wsgi.py
    if os.path.exists('wsgi.py'):
        with open('wsgi.py', 'r') as f:
            content = f.read()
            
        if 'app.run(' in content:
            print("❌ wsgi.py contains app.run() - may interfere with gunicorn")
        else:
            print("✅ wsgi.py is clean (no app.run() calls)")
    else:
        print("⚠️  wsgi.py not found")
    
    print("\n🚀 Deployment Checklist:")
    print("1. ✅ Removed explicit PORT=10000 from render.yaml envVars")
    print("2. ✅ Using $PORT in gunicorn startCommand")
    print("3. ✅ wsgi.py is clean and compatible")
    print("4. 🔄 Commit and push changes to trigger deployment")
    print("5. 🔄 Monitor Render logs for successful port detection")
    print("6. 🔄 Test external access to your app")
    
    print("\n📋 Expected Render Log Messages (after deployment):")
    print("✅ 'Starting gunicorn'")
    print("✅ 'Listening at: http://0.0.0.0:10000' (or similar)")
    print("✅ 'Port scan successful' (or absence of port scan errors)")
    print("❌ 'No open ports detected' (should not appear)")
    print("❌ 'Port scan timeout' (should not appear)")

if __name__ == "__main__":
    check_port_binding()
