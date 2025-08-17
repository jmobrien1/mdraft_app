#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== Pre-deployment setup ==="

# Set fallback session backend for pre-deployment
export SESSION_BACKEND="${SESSION_BACKEND:-filesystem}"
export SESSION_TYPE="${SESSION_TYPE:-filesystem}"

echo "SESSION_BACKEND=$SESSION_BACKEND"
echo "SESSION_TYPE=$SESSION_TYPE"

echo "=== Pre-deployment setup complete ==="
