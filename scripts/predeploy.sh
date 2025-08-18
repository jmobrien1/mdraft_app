#!/bin/bash
set -euo pipefail

echo "=== MDraft Pre-deployment Script ==="
echo "Timestamp: $(date)"
echo "Working directory: $(pwd)"
echo "Python version: $(python3 --version)"

# Function to run with timeout and logging
run_with_timeout() {
    local cmd="$1"
    local timeout_seconds="$2"
    local description="$3"
    
    echo ">>> $description"
    echo "Command: $cmd"
    echo "Timeout: ${timeout_seconds}s"
    
    # Use gtimeout on macOS if available, otherwise use timeout
    if command -v gtimeout >/dev/null 2>&1; then
        if gtimeout "$timeout_seconds" bash -c "$cmd"; then
            echo "✅ $description completed successfully"
            return 0
        else
            echo "❌ $description failed or timed out"
            return 1
        fi
    elif command -v timeout >/dev/null 2>&1; then
        if timeout "$timeout_seconds" bash -c "$cmd"; then
            echo "✅ $description completed successfully"
            return 0
        else
            echo "❌ $description failed or timed out"
            return 1
        fi
    else
        # Fallback: run without timeout
        echo "⚠️  No timeout command available, running without timeout"
        if bash -c "$cmd"; then
            echo "✅ $description completed successfully"
            return 0
        else
            echo "❌ $description failed"
            return 1
        fi
    fi
}

# Test Flask app can import
run_with_timeout "python3 -c 'from app import create_app; print(\"App import successful\")'" 30 "Flask app import test"

# Test database connection
run_with_timeout "DATABASE_URL=\"sqlite:///:memory:\" python3 -c 'from app import create_app; app=create_app(); app.app_context().push(); from app import db; from sqlalchemy import text; db.session.execute(text(\"SELECT 1\")); print(\"DB connection successful\")'" 30 "Database connection test"

# Run critical auth and health tests
run_with_timeout "DATABASE_URL=\"sqlite:///:memory:\" python3 -m pytest tests/test_auth_and_health.py -v --tb=short" 60 "Auth and health tests"

# Skip migrations for in-memory database (used in testing)
echo ">>> Skipping migrations for in-memory database"
echo "✅ Database migrations skipped (in-memory database)"

echo "=== Pre-deployment completed successfully ==="
