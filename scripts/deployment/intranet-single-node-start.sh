#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"
ENV_FILE="${ROOT_DIR}/.env.intranet"
EXTERNAL_PY_API_PORT="${PY_API_PORT:-}"
EXTERNAL_SIDECAR_PORT="${SIDECAR_PORT:-}"
EXTERNAL_PYTHON_BIN="${PYTHON_BIN:-}"

mkdir -p "${PID_DIR}" "${LOG_DIR}"

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
if [[ -n "${EXTERNAL_PYTHON_BIN}" ]]; then
  PYTHON_BIN="${EXTERNAL_PYTHON_BIN}"
fi

bash "${ROOT_DIR}/scripts/deployment/check-required-env.sh" intranet

PY_API_PORT="${PY_API_PORT:-8000}"
SIDECAR_PORT="${SIDECAR_PORT:-3001}"
SIDECAR_PID_FILE="${PID_DIR}/sidecar.pid"
PY_API_PID_FILE="${PID_DIR}/py-api.pid"

detect_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s\n' "${PYTHON_BIN}"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi

  printf '%s\n' "python3"
}

PYTHON_BIN="${PYTHON_BIN:-$(detect_python_bin)}"

assert_port_free() {
  local port="$1"
  if "${PYTHON_BIN}" - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
  then
    return 0
  fi

  echo "Port conflict detected: 127.0.0.1:${port} is already in use" >&2
  echo "Resolve the conflict or override ports in .env.intranet" >&2
  exit 1
}

assert_port_free "${PY_API_PORT}"
assert_port_free "${SIDECAR_PORT}"
echo "Starting intranet single-node services..."

rm -f "${SIDECAR_PID_FILE}" "${PY_API_PID_FILE}"

echo "Building React Web frontend..."
npm --prefix frontend run build >"${LOG_DIR}/frontend-build.log" 2>&1

echo "Building Nest sidecar..."
npm --prefix frontend/api run build >"${LOG_DIR}/sidecar-build.log" 2>&1

nohup env \
  HOST=127.0.0.1 \
  PORT="${SIDECAR_PORT}" \
  BACKEND_BASE_URL="http://127.0.0.1:${PY_API_PORT}" \
  npm --prefix frontend/api run start >"${LOG_DIR}/sidecar.log" 2>&1 < /dev/null &
echo $! >"${SIDECAR_PID_FILE}"

nohup env \
  SIDECAR_BASE_URL="http://127.0.0.1:${SIDECAR_PORT}" \
  PYTHONPATH=. \
  "${PYTHON_BIN}" -m uvicorn src.api.main:app --host 127.0.0.1 --port "${PY_API_PORT}" >"${LOG_DIR}/py-api.log" 2>&1 < /dev/null &
echo $! >"${PY_API_PID_FILE}"

echo "Started with ports: PY=${PY_API_PORT}, SIDECAR=${SIDECAR_PORT}"
echo "Logs: ${LOG_DIR}"
