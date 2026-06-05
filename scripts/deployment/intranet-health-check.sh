#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.intranet"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"
EXTERNAL_PY_API_PORT="${PY_API_PORT:-}"
EXTERNAL_SIDECAR_PORT="${SIDECAR_PORT:-}"

mkdir -p "${RUNTIME_DIR}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -n "${EXTERNAL_PY_API_PORT}" ]]; then
  PY_API_PORT="${EXTERNAL_PY_API_PORT}"
fi
if [[ -n "${EXTERNAL_SIDECAR_PORT}" ]]; then
  SIDECAR_PORT="${EXTERNAL_SIDECAR_PORT}"
fi

PY_API_PORT="${PY_API_PORT:-8000}"
SIDECAR_PORT="${SIDECAR_PORT:-3001}"

echo "[health] React Web shell via Python API"
curl -sf "http://127.0.0.1:${PY_API_PORT}/" >/dev/null
echo "frontend shell: OK"
echo

echo "[health] Python API"
curl -sf "http://127.0.0.1:${PY_API_PORT}/health"
echo

echo "[health] Runtime diagnostics"
curl -sf "http://127.0.0.1:${PY_API_PORT}/api/v1/diagnostics/runtime"
echo

echo "[health] Sidecar /health via Python API proxy"
curl -sf "http://127.0.0.1:${PY_API_PORT}/sidecar/health"
echo

echo "[health] Sidecar /ready via Python API proxy"
curl -sf "http://127.0.0.1:${PY_API_PORT}/sidecar/ready"
echo

echo "[smoke] key endpoint reachability: POST /api/v1/query"
query_out_file="${RUNTIME_DIR}/task15-query-smoke.json"
query_status="$(curl -s -o "${query_out_file}" -w '%{http_code}' \
  -X POST "http://127.0.0.1:${PY_API_PORT}/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{}')"

if [[ "${query_status}" != "422" ]]; then
  echo "query smoke failed: expected HTTP 422 from schema validation, got ${query_status}" >&2
  cat "${query_out_file}" >&2 || true
  exit 1
fi

echo "query smoke: HTTP ${query_status} (expected)"
