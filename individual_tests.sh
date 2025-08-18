#!/bin/bash
# Individual test commands for copy/paste in Render web shell

echo "📋 INDIVIDUAL TEST COMMANDS"
echo "==========================="
echo ""
echo "Copy and paste these commands one by one in Render web shell:"
echo ""

echo "# 1. Print API routes"
echo 'python3 - <<'"'"'PY'"'"'
import os
os.environ.setdefault("'"'"'DATABASE_URL'"'"'", '"'"'sqlite:///:memory:'"'"')
os.environ.setdefault("'"'"'SECRET_KEY'"'"'", '"'"'debug-secret-key'"'"')

from app import create_app
a = create_app()
api_routes = sorted([f"{r.rule} {sorted(r.methods)}" for r in a.url_map.iter_rules() if r.rule.startswith("'"'"'/api'"'"'")])
print("API routes found:")
for route in api_routes:
    print(f"  {route}")
print(f"\nTotal API routes: {len(api_routes)}")
PY'
echo ""

echo "# 2. Test /api/estimate endpoint"
echo 'curl -sS -i "$RENDER_EXTERNAL_URL/api/estimate" -F "file=@/etc/hosts"'
echo ""

echo "# 3. Test /api/convert endpoint"
echo 'curl -sS -i "$RENDER_EXTERNAL_URL/api/convert" -F "file=@/etc/hosts"'
echo ""

echo "# 4. Test /api/conversions list"
echo 'curl -sS -i "$RENDER_EXTERNAL_URL/api/conversions?limit=10"'
echo ""

echo "# 5. Test /health endpoint"
echo 'curl -sS -i "$RENDER_EXTERNAL_URL/health"'
echo ""

echo "Expected results:"
echo "  ✅ /api/estimate: 200 OK or 302 (redirect to login)"
echo "  ✅ /api/convert: 202 Accepted or 302 (redirect to login)"
echo "  ✅ /api/conversions: 200 OK with JSON response"
echo "  ✅ /health: 200 OK"
echo ""
echo "If you see 302 redirects, that's normal - endpoints require authentication."
echo "If you see 500 errors, check the logs for specific issues."
