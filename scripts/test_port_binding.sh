#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== Testing Port Binding ==="
echo "PORT=$PORT"

# Test if port is bound
echo "Checking if port $PORT is bound..."
ss -ltnp | grep ":$PORT" || echo "Port $PORT not bound yet"

# Test health endpoint
echo "Testing health endpoint..."
curl -sS -I "http://127.0.0.1:$PORT/health/simple" | head -n1 || echo "Health endpoint not responding"

echo "=== Port Binding Test Complete ==="
