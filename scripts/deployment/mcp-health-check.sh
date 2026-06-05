#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_INTRANET_FILE="${ROOT_DIR}/.env.intranet"
ENV_MCP_FILE="${ROOT_DIR}/.env.mcp"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"

EXTERNAL_MCP_HOST="${MEMORY_GRAPH_MCP_HOST:-${MCP_HOST:-}}"
EXTERNAL_MCP_PORT="${MEMORY_GRAPH_MCP_PORT:-${MCP_PORT:-}}"
EXTERNAL_MCP_STREAMABLE_HTTP_PATH="${MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH:-${MCP_STREAMABLE_HTTP_PATH:-}}"
EXTERNAL_MCP_STARTUP_TIMEOUT_SECONDS="${MCP_STARTUP_TIMEOUT_SECONDS:-}"
EXTERNAL_MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN:-}"
EXTERNAL_PYTHON_BIN="${PYTHON_BIN:-}"
EXTERNAL_MCP_PYTHONPATH="${MCP_PYTHONPATH:-}"

mkdir -p "${RUNTIME_DIR}"

if [[ -f "${ENV_INTRANET_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_INTRANET_FILE}"
  set +a
fi

if [[ -f "${ENV_MCP_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_MCP_FILE}"
  set +a
fi

if [[ -n "${EXTERNAL_MCP_HOST}" ]]; then
  MEMORY_GRAPH_MCP_HOST="${EXTERNAL_MCP_HOST}"
fi
if [[ -n "${EXTERNAL_MCP_PORT}" ]]; then
  MEMORY_GRAPH_MCP_PORT="${EXTERNAL_MCP_PORT}"
fi
if [[ -n "${EXTERNAL_MCP_STREAMABLE_HTTP_PATH}" ]]; then
  MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH="${EXTERNAL_MCP_STREAMABLE_HTTP_PATH}"
fi
if [[ -n "${EXTERNAL_MCP_STARTUP_TIMEOUT_SECONDS}" ]]; then
  MCP_STARTUP_TIMEOUT_SECONDS="${EXTERNAL_MCP_STARTUP_TIMEOUT_SECONDS}"
fi
if [[ -n "${EXTERNAL_MCP_BEARER_TOKEN}" ]]; then
  MEMORY_GRAPH_MCP_BEARER_TOKEN="${EXTERNAL_MCP_BEARER_TOKEN}"
fi
if [[ -n "${EXTERNAL_PYTHON_BIN}" ]]; then
  PYTHON_BIN="${EXTERNAL_PYTHON_BIN}"
fi
if [[ -n "${EXTERNAL_MCP_PYTHONPATH}" ]]; then
  MCP_PYTHONPATH="${EXTERNAL_MCP_PYTHONPATH}"
fi

MCP_HOST="${MEMORY_GRAPH_MCP_HOST:-${MCP_HOST:-127.0.0.1}}"
MCP_PORT="${MEMORY_GRAPH_MCP_PORT:-${MCP_PORT:-8001}}"
MCP_STREAMABLE_HTTP_PATH="${MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH:-${MCP_STREAMABLE_HTTP_PATH:-/mcp}}"
MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN:-}"
MCP_STARTUP_TIMEOUT_SECONDS="${MCP_STARTUP_TIMEOUT_SECONDS:-20}"
HEALTH_URL="http://${MCP_HOST}:${MCP_PORT}${MCP_STREAMABLE_HTTP_PATH}"

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

build_pythonpath() {
  local parts=("${ROOT_DIR}")
  if [[ -n "${PYTHONPATH:-}" ]]; then
    parts+=("${PYTHONPATH}")
  fi
  if [[ -n "${MCP_PYTHONPATH:-}" ]]; then
    parts+=("${MCP_PYTHONPATH}")
  fi
  local joined=""
  local item
  for item in "${parts[@]}"; do
    if [[ -z "${item}" ]]; then
      continue
    fi
    if [[ -n "${joined}" ]]; then
      joined="${joined}:${item}"
    else
      joined="${item}"
    fi
  done
  printf '%s\n' "${joined}"
}

RUNTIME_PYTHONPATH="$(build_pythonpath)"

wait_for_port() {
  local deadline=$((SECONDS + MCP_STARTUP_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if "${PYTHON_BIN}" - "${MCP_HOST}" "${MCP_PORT}" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(1.0)
try:
    sock.connect((host, port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
sys.exit(0)
PY
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

if ! wait_for_port; then
  echo "[mcp-health] port did not open within ${MCP_STARTUP_TIMEOUT_SECONDS}s: ${MCP_HOST}:${MCP_PORT}" >&2
  exit 1
fi

echo "[mcp-health] checking streamable-http endpoint: ${HEALTH_URL}"
last_output=""
for attempt in $(seq 1 10); do
  if probe_output="$(PYTHONPATH="${RUNTIME_PYTHONPATH}" \
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/deployment/mcp_protocol_health_probe.py" \
    --url "${HEALTH_URL}" \
    --bearer-token "${MCP_BEARER_TOKEN}" 2>&1)"; then
    printf '%s\n' "${probe_output}"
    echo "MCP health check: OK"
    exit 0
  fi
  last_output="${probe_output}"
  sleep 0.5
done

if [[ -n "${last_output}" ]]; then
  printf '%s\n' "${last_output}" >&2
fi
echo "MCP health check failed after retries" >&2
exit 1
