#!/usr/bin/env python3
"""
Build validation script for mdraft_app
Validates critical dependencies, compatibility, and security requirements
"""

import sys
import subprocess
from pathlib import Path

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print(f"{'='*50}")

def print_success(message):
    """Print a success message"""
    print(f"✅ {message}")

def print_error(message):
    """Print an error message"""
    print(f"❌ {message}")

def print_warning(message):
    """Print a warning message"""
    print(f"⚠️  {message}")

def check_package_version(package_name, expected_version=None):
    """Check if a package is installed and optionally verify version"""
    try:
        module = __import__(package_name)
        version = getattr(module, '__version__', 'unknown')
        print_success(f"{package_name} {version} is installed")
        if expected_version and version != expected_version:
            print_warning(f"{package_name} version {version} differs from expected {expected_version}")
        return True
    except ImportError:
        print_error(f"{package_name} is not installed")
        return False

def check_import(import_statement, description):
    """Check if an import statement works"""
    try:
        exec(import_statement)
        print_success(f"{description} - import successful")
        return True
    except ImportError as e:
        print_error(f"{description} - import failed: {e}")
        return False
    except Exception as e:
        print_error(f"{description} - unexpected error: {e}")
        return False

def run_command(cmd, description):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        print_success(f"{description} - command successful")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"{description} - command failed: {e.stderr}")
        return False

def main():
    """Main validation function"""
    print_header("mdraft_app Build Validation")
    
    all_checks_passed = True
    
    # Check Python version
    print_header("Python Environment")
    python_version = sys.version_info
    print_success(f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print_error("Python 3.8+ is required")
        all_checks_passed = False
    
    # Check critical packages
    print_header("Critical Dependencies")
    
    # Flask and core dependencies
    flask_checks = [
        ("flask", "3.0.3"),
        ("gunicorn", "22.0.0"),
        ("flask_sqlalchemy", "3.1.1"),
        ("flask_migrate", "4.0.7"),
        ("alembic", "1.13.1"),
    ]
    
    for package, version in flask_checks:
        if not check_package_version(package, version):
            all_checks_passed = False
    
    # Security-critical packages
    print_header("Security-Critical Packages")
    security_checks = [
        ("itsdangerous", "2.1.2"),
        ("werkzeug", "3.0.1"),
    ]
    
    for package, version in security_checks:
        if not check_package_version(package, version):
            all_checks_passed = False
    
    # Celery and Redis compatibility
    print_header("Async Processing")
    celery_checks = [
        ("celery", "5.4.0"),
        ("redis", "5.0.7"),
    ]
    
    for package, version in celery_checks:
        if not check_package_version(package, version):
            all_checks_passed = False
    
    # Test Celery/Redis compatibility
    if check_import("import celery; import redis", "Celery/Redis compatibility"):
        try:
            import celery
            import redis
            print_success(f"Celery {celery.__version__} and Redis {redis.__version__} are compatible")
        except Exception as e:
            print_error(f"Celery/Redis compatibility check failed: {e}")
            all_checks_passed = False
    
    # Google Cloud packages
    print_header("Google Cloud Services")
    gcp_imports = [
        ("from google.cloud import storage", "Google Cloud Storage"),
        ("from google.cloud import tasks", "Google Cloud Tasks"),
        ("from google.cloud import secretmanager", "Google Secret Manager"),
        ("from google.cloud import documentai", "Google Document AI"),
        ("from google.cloud import aiplatform", "Google Vertex AI"),
    ]
    
    for import_stmt, description in gcp_imports:
        if not check_import(import_stmt, description):
            all_checks_passed = False
    
    # Check requirements files
    print_header("Requirements Files")
    requirements_files = [
        "requirements.txt",
        "requirements.in",
        "requirements-dev.txt",
        "requirements-dev.in",
    ]
    
    for file_path in requirements_files:
        if Path(file_path).exists():
            print_success(f"{file_path} exists")
        else:
            print_error(f"{file_path} not found")
            all_checks_passed = False
    
    # Check pip-tools availability
    print_header("Build Tools")
    if run_command("pip-compile --version", "pip-compile availability"):
        print_success("pip-tools is available for dependency locking")
    else:
        print_warning("pip-tools not available - install with: pip install pip-tools")
    
    # Check security tools
    security_tools = [
        ("pip-audit --version", "pip-audit"),
        ("safety --version", "safety"),
    ]
    
    for cmd, tool in security_tools:
        if run_command(cmd, f"{tool} availability"):
            print_success(f"{tool} is available for security scanning")
        else:
            print_warning(f"{tool} not available - install with: pip install {tool}")
    
    # Final summary
    print_header("Validation Summary")
    
    if all_checks_passed:
        print_success("All critical checks passed!")
        print("\n🎉 Build validation completed successfully")
        print("\n💡 Next steps:")
        print("  make lock        # Lock production dependencies")
        print("  make lock-dev    # Lock development dependencies")
        print("  make security-scan # Run security validation")
        return True
    else:
        print_error("Some checks failed - please review the errors above")
        print("\n🔧 Troubleshooting:")
        print("  1. Install missing packages: pip install -r requirements.txt")
        print("  2. Install dev tools: pip install -r requirements-dev.txt")
        print("  3. Check Python version: python3 --version")
        print("  4. Verify virtual environment is activated")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
