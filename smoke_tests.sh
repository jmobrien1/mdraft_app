#!/bin/bash
# Smoke tests for mdraft app fixes
# Run these in Render web shell to verify everything is working

set -e

echo "🧪 MDRAFT SMOKE TESTS"
echo "======================"

# Check if RENDER_EXTERNAL_URL is set
if [ -z "$RENDER_EXTERNAL_URL" ]; then
    echo "❌ RENDER_EXTERNAL_URL not set. Please run this in Render web shell."
    exit 1
fi

echo "📍 Testing against: $RENDER_EXTERNAL_URL"
echo ""

# Test 1: Print API routes
echo "1️⃣  Testing API routes..."
python3 - <<'PY'
import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'debug-secret-key')

from app import create_app
a = create_app()
api_routes = sorted([f"{r.rule} {sorted(r.methods)}" for r in a.url_map.iter_rules() if r.rule.startswith('/api')])
print("API routes found:")
for route in api_routes:
    print(f"  {route}")
print(f"\nTotal API routes: {len(api_routes)}")
PY

echo ""
echo "2️⃣  Testing /api/estimate endpoint..."
curl -sS -i "$RENDER_EXTERNAL_URL/api/estimate" -F "file=@/etc/hosts" || echo "❌ /api/estimate failed"

echo ""
echo "3️⃣  Testing /api/convert endpoint..."
curl -sS -i "$RENDER_EXTERNAL_URL/api/convert" -F "file=@/etc/hosts" || echo "❌ /api/convert failed"

echo ""
echo "4️⃣  Testing /api/conversions list..."
curl -sS -i "$RENDER_EXTERNAL_URL/api/conversions?limit=10" || echo "❌ /api/conversions failed"

echo ""
echo "5️⃣  Testing /health endpoint..."
curl -sS -i "$RENDER_EXTERNAL_URL/health" || echo "❌ /health failed"

echo ""
echo "🎉 Smoke tests completed!"
echo ""
echo "Expected results:"
echo "  ✅ /api/estimate: 200 OK or 302 (redirect to login)"
echo "  ✅ /api/convert: 202 Accepted or 302 (redirect to login)"
echo "  ✅ /api/conversions: 200 OK with JSON response"
echo "  ✅ /health: 200 OK"
echo ""
echo "If you see 302 redirects, that's normal - endpoints require authentication."
echo "If you see 500 errors, check the logs for specific issues."
