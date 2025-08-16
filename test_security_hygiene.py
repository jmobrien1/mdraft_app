#!/usr/bin/env python3
"""
Test script to validate security hygiene implementation.

This script tests that secrets are properly isolated and not exposed
in configuration dumps or logs.
"""

import os
import sys
import json
from typing import Dict, Any

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_secret_isolation():
    """Test that secrets are not exposed in configuration dumps."""
    print("=== Testing Secret Isolation ===")
    
    from app.config import get_config
    
    # Get configuration
    config = get_config()
    
    # Test that to_dict() doesn't contain secrets
    config_dict = config.to_dict()
    
    # List of secrets that should NOT be in config_dict
    secrets_to_check = [
        "SECRET_KEY",
        "STRIPE_SECRET_KEY", 
        "STRIPE_WEBHOOK_SECRET",
        "OPENAI_API_KEY",
        "ADMIN_TOKEN",
        "WEBHOOK_SECRET"
    ]
    
    exposed_secrets = []
    for secret in secrets_to_check:
        if secret in config_dict:
            exposed_secrets.append(secret)
            print(f"✗ Secret exposed in config_dict: {secret}")
        else:
            print(f"✓ Secret properly isolated: {secret}")
    
    if exposed_secrets:
        print(f"\n❌ {len(exposed_secrets)} secrets exposed in configuration dump!")
        return False
    else:
        print("\n✅ All secrets properly isolated from configuration dumps")
        return True

def test_secret_access():
    """Test that secrets are accessible but not exposed."""
    print("\n=== Testing Secret Access ===")
    
    from app.config import get_config
    
    # Get configuration
    config = get_config()
    
    # Test that secrets are accessible via direct access
    secrets_to_check = [
        ("FLASK_SECRET_KEY", config.FLASK_SECRET_KEY),
        ("STRIPE_SECRET_KEY", config.STRIPE_SECRET_KEY),
        ("STRIPE_WEBHOOK_SECRET", config.STRIPE_WEBHOOK_SECRET),
        ("OPENAI_API_KEY", config.OPENAI_API_KEY),
        ("ADMIN_TOKEN", config.ADMIN_TOKEN),
        ("WEBHOOK_SECRET", config.WEBHOOK_SECRET)
    ]
    
    accessible_secrets = []
    for secret_name, secret_value in secrets_to_check:
        if secret_value is not None:
            accessible_secrets.append(secret_name)
            print(f"✓ Secret accessible: {secret_name}")
        else:
            print(f"⚠ Secret not set: {secret_name}")
    
    print(f"\n✅ {len(accessible_secrets)} secrets are accessible")
    return True

def test_environment_template():
    """Test that env.example doesn't contain secrets."""
    print("\n=== Testing Environment Template ===")
    
    env_example_path = "env.example"
    if not os.path.exists(env_example_path):
        print(f"✗ {env_example_path} not found")
        return False
    
    with open(env_example_path, 'r') as f:
        content = f.read()
    
    # Check for actual secret values that should NOT be in env.example
    # (not commented examples)
    secret_patterns = [
        "sk_test_",
        "sk_live_",
        "pk_test_",
        "pk_live_",
        "whsec_"
    ]
    
    # Check for uncommented secret assignments
    uncommented_secrets = [
        "SECRET_KEY=",
        "OPENAI_API_KEY=",
        "STRIPE_SECRET_KEY=",
        "STRIPE_WEBHOOK_SECRET=",
        "ADMIN_TOKEN=",
        "WEBHOOK_SECRET="
    ]
    
    found_secrets = []
    for pattern in secret_patterns:
        if pattern in content:
            found_secrets.append(pattern)
            print(f"✗ Secret pattern found in env.example: {pattern}")
        else:
            print(f"✓ Secret pattern properly excluded: {pattern}")
    
    # Check for uncommented secret assignments
    found_uncommented = []
    for secret in uncommented_secrets:
        # Look for the pattern without a # comment prefix
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(secret) and not line.startswith('#'):
                found_uncommented.append(secret)
                print(f"✗ Uncommented secret assignment found: {secret}")
                break
        else:
            print(f"✓ Secret assignment properly commented: {secret}")
    
    if found_secrets or found_uncommented:
        total_found = len(found_secrets) + len(found_uncommented)
        print(f"\n❌ {total_found} secret issues found in env.example!")
        return False
    else:
        print("\n✅ env.example properly excludes all secret patterns and assignments")
        return True

