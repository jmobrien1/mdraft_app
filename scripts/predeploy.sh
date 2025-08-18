#!/bin/bash
set -euo pipefail

echo "=== MDraft Pre-deployment Script ==="
echo "Timestamp: $(date)"
echo "Working directory: $(pwd)"
echo "Python version: $(python --version)"

# Function to run with timeout and logging
run_with_timeout() {
    local cmd="$1"
    local timeout_seconds="$2"
    local description="$3"
    
    echo ">>> $description"
    echo "Command: $cmd"
    echo "Timeout: ${timeout_seconds}s"
    
    if timeout "$timeout_seconds" bash -c "$cmd"; then
        echo "✅ $description completed successfully"
        return 0
    else
        echo "❌ $description failed or timed out"
        return 1
    fi
}

# Test Flask app can import
run_with_timeout "python -c 'from app import create_app; print(\"App import successful\")'" 30 "Flask app import test"

# Test database connection
run_with_timeout "python -c 'from app import create_app; app=create_app(); app.app_context().push(); from app import db; from sqlalchemy import text; db.session.execute(text(\"SELECT 1\")); print(\"DB connection successful\")'" 30 "Database connection test"

# Run migrations
run_with_timeout "flask --app app:create_app db upgrade" 120 "Database migrations"

echo "=== Pre-deployment completed successfully ==="
