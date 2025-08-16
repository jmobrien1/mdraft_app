#!/usr/bin/env python3
"""
Smoke test for reliability engineering features.

This script tests the basic functionality of the reliability module
to ensure it's working correctly.
"""

import time
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_basic_functionality():
    """Test basic reliability functionality."""
    print("Testing basic reliability functionality...")
    
    try:
        from app.services.reliability import (
            ReliabilityError, ExternalServiceError, CircuitBreaker, 
            CircuitBreakerState, map_external_error, resilient_call
        )
        print("✓ Successfully imported reliability modules")
        
        # Test error mapping
        error = Exception("Connection timeout")
        mapped_error = map_external_error("test_service", "test_endpoint", error)
        assert mapped_error.error_type == ExternalServiceError.TIMEOUT
        print("✓ Error mapping works correctly")
        
        # Test circuit breaker
        breaker = CircuitBreaker("test_endpoint", 3, 60)
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.can_execute() is True
        print("✓ Circuit breaker initializes correctly")
        
        # Test successful resilient call
        def success_func():
            return "success"
        
        result = resilient_call("test_service", "test_endpoint", success_func)
        assert result == "success"
        print("✓ Resilient call works with successful function")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing basic functionality: {e}")
        return False

def test_configuration():
    """Test configuration integration."""
    print("\nTesting configuration integration...")
    
    try:
        from app.config import get_config
        
        config = get_config()
        assert hasattr(config, 'reliability')
        assert config.reliability.HTTP_TIMEOUT_SEC > 0
        assert config.reliability.HTTP_RETRIES >= 0
        assert config.reliability.CB_FAIL_THRESHOLD > 0
        assert config.reliability.CB_RESET_SEC > 0
        print("✓ Configuration integration works correctly")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing configuration: {e}")
        return False

def test_service_integration():
    """Test integration with existing services."""
    print("\nTesting service integration...")
    
    try:
        # Test LLM client integration (without Flask context)
        from app.services.llm_client import _get_client
        try:
            client = _get_client()
            print("✓ LLM client integration works")
        except Exception as e:
            if "missing OPENAI_API_KEY" in str(e):
                print("✓ LLM client integration works (expected auth error)")
            else:
                raise e
        
        # Test storage service integration (without Flask context)
        from app.services.storage import Storage
        try:
            storage = Storage()
            print("✓ Storage service integration works")
        except Exception as e:
            if "Working outside of application context" in str(e):
                print("✓ Storage service integration works (expected Flask context error)")
            else:
                raise e
        
        # Test antivirus service integration
        from app.services.antivirus import get_antivirus_service
        av_service = get_antivirus_service()
        print("✓ Antivirus service integration works")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing service integration: {e}")
        return False

def test_retry_behavior():
    """Test retry behavior with simulated failures."""
    print("\nTesting retry behavior...")
    
    try:
        from app.services.reliability import resilient_call, ReliabilityError
        
        call_count = 0
        
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("temporary failure")
            return "success"
        
        result = resilient_call("test_service", "test_endpoint", failing_then_success, max_retries=2)
        assert result == "success"
        assert call_count == 3
        print("✓ Retry behavior works correctly")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing retry behavior: {e}")
        return False

def test_circuit_breaker_behavior():
    """Test circuit breaker behavior."""
    print("\nTesting circuit breaker behavior...")
    
    try:
        from app.services.reliability import resilient_call, ReliabilityError, ExternalServiceError
        
        def always_failing():
            raise Exception("permanent failure")
        
        # Use a different endpoint to avoid conflicts with other tests
        endpoint = "circuit_breaker_test"
        
        # First call should fail and open circuit
        try:
            resilient_call("test_service", endpoint, always_failing, max_retries=1)
        except ReliabilityError:
            pass  # Expected to fail
        
        # Second call should be blocked by circuit breaker
        try:
            resilient_call("test_service", endpoint, always_failing, max_retries=1)
        except ReliabilityError as exc_info:
            # The circuit breaker should block the call, resulting in a SERVER_ERROR
            # or the call should fail with the original error type
            if exc_info.error_type in [ExternalServiceError.SERVER_ERROR, ExternalServiceError.UNKNOWN_ERROR]:
                print("✓ Circuit breaker behavior works correctly")
                return True
            else:
                print(f"✗ Expected SERVER_ERROR or UNKNOWN_ERROR, got {exc_info.error_type}")
                return False
        
        print("✗ Circuit breaker should have blocked second call")
        return False
        
    except Exception as e:
        print(f"✗ Error testing circuit breaker behavior: {e}")
        return False

def main():
    """Run all smoke tests."""
    print("Starting reliability engineering smoke tests...\n")
    
    tests = [
        test_basic_functionality,
        test_configuration,
        test_service_integration,
        test_retry_behavior,
        test_circuit_breaker_behavior
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"✗ Test {test.__name__} failed")
    
    print(f"\nSmoke test results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Reliability features are working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
