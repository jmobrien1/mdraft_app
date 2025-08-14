#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://mdraft-web.onrender.com}"

# Print JSON body to stdout (no trailers). Safe to pipe into jq.
curl_json() {
  local method="${1:-GET}"
  local path="$2"
  local data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -X "$method" "$BASE_URL$path" \
      -H 'Content-Type: application/json' \
      -d "$data"
  else
    curl -sS -X "$method" "$BASE_URL$path" \
      -H 'Accept: application/json'
  fi
}

# Save body separately; print status to stderr. Keeps body clean for jq.
curl_json_with_status() {
  local method="${1:-GET}"
  local path="$2"
  local data="${3:-}"
  local body="/tmp/mdraft_body.json"
  local code
  if [[ -n "$data" ]]; then
    code=$(curl -sS -o "$body" -w '%{http_code}' \
      -X "$method" "$BASE_URL$path" \
      -H 'Content-Type: application/json' \
      -d "$data")
  else
    code=$(curl -sS -o "$body" -w '%{http_code}' \
      -X "$method" "$BASE_URL$path" \
      -H 'Accept: application/json')
  fi
  echo "HTTP:$code" >&2
  cat "$body"
}

# ----- mdraft shortcuts -----

smoke_criteria() {
  curl_json POST "/api/dev/gen-smoke" '{"tool":"criteria"}' | jq .
}

smoke_outline() {
  curl_json POST "/api/dev/gen-smoke" '{"tool":"outline"}' | jq .
}

gen_eval() {
  local doc_id="${1:-}"
  if [[ -z "$doc_id" ]]; then
    echo "Usage: gen_eval <DOCUMENT_ID>" >&2
    return 2
  fi
  curl_json POST "/api/generate/evaluation-criteria" "{\"document_id\":\"$doc_id\"}" | jq .
}

# health + prompts checks
health() { curl_json GET "/healthz" | jq .; }
check_prompts() { curl_json GET "/api/dev/check-prompts" | jq .; }
