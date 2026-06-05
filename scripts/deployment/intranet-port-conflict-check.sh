#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.intranet"
EXTERNAL_PY_API_PORT="${PY_API_PORT:-}"
EXTERNAL_PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -n "${EXTERNAL_PY_API_PORT}" ]]; then
  PY_API_PORT="${EXTERNAL_PY_API_PORT}"
fi
if [[ -n "${EXTERNAL_PYTHON_BIN}" ]]; then
  PYTHON_BIN="${EXTERNAL_PYTHON_BIN}"
fi

PY_API_PORT="${PY_API_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" - "${PY_API_PORT}" <<'PY' &
import socket
import sys
import time

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", port))
s.listen(1)
time.sleep(8)
PY

holder_pid=$!
set +e
bash "${ROOT_DIR}/scripts/deployment/intranet-single-node-start.sh"
rc=$?
set -e

kill "${holder_pid}" 2>/dev/null || true
wait "${holder_pid}" 2>/dev/null || true

if [[ ${rc} -eq 0 ]]; then
  echo "Expected port conflict failure but startup succeeded" >&2
  exit 1
fi

echo "Port conflict check passed (startup failed as expected)."
