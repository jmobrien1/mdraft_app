#!/usr/bin/env bash
# Smoke test for mdraft application (shell version)
# 
# This script performs a basic smoke test using curl:
# 1. Health check
# 2. Login (if credentials provided)
# 3. Basic API endpoints test

set -euo pipefail

# Configuration
BASE_URL="${SMOKE_TEST_URL:-http://localhost:5000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_step() {
    echo -e "\n${BLUE}🔍 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

test_endpoint() {
    local step="$1"
    local method="$2"
    local url="$3"
    local data="${4:-}"
    local expected_status="${5:-200}"
    
    print_step "$step"
    echo "   Method: $method"
    echo "   URL: $url"
    
    local response
    local status_code
    
    if [[ -n "$data" ]]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json" \
            -d "$data" 2>/dev/null || echo -e "\n000")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
            -H "Accept: application/json" 2>/dev/null || echo -e "\n000")
    fi
    
    status_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | head -n -1)
    
    echo "   Status: $status_code"
    
    if [[ "$status_code" == "$expected_status" ]]; then
        print_success "$step"
        if [[ -n "$response_body" ]]; then
            echo "   Response: $response_body"
        fi
        return 0
    else
        print_error "$step (expected $expected_status, got $status_code)"
        if [[ -n "$response_body" ]]; then
            echo "   Response: $response_body"
        fi
        return 1
    fi
}

# Main smoke test
main() {
    echo "🧪 Starting Smoke Test (Shell Version)"
    echo "=================================================="
    echo "Base URL: $BASE_URL"
    echo "Admin Email: $ADMIN_EMAIL"
    
    local passed=0
    local failed=0
    
    # Test 1: Health Check
    if test_endpoint "Health Check" "GET" "$BASE_URL/health"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Test 2: Ready Check
    if test_endpoint "Ready Check" "GET" "$BASE_URL/readyz"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Test 3: API Health Check
    if test_endpoint "API Health Check" "GET" "$BASE_URL/api/ops/health"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Test 4: Migration Status (should return 401 - requires auth)
    if test_endpoint "Migration Status (Auth Required)" "GET" "$BASE_URL/api/ops/migration_status" "" "401"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Test 5: Proposals List (should return 401 - requires auth)
    if test_endpoint "Proposals List (Auth Required)" "GET" "$BASE_URL/api/agents/compliance-matrix/proposals" "" "401"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Test 6: Convert Endpoint (should return 401 - requires auth)
    if test_endpoint "Convert Endpoint (Auth Required)" "POST" "$BASE_URL/api/convert" "" "401"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Test 7: Worker Ping (should return 401 - requires auth)
    if test_endpoint "Worker Ping (Auth Required)" "POST" "$BASE_URL/api/ops/ping" '{"message":"test"}' "401"; then
        ((passed++))
    else
        ((failed++))
    fi
    
    # Summary
    echo -e "\n=================================================="
    echo "📊 SMOKE TEST SUMMARY"
    echo "=================================================="
    echo "Results: $passed passed, $failed failed"
    
    if [[ $failed -eq 0 ]]; then
        print_success "All basic tests passed! Deployment looks good."
        echo ""
        echo "Note: This shell version only tests basic connectivity."
        echo "For full end-to-end testing, run: python scripts/smoke_test.py"
        return 0
    else
        print_error "Some tests failed. Check the logs above."
        return 1
    fi
}

# Run the smoke test
main "$@"
