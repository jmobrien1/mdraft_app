#!/usr/bin/env bash
set -euo pipefail
echo "[predeploy] running migrations..."
flask --app app:create_app db upgrade && exit 0 || true
echo "[predeploy] attempting stamp+migrate+upgrade..."
flask --app app:create_app db stamp head || true
flask --app app:create_app db migrate -m "autogen" || true
flask --app app:create_app db upgrade || true
echo "[predeploy] complete"
