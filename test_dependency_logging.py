#!/usr/bin/env python3
"""
Test script to verify dependency logging works correctly.
This tests that the dependency version logging is working during app startup.
"""

import os
import sys
import logging

# Set minimal environment variables for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

def test_dependency_logging():
    """Test that dependency logging works during app startup."""
    print("🔧 TESTING DEPENDENCY LOGGING")
    print("=" * 35)
    
    # Capture logs to verify dependency logging
    log_capture = []
    
    class LogCaptureHandler(logging.Handler):
        def emit(self, record):
            log_capture.append(self.format(record))
    
    # Set up logging capture
    logger = logging.getLogger()
    handler = LogCaptureHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        from app import create_app
        
        print("✅ App imports successful")
        
        # Create app (this should trigger dependency logging)
        app = create_app()
        print("✅ App creation successful")
        
        # Check if dependency logging was captured
        print("\n📋 Dependency logging output:")
        dependency_logs = [log for log in log_capture if "Dependency Version Check" in log or "pypdf" in log or "openai" in log or "google-cloud-storage" in log or "stripe" in log]
        
        if dependency_logs:
            for log in dependency_logs:
                print(f"   {log}")
            
            # Check for specific dependencies
            pypdf_logs = [log for log in dependency_logs if "pypdf" in log]
            openai_logs = [log for log in dependency_logs if "openai" in log]
            gcs_logs = [log for log in dependency_logs if "google-cloud-storage" in log]
            stripe_logs = [log for log in dependency_logs if "stripe" in log]
            
            print(f"\n🎯 Dependency Status:")
            print(f"  • pypdf: {'✅' if pypdf_logs and 'not importable' not in str(pypdf_logs) else '❌'}")
            print(f"  • openai: {'✅' if openai_logs and 'not importable' not in str(openai_logs) else '❌'}")
            print(f"  • google-cloud-storage: {'✅' if gcs_logs and 'not importable' not in str(gcs_logs) else '❌'}")
            print(f"  • stripe: {'✅' if stripe_logs and 'not importable' not in str(stripe_logs) else '❌'}")
            
            # Verify that at least the critical dependencies are available
            critical_deps_available = (
                pypdf_logs and 'not importable' not in str(pypdf_logs) and
                openai_logs and 'not importable' not in str(openai_logs)
            )
            
            if critical_deps_available:
                print("  ✅ Critical dependencies available")
                return True
            else:
                print("  ❌ Critical dependencies missing")
                return False
        else:
            print("  ❌ No dependency logging captured")
            return False
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up logging
        logger.removeHandler(handler)

def test_requirements_installation():
    """Test that required packages are actually installed."""
    print("\n🔧 TESTING REQUIREMENTS INSTALLATION")
    print("=" * 40)
    
    required_packages = [
        ("pypdf", "4.2.0"),
        ("openai", "1.30.0"),
        ("google.cloud.storage", None),  # Just check if importable
        ("stripe", None),  # Just check if importable
    ]
    
    all_available = True
    
    for package, min_version in required_packages:
        try:
            if "." in package:
                # Handle dotted imports like google.cloud.storage
                module_parts = package.split(".")
                module = __import__(package, fromlist=[module_parts[-1]])
            else:
                module = __import__(package)
            
            if min_version:
                version = getattr(module, "__version__", "unknown")
                print(f"   ✅ {package} {version}")
                
                # Simple version check (this is basic, but works for our needs)
                if version != "unknown" and version < min_version:
                    print(f"   ⚠️  {package} version {version} may be too old (need >= {min_version})")
                    all_available = False
            else:
                print(f"   ✅ {package} available")
                
        except ImportError as e:
            print(f"   ❌ {package} not available: {e}")
            all_available = False
        except Exception as e:
            print(f"   ⚠️  {package} error: {e}")
            all_available = False
    
    return all_available

if __name__ == "__main__":
    success1 = test_dependency_logging()
    success2 = test_requirements_installation()
    
    print(f"\n🎯 SUMMARY:")
    print(f"  • Dependency logging: {'✅' if success1 else '❌'}")
    print(f"  • Requirements installation: {'✅' if success2 else '❌'}")
    
    if success1 and success2:
        print("\n🎉 DEPENDENCY LOGGING VERIFIED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
