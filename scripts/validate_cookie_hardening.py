#!/usr/bin/env python3
"""
Deployment validation script for cookie hardening implementation.

This script validates that the cookie hardening features are working correctly
in the deployed environment.
"""

import os
import sys
import requests
import json
from datetime import datetime
from urllib.parse import urlparse

def validate_cookie_attributes(base_url):
    """Validate that cookies have proper security attributes."""
    
    print(f"Validating cookie hardening at: {base_url}")
    print("=" * 60)
    
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "base_url": base_url,
        "tests": {},
        "overall_status": "PASS"
    }
    
    # Test 1: Visitor session cookie creation
    print("1. Testing visitor session cookie creation...")
    try:
        response = requests.get(f"{base_url}/", allow_redirects=False, timeout=10)
        
        visitor_cookie = response.cookies.get("visitor_session_id")
        if visitor_cookie:
            print(f"   ✓ Visitor session cookie created")
            
            # Check cookie attributes
            cookie_obj = response.cookies.get("visitor_session_id")
            secure = getattr(cookie_obj, 'secure', False)
            httponly = getattr(cookie_obj, 'has_nonstandard_attr', lambda x: False)('HttpOnly')
            samesite = getattr(cookie_obj, 'has_nonstandard_attr', lambda x: None)('SameSite')
            
            test_result = {
                "status": "PASS" if secure and httponly and samesite == "Lax" else "FAIL",
                "secure": secure,
                "httponly": httponly,
                "samesite": samesite,
                "cookie_value": str(visitor_cookie)[:8] + "..."
            }
            
            if test_result["status"] == "PASS":
                print("   ✓ Cookie security attributes are correct")
            else:
                print("   ✗ Cookie security attributes are missing or incorrect")
                results["overall_status"] = "FAIL"
                
            results["tests"]["visitor_cookie"] = test_result
            
        else:
            print("   ✗ No visitor session cookie found")
            results["tests"]["visitor_cookie"] = {"status": "FAIL", "error": "No cookie found"}
            results["overall_status"] = "FAIL"
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
        results["tests"]["visitor_cookie"] = {"status": "ERROR", "error": str(e)}
        results["overall_status"] = "FAIL"
    
    # Test 2: Session configuration
    print("\n2. Testing session configuration...")
    try:
        response = requests.get(f"{base_url}/auth/login", allow_redirects=False, timeout=10)
        
        session_cookie = response.cookies.get("session")
        if session_cookie:
            print(f"   ✓ Session cookie found")
            results["tests"]["session_cookie"] = {"status": "PASS", "cookie_value": str(session_cookie)[:8] + "..."}
        else:
            print("   ℹ No session cookie (normal for unauthenticated requests)")
            results["tests"]["session_cookie"] = {"status": "INFO", "message": "No session cookie for unauthenticated request"}
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
        results["tests"]["session_cookie"] = {"status": "ERROR", "error": str(e)}
        results["overall_status"] = "FAIL"
    
    # Test 3: Environment configuration
    print("\n3. Checking environment configuration...")
    env_check = {}
    
    # Check if running in HTTPS
    is_https = base_url.startswith("https://")
    env_check["https"] = {"status": "PASS" if is_https else "WARN", "value": is_https}
    print(f"   {'✓' if is_https else '⚠'} HTTPS: {is_https}")
    
    # Check environment variables (if available)
    env_vars = ["SESSION_BACKEND", "REDIS_URL", "VISITOR_SESSION_TTL_DAYS", "SECRET_KEY"]
    for var in env_vars:
        value = os.getenv(var, "NOT_SET")
        if var == "SECRET_KEY" and value != "NOT_SET":
            env_check[var] = {"status": "PASS", "value": "SET"}
            print(f"   ✓ {var}: SET")
        elif var == "SECRET_KEY":
            env_check[var] = {"status": "WARN", "value": "NOT_SET"}
            print(f"   ⚠ {var}: NOT_SET")
        else:
            env_check[var] = {"status": "INFO", "value": value}
            print(f"   ℹ {var}: {value}")
    
    results["tests"]["environment"] = env_check
    
    # Test 4: Health check
    print("\n4. Testing application health...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("   ✓ Application health check passed")
            results["tests"]["health"] = {"status": "PASS", "status_code": response.status_code}
        else:
            print(f"   ✗ Health check failed: {response.status_code}")
            results["tests"]["health"] = {"status": "FAIL", "status_code": response.status_code}
            results["overall_status"] = "FAIL"
    except Exception as e:
        print(f"   ✗ Health check error: {e}")
        results["tests"]["health"] = {"status": "ERROR", "error": str(e)}
        results["overall_status"] = "FAIL"
    
    return results

def print_summary(results):
    """Print a summary of validation results."""
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    print(f"Timestamp: {results['timestamp']}")
    print(f"Target URL: {results['base_url']}")
    print(f"Overall Status: {results['overall_status']}")
    
    print("\nTest Results:")
    for test_name, test_result in results["tests"].items():
        if isinstance(test_result, dict) and "status" in test_result:
            status = test_result["status"]
            print(f"  {test_name}: {status}")
        elif isinstance(test_result, dict):
            # Handle nested results (like environment)
            print(f"  {test_name}:")
            for sub_test, sub_result in test_result.items():
                if isinstance(sub_result, dict) and "status" in sub_result:
                    print(f"    {sub_test}: {sub_result['status']}")
    
    print("\nRecommendations:")
    if results["overall_status"] == "PASS":
        print("  ✓ Cookie hardening is working correctly!")
        print("  ✓ Consider enabling Redis session backend for production")
        print("  ✓ Monitor session behavior in production")
    else:
        print("  ✗ Some tests failed - review configuration")
        print("  ✗ Check environment variables")
        print("  ✗ Verify HTTPS configuration")
        print("  ✗ Test in production environment")

def save_results(results, output_file=None):
    """Save validation results to file."""
    if output_file:
        try:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to: {output_file}")
        except Exception as e:
            print(f"\nWarning: Could not save results to {output_file}: {e}")

def main():
    """Main validation function."""
    if len(sys.argv) < 2:
        print("Usage: python validate_cookie_hardening.py <base_url> [output_file]")
        print("Example: python validate_cookie_hardening.py https://your-app.com results.json")
        sys.exit(1)
    
    base_url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate URL format
    if not base_url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://")
        sys.exit(1)
    
    try:
        results = validate_cookie_attributes(base_url)
        print_summary(results)
        save_results(results, output_file)
        
        if results["overall_status"] == "PASS":
            print("\n✓ Validation completed successfully!")
            sys.exit(0)
        else:
            print("\n✗ Validation completed with issues!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nValidation failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
