#!/usr/bin/env bash
set -euo pipefail

bash "$(dirname "$0")/check-required-env.sh" cloud

PY_API_PORT="${PY_API_PORT:-8000}"
SIDECAR_PORT="${SIDECAR_PORT:-3001}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=== Cloud baseline security notice ==="
echo "PRIVATE_NETWORK_ONLY=true (validated)"
echo "ALLOWLIST_CIDRS=${ALLOWLIST_CIDRS}"
echo "Recommendation: expose services only via private network + allowlist gateway rules."
echo "No-login stage requirement: do NOT expose Sidecar/Python API directly to public internet by default."
echo
echo "=== Cloud baseline startup templates ==="
echo "[1] Build React Web: npm --prefix frontend run build"
echo "[2] Nest Sidecar (private bind): npm --prefix frontend/api run build && HOST=127.0.0.1 PORT=${SIDECAR_PORT} npm --prefix frontend/api run start"
echo "[3] Python API + Web shell (private bind): SIDECAR_BASE_URL=http://127.0.0.1:${SIDECAR_PORT} PYTHONPATH=. ${PYTHON_BIN} -m uvicorn src.api.main:app --host 127.0.0.1 --port ${PY_API_PORT}"
echo
echo "=== Cloud health-check templates ==="
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/health"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/api/v1/diagnostics/runtime"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/sidecar/health"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/sidecar/ready"
echo
echo "=== Cloud smoke templates (health + key query) ==="
echo "bash scripts/deployment/cloud-smoke-check.sh"
echo "bash scripts/deployment/cloud-network-fail-sim.sh"
