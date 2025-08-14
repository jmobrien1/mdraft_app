#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-}"
if [[ -z "$PORT" ]]; then
  PORT="10000"
  echo "[start-web] PORT was empty; using fallback ${PORT}"
else
  echo "[start-web] PORT=${PORT}"
fi

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
echo "[start-web] WEB_CONCURRENCY=${WEB_CONCURRENCY}"

exec gunicorn run:app \
  --workers "${WEB_CONCURRENCY}" \
  --threads 2 \
  --timeout 120 \
  --bind "0.0.0.0:${PORT}"
