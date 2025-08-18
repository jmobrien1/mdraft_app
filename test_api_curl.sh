#!/bin/bash
# Test script for real API endpoints (CSRF exempt, 100MB upload limit)
# Usage: ./test_api_curl.sh [BASE_URL]
# Example: ./test_api_curl.sh https://your-app.onrender.com

BASE_URL="${1:-http://localhost:5000}"

echo "🧪 Testing real API endpoints at: $BASE_URL"
echo "============================================================"

# Create a test file
echo "This is a test file for API shim testing." > /tmp/test_api.txt

echo ""
echo "📊 Testing /api/estimate..."
curl -sS -i "$BASE_URL/api/estimate" -F "file=@/tmp/test_api.txt"

echo ""
echo ""
echo "🔄 Testing /api/convert..."
curl -sS -i "$BASE_URL/api/convert" -F "file=@/tmp/test_api.txt"

echo ""
echo ""
echo "✅ Real API test completed!"

# Clean up
rm -f /tmp/test_api.txt
