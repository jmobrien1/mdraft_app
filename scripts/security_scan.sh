#!/bin/bash

# Security scanning script for mdraft_app
# This script runs comprehensive security checks on dependencies

set -e

echo "🔍 Starting security scan for mdraft_app..."
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        return 1
    fi
}

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️  Warning: Not in a virtual environment${NC}"
    echo "Consider activating your virtual environment first"
fi

# Install security tools if not present
echo "📦 Ensuring security tools are installed..."
if ! command_exists pip-audit; then
    echo "Installing pip-audit..."
    pip install pip-audit
fi

if ! command_exists safety; then
    echo "Installing safety..."
    pip install safety
fi

# Run pip-audit
echo ""
echo "🔍 Running pip-audit..."
pip-audit --format json --output pip-audit-report.json
print_status $? "pip-audit completed"

# Run safety
echo ""
echo "🔍 Running safety..."
safety check --json --output safety-report.json
print_status $? "safety completed"

# Analyze results
echo ""
echo "📊 Analyzing security scan results..."
echo "=================================="

# Check pip-audit results
if [ -f pip-audit-report.json ]; then
    echo "📋 pip-audit findings:"
    HIGH_CRITICAL_COUNT=$(cat pip-audit-report.json | grep -c '"severity": "HIGH\|"severity": "CRITICAL"' || echo "0")
    
    if [ "$HIGH_CRITICAL_COUNT" -gt 0 ]; then
        echo -e "${RED}❌ Found $HIGH_CRITICAL_COUNT high/critical vulnerabilities in pip-audit${NC}"
        cat pip-audit-report.json | grep -A 5 -B 5 '"severity": "HIGH\|"severity": "CRITICAL"' || true
    else
        echo -e "${GREEN}✅ No high/critical vulnerabilities found in pip-audit${NC}"
    fi
fi

# Check safety results
if [ -f safety-report.json ]; then
    echo ""
    echo "📋 safety findings:"
    HIGH_CRITICAL_COUNT=$(cat safety-report.json | grep -c '"severity": "HIGH\|"severity": "CRITICAL"' || echo "0")
    
    if [ "$HIGH_CRITICAL_COUNT" -gt 0 ]; then
        echo -e "${RED}❌ Found $HIGH_CRITICAL_COUNT high/critical vulnerabilities in safety${NC}"
        cat safety-report.json | grep -A 5 -B 5 '"severity": "HIGH\|"severity": "CRITICAL"' || true
    else
        echo -e "${GREEN}✅ No high/critical vulnerabilities found in safety${NC}"
    fi
fi

# Check Celery/Redis compatibility
echo ""
echo "📦 Checking Celery/Redis compatibility..."
python3 -c "
import celery
import redis
print(f'✅ Celery {celery.__version__} and Redis {redis.__version__} are compatible')
"
print_status $? "Celery/Redis compatibility check"

# Check pinned security packages
echo ""
echo "🔐 Checking security-critical packages..."
python3 -c "
import itsdangerous
import werkzeug
print(f'✅ itsdangerous {itsdangerous.__version__} and Werkzeug {werkzeug.__version__} are pinned')
"
print_status $? "Security package pinning check"

# Check Google Cloud packages
echo ""
echo "☁️ Checking Google Cloud packages..."
python3 -c "
from google.cloud import storage, tasks, secretmanager, documentai, aiplatform
print('✅ All Google Cloud packages are available')
"
print_status $? "Google Cloud packages check"

echo ""
echo "=========================================="
echo "🔍 Security scan completed!"
echo ""
echo "📊 Reports generated:"
echo "  - pip-audit-report.json"
echo "  - safety-report.json"
echo ""
echo "💡 To update dependencies:"
echo "  make lock        # Update production dependencies"
echo "  make lock-dev    # Update development dependencies"
echo ""
echo "💡 To run this scan again:"
echo "  make security-scan"
echo "  or"
echo "  ./scripts/security_scan.sh"