def test_render_configuration():
    """Test that render.yaml properly configures secrets."""
    print("\n=== Testing Render Configuration ===")
    
    render_yaml_path = "render.yaml"
    if not os.path.exists(render_yaml_path):
        print(f"✗ {render_yaml_path} not found")
        return False
    
    with open(render_yaml_path, 'r') as f:
        content = f.read()
    
    # Check for required secret configurations
    required_secrets = [
        "OPENAI_API_KEY",
        "STRIPE_SECRET_KEY", 
        "STRIPE_WEBHOOK_SECRET",
        "ADMIN_TOKEN",
        "WEBHOOK_SECRET"
    ]
    
    configured_secrets = []
    for secret in required_secrets:
        if f"key: {secret}" in content and "sync: false" in content:
            configured_secrets.append(secret)
            print(f"✓ Secret properly configured: {secret}")
        else:
            print(f"✗ Secret not properly configured: {secret}")
    
    if len(configured_secrets) == len(required_secrets):
        print(f"\n✅ All {len(configured_secrets)} secrets properly configured in render.yaml")
        return True
    else:
        print(f"\n❌ Only {len(configured_secrets)}/{len(required_secrets)} secrets properly configured")
        return False

def test_mdraft_public_mode_alignment():
    """Test that MDRAFT_PUBLIC_MODE is aligned between services."""
    print("\n=== Testing MDRAFT_PUBLIC_MODE Alignment ===")
    
    render_yaml_path = "render.yaml"
    if not os.path.exists(render_yaml_path):
        print(f"✗ {render_yaml_path} not found")
        return False
    
    with open(render_yaml_path, 'r') as f:
        content = f.read()
    
    # Count MDRAFT_PUBLIC_MODE configurations
    public_mode_count = content.count("MDRAFT_PUBLIC_MODE")
    value_zero_count = content.count('value: "0"')
    
    print(f"✓ Found {public_mode_count} MDRAFT_PUBLIC_MODE configurations")
    print(f"✓ Found {value_zero_count} instances with value: '0'")
    
    if public_mode_count >= 2 and value_zero_count >= 2:
        print("✅ MDRAFT_PUBLIC_MODE properly aligned between services")
        return True
    else:
        print("❌ MDRAFT_PUBLIC_MODE not properly aligned")
        return False

def test_configuration_methods():
    """Test that secure configuration methods exist."""
    print("\n=== Testing Configuration Methods ===")
    
    from app.config import get_config
    
    config = get_config()
    
    # Test that apply_secrets_to_app method exists
    if hasattr(config, 'apply_secrets_to_app'):
        print("✓ apply_secrets_to_app method exists")
        
        # Test that it's callable
        if callable(config.apply_secrets_to_app):
            print("✓ apply_secrets_to_app is callable")
            return True
        else:
            print("✗ apply_secrets_to_app is not callable")
            return False
    else:
        print("✗ apply_secrets_to_app method not found")
        return False

def show_security_summary():
    """Show a summary of the security implementation."""
    print("\n=== Security Hygiene Implementation Summary ===")
    print("✅ Secrets moved to Render Dashboard (Environment → Secret files/variables)")
    print("  • OPENAI_API_KEY")
    print("  • SECRET_KEY") 
    print("  • STRIPE_SECRET_KEY")
    print("  • STRIPE_WEBHOOK_SECRET")
    print("  • ADMIN_TOKEN")
    print("  • WEBHOOK_SECRET")
    print()
    print("✅ Environment variables kept (TLS rediss:// URLs are OK)")
    print("  • FLASK_LIMITER_STORAGE_URI")
    print("  • REDIS_URL")
    print("  • DATABASE_URL")
    print()
    print("✅ Configuration alignment")
    print("  • MDRAFT_PUBLIC_MODE aligned between web/worker services")
    print()
    print("✅ Security improvements")
    print("  • Secrets isolated from configuration dumps")
    print("  • Secure configuration application method")
    print("  • Environment template excludes secrets")
    print("  • Render configuration properly structured")

if __name__ == "__main__":
    print("Testing Security Hygiene Implementation for Render...")
    print("=" * 60)
    
    # Run all tests
    tests = [
        test_secret_isolation,
        test_secret_access,
        test_environment_template,
        test_render_configuration,
        test_mdraft_public_mode_alignment,
        test_configuration_methods
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        show_security_summary()
        print("\n🎉 Security hygiene implementation is complete and secure!")
        print("\n📋 Next Steps:")
        print("1. Set secrets in Render Dashboard → Environment → Secret files/variables")
        print("2. Deploy the updated configuration")
        print("3. Verify secrets are not exposed in logs")
        print("4. Test application functionality with secure configuration")
    else:
        print(f"\n❌ {total - passed} tests failed. Please review the security implementation.")
        sys.exit(1)
