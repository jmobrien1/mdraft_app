#!/bin/bash
"""
Quick Status Check Script

This script quickly checks the status of your Render deployment.
"""

echo "🔍 QUICK STATUS CHECK"
echo "===================="
echo ""

# Test basic connectivity
echo "Testing basic connectivity..."
if curl -s --connect-timeout 10 https://mdraft.onrender.com/ > /dev/null 2>&1; then
    echo "✅ Service is responding"
else
    echo "❌ Service is not responding"
    echo "   This could mean:"
    echo "   - Service is still restarting"
    echo "   - App creation failed completely"
    echo "   - Network connectivity issues"
    exit 1
fi

# Test specific endpoints
echo ""
echo "Testing endpoints..."

endpoints=(
    "/health/simple:Health Check"
    "/test:Test Route"
    "/debug:Debug Route"
    "/:Homepage"
)

for endpoint_info in "${endpoints[@]}"; do
    endpoint="${endpoint_info%:*}"
    description="${endpoint_info#*:}"
    
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "https://mdraft.onrender.com$endpoint")
    
    case $status_code in
        200)
            echo "✅ $description: $status_code"
            ;;
        404)
            echo "❌ $description: $status_code (Not Found)"
            ;;
        500)
            echo "❌ $description: $status_code (Internal Server Error)"
            ;;
        *)
            echo "⚠️  $description: $status_code (Unexpected)"
            ;;
    esac
done

echo ""
echo "📋 NEXT STEPS:"
echo "1. If you see 404s, check Render logs for app creation errors"
echo "2. If you see 500s, check Render logs for request handling errors"
echo "3. Look for these specific messages in the logs:"
echo "   - '❌❌❌ FATAL: Exception occurred during app creation'"
echo "   - '❌❌❌ FATAL: Exception occurred during a request'"
echo "   - '✅ Flask app created successfully'"
echo ""
echo "4. Run the enhanced debug script if needed:"
echo "   cp wsgi_enhanced_debug.py wsgi.py"
echo "   # Then restart the service"
