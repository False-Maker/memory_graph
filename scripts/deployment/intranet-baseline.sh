#!/usr/bin/env bash
set -euo pipefail

bash "$(dirname "$0")/check-required-env.sh" intranet

PY_API_PORT="${PY_API_PORT:-8000}"
SIDECAR_PORT="${SIDECAR_PORT:-3001}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=== Intranet baseline startup templates ==="
echo "[1] Build React Web: npm --prefix frontend run build"
echo "[2] Nest Sidecar: npm --prefix frontend/api run build && HOST=127.0.0.1 PORT=${SIDECAR_PORT} npm --prefix frontend/api run start"
echo "[3] Python API + Web shell: SIDECAR_BASE_URL=http://127.0.0.1:${SIDECAR_PORT} PYTHONPATH=. ${PYTHON_BIN} -m uvicorn src.api.main:app --host 127.0.0.1 --port ${PY_API_PORT}"
echo
echo "=== Intranet health-check templates ==="
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/health"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/api/v1/diagnostics/runtime"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/sidecar/health"
echo "curl -sf http://127.0.0.1:${PY_API_PORT}/sidecar/ready"
echo
echo "=== Intranet single-node runnable flow (T15) ==="
echo "cp scripts/deployment/.env.intranet.example .env.intranet"
echo "bash scripts/deployment/intranet-single-node-start.sh"
echo "bash scripts/deployment/intranet-health-check.sh"
echo "bash scripts/deployment/mcp-health-check.sh  # optional when MCP 单独部署"
echo "bash scripts/deployment/intranet-single-node-stop.sh"
