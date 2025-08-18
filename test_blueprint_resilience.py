#!/usr/bin/env python3
"""
Test script to verify blueprint registration resilience.
This tests that individual blueprint failures don't prevent other blueprints from registering.
"""

import os
import sys

# Set minimal environment variables for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

def test_blueprint_resilience():
    """Test that blueprint registration is resilient to individual failures."""
    print("🔧 TESTING BLUEPRINT REGISTRATION RESILIENCE")
    print("=" * 55)
    
    try:
        from app import create_app
        from app.blueprints import register_blueprints
        
        print("✅ App imports successful")
        
        # Create app
        app = create_app()
        print("✅ App creation successful")
        
        # Get all registered routes
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'rule': rule.rule,
                'methods': sorted(rule.methods),
                'endpoint': rule.endpoint
            })
        
        # Sort routes for consistent output
        routes.sort(key=lambda x: x['rule'])
        
        print(f"\n📋 Total routes registered: {len(routes)}")
        
        # Check for critical endpoints
        critical_endpoints = [
            '/api/estimate',
            '/api/convert', 
            '/health',
            '/',
            '/auth/login'
        ]
        
        found_endpoints = []
        missing_endpoints = []
        
        for endpoint in critical_endpoints:
            found = any(route['rule'] == endpoint for route in routes)
            if found:
                found_endpoints.append(endpoint)
                print(f"✅ {endpoint} - FOUND")
            else:
                missing_endpoints.append(endpoint)
                print(f"❌ {endpoint} - MISSING")
        
        # Check for API routes
        api_routes = [route for route in routes if route['rule'].startswith('/api')]
        print(f"\n📋 API routes found: {len(api_routes)}")
        
        # Show some example API routes
        if api_routes:
            print("   Example API routes:")
            for route in api_routes[:5]:  # Show first 5
                print(f"   - {route['rule']} ({', '.join(route['methods'])})")
        
        # Check for blueprint errors
        print(f"\n🔍 Blueprint Registration Status:")
        
        # Test the register_blueprints function directly
        test_app = create_app()
        blueprint_errors = register_blueprints(test_app)
        
        if blueprint_errors:
            print(f"⚠️  Blueprint registration errors: {len(blueprint_errors)}")
            for error in blueprint_errors[:3]:  # Show first 3 errors
                print(f"   - {error}")
            if len(blueprint_errors) > 3:
                print(f"   ... and {len(blueprint_errors) - 3} more errors")
        else:
            print("✅ All blueprints registered successfully")
        
        # Test resilience by checking if core functionality still works
        print(f"\n🎯 Resilience Test Results:")
        
        # Check if health endpoint works (should always be available)
        with app.test_client() as client:
            try:
                response = client.get('/health')
                if response.status_code == 200:
                    print("✅ Health endpoint working")
                else:
                    print(f"⚠️  Health endpoint returned {response.status_code}")
            except Exception as e:
                print(f"❌ Health endpoint failed: {e}")
        
        # Check if root endpoint works
        with app.test_client() as client:
            try:
                response = client.get('/')
                if response.status_code in [200, 302]:  # 302 is redirect to login
                    print("✅ Root endpoint working")
                else:
                    print(f"⚠️  Root endpoint returned {response.status_code}")
            except Exception as e:
                print(f"❌ Root endpoint failed: {e}")
        
        print(f"\n📊 SUMMARY:")
        print(f"  • Total routes: {len(routes)}")
        print(f"  • API routes: {len(api_routes)}")
        print(f"  • Critical endpoints found: {len(found_endpoints)}/{len(critical_endpoints)}")
        print(f"  • Blueprint errors: {len(blueprint_errors)}")
        
        if len(found_endpoints) >= 3 and len(blueprint_errors) < 5:
            print("  ✅ Blueprint registration is resilient")
            return True
        else:
            print("  ⚠️  Some blueprint registration issues detected")
            return False
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_blueprint_resilience()
    sys.exit(0 if success else 1)
