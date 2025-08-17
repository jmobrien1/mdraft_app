#!/bin/bash
set -euo pipefail

echo "🔧 Testing Render Port Binding Fix"
echo "=================================="

# Test 1: Check if PORT environment variable is properly set
echo "1. Testing PORT environment variable..."
if [[ -n "${PORT:-}" ]]; then
    echo "   ✅ PORT is set to: $PORT"
else
    echo "   ❌ PORT is not set (this is expected in local dev)"
fi

# Test 2: Test gunicorn binding with $PORT
echo "2. Testing gunicorn port binding..."
if command -v gunicorn >/dev/null 2>&1; then
    echo "   ✅ gunicorn is available"
    
    # Test the exact command from render.yaml
    echo "   Testing: gunicorn --bind 0.0.0.0:\${PORT:-10000} --workers 2 --threads 8 --timeout 120 --access-logfile - --error-logfile - wsgi:app"
    
    # Start gunicorn in background for testing
    PORT="${PORT:-10000}"
    timeout 5s gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 5 --access-logfile - --error-logfile - wsgi:app &
    GUNICORN_PID=$!
    
    # Wait a moment for startup
    sleep 2
    
    # Test if port is listening
    if netstat -an 2>/dev/null | grep -q ":$PORT.*LISTEN" || lsof -i :$PORT >/dev/null 2>&1; then
        echo "   ✅ Port $PORT is listening"
    else
        echo "   ❌ Port $PORT is not listening"
    fi
    
    # Kill the test process
    kill $GUNICORN_PID 2>/dev/null || true
    wait $GUNICORN_PID 2>/dev/null || true
else
    echo "   ⚠️  gunicorn not available (install with: pip install gunicorn)"
fi

# Test 3: Check wsgi.py compatibility
echo "3. Testing wsgi.py compatibility..."
if [[ -f "wsgi.py" ]]; then
    echo "   ✅ wsgi.py exists"
    
    # Check if wsgi.py has any app.run() calls that might interfere
    if grep -q "app\.run" wsgi.py; then
        echo "   ❌ wsgi.py contains app.run() - this may interfere with gunicorn"
    else
        echo "   ✅ wsgi.py is clean (no app.run() calls)"
    fi
else
    echo "   ❌ wsgi.py not found"
fi

# Test 4: Check render.yaml configuration
echo "4. Testing render.yaml configuration..."
if [[ -f "render.yaml" ]]; then
    echo "   ✅ render.yaml exists"
    
    # Check for explicit PORT setting (should be removed)
    if grep -q "key: PORT" render.yaml; then
        echo "   ❌ render.yaml still contains explicit PORT setting"
        grep -A 1 "key: PORT" render.yaml
    else
        echo "   ✅ render.yaml has no explicit PORT setting"
    fi
    
    # Check for $PORT usage in startCommand
    if grep -q "\$PORT" render.yaml; then
        echo "   ✅ render.yaml uses \$PORT in startCommand"
    else
        echo "   ❌ render.yaml doesn't use \$PORT in startCommand"
    fi
else
    echo "   ❌ render.yaml not found"
fi

echo ""
echo "🎯 SUMMARY:"
echo "The key fix was removing the explicit 'PORT: 10000' from render.yaml envVars"
echo "This allows Render to manage the PORT environment variable properly."
echo ""
echo "🚀 Next steps:"
echo "1. Commit and push the render.yaml changes"
echo "2. Monitor Render logs for successful port detection"
echo "3. Test external access to your app"
