#!/usr/bin/env python3
"""
Verify API shim registration in production.

Run this in Render web shell to confirm the API shim is active.
"""
import os

# Set minimal environment variables for production
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'debug-secret-key')

try:
    from app import create_app
    
    print("🔍 VERIFYING API SHIM REGISTRATION")
    print("=" * 50)
    
    # Create app
    app = create_app()
    
    # Get all API routes
    api_routes = sorted([r.rule for r in app.url_map.iter_rules() if r.rule.startswith('/api')])
    
    print(f"📋 Total API routes found: {len(api_routes)}")
    print()
    
    # Check for critical endpoints
    critical_endpoints = ['/api/estimate', '/api/convert']
    found_endpoints = []
    
    for endpoint in critical_endpoints:
        if endpoint in api_routes:
            found_endpoints.append(endpoint)
            print(f"✅ {endpoint} - FOUND")
        else:
            print(f"❌ {endpoint} - MISSING")
    
    print()
    
    # Show all API routes
    print("📋 All API routes:")
    for route in api_routes:
        print(f"  {route}")
    
    print()
    
    # Summary
    if len(found_endpoints) == len(critical_endpoints):
        print("🎉 SUCCESS: API shim is properly registered!")
        print("   - Both /api/estimate and /api/convert are available")
        print("   - UI should work correctly")
    else:
        print("⚠️  WARNING: Some critical endpoints are missing")
        print("   - Check the logs for API shim registration errors")
    
    print()
    print("💡 Note: If you see endpoints listed twice, that's normal")
    print("   - Real blueprints and shim are both registered")
    print("   - Real blueprints take precedence")
    
except Exception as e:
    print(f"❌ Error during verification: {e}")
    import traceback
    traceback.print_exc()
