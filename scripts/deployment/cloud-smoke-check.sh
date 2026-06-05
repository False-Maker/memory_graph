#!/usr/bin/env bash
set -euo pipefail

PY_API_PORT="${PY_API_PORT:-8000}"
SIDECAR_PORT="${SIDECAR_PORT:-3001}"

echo "[cloud-smoke] checking frontend shell: http://127.0.0.1:${PY_API_PORT}/"
curl -sf "http://127.0.0.1:${PY_API_PORT}/" > /dev/null

echo "[cloud-smoke] checking python health: http://127.0.0.1:${PY_API_PORT}/health"
curl -sf "http://127.0.0.1:${PY_API_PORT}/health" > /dev/null

echo "[cloud-smoke] checking runtime diagnostics: http://127.0.0.1:${PY_API_PORT}/api/v1/diagnostics/runtime"
curl -sf "http://127.0.0.1:${PY_API_PORT}/api/v1/diagnostics/runtime" > /dev/null

echo "[cloud-smoke] checking sidecar health via proxy: http://127.0.0.1:${PY_API_PORT}/sidecar/health"
curl -sf "http://127.0.0.1:${PY_API_PORT}/sidecar/health" > /dev/null

echo "[cloud-smoke] checking sidecar ready via proxy: http://127.0.0.1:${PY_API_PORT}/sidecar/ready"
curl -sf "http://127.0.0.1:${PY_API_PORT}/sidecar/ready" > /dev/null

echo "[cloud-smoke] checking key query endpoint: http://127.0.0.1:${PY_API_PORT}/api/v1/query"
http_code="$(curl -s -o /tmp/cloud-smoke-query.json -w '%{http_code}' \
  -X POST "http://127.0.0.1:${PY_API_PORT}/api/v1/query" \
  -H 'Content-Type: application/json' \
  -d '{"question":"cloud smoke check","strategy":"graphrag","top_k":1,"include_sources":false}')"

if [[ "$http_code" != "200" ]]; then
  echo "[cloud-smoke] key query failed: HTTP ${http_code}" >&2
  if [[ -f /tmp/cloud-smoke-query.json ]]; then
    cat /tmp/cloud-smoke-query.json >&2
  fi
  exit 1
fi

echo "[cloud-smoke] key query passed: HTTP ${http_code}"
echo "[cloud-smoke] all checks passed"
