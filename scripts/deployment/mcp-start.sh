#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"
ENV_INTRANET_FILE="${ROOT_DIR}/.env.intranet"
ENV_MCP_FILE="${ROOT_DIR}/.env.mcp"

EXTERNAL_MCP_HOST="${MEMORY_GRAPH_MCP_HOST:-${MCP_HOST:-}}"
EXTERNAL_MCP_PORT="${MEMORY_GRAPH_MCP_PORT:-${MCP_PORT:-}}"
EXTERNAL_MCP_MOUNT_PATH="${MEMORY_GRAPH_MCP_MOUNT_PATH:-${MCP_MOUNT_PATH:-}}"
EXTERNAL_MCP_STREAMABLE_HTTP_PATH="${MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH:-${MCP_STREAMABLE_HTTP_PATH:-}}"
EXTERNAL_MCP_STATELESS_HTTP="${MEMORY_GRAPH_MCP_STATELESS_HTTP:-${MCP_STATELESS_HTTP:-}}"
EXTERNAL_MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN:-}"
EXTERNAL_PYTHON_BIN="${PYTHON_BIN:-}"
EXTERNAL_MCP_PYTHONPATH="${MCP_PYTHONPATH:-}"

mkdir -p "${PID_DIR}" "${LOG_DIR}"

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
if [[ -n "${EXTERNAL_MCP_MOUNT_PATH}" ]]; then
  MEMORY_GRAPH_MCP_MOUNT_PATH="${EXTERNAL_MCP_MOUNT_PATH}"
fi
if [[ -n "${EXTERNAL_MCP_STREAMABLE_HTTP_PATH}" ]]; then
  MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH="${EXTERNAL_MCP_STREAMABLE_HTTP_PATH}"
fi
if [[ -n "${EXTERNAL_MCP_STATELESS_HTTP}" ]]; then
  MEMORY_GRAPH_MCP_STATELESS_HTTP="${EXTERNAL_MCP_STATELESS_HTTP}"
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
MCP_MOUNT_PATH="${MEMORY_GRAPH_MCP_MOUNT_PATH:-${MCP_MOUNT_PATH:-/}}"
MCP_STREAMABLE_HTTP_PATH="${MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH:-${MCP_STREAMABLE_HTTP_PATH:-/mcp}}"
MCP_STATELESS_HTTP="${MEMORY_GRAPH_MCP_STATELESS_HTTP:-${MCP_STATELESS_HTTP:-true}}"
MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN:-}"
MCP_PID_FILE="${PID_DIR}/mcp.pid"
MCP_LOG_FILE="${LOG_DIR}/mcp.log"

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

assert_mcp_sdk_installed() {
  local runtime_pythonpath="$1"
  if PYTHONPATH="${runtime_pythonpath}" "${PYTHON_BIN}" - <<'PY'
import importlib.util
import sys

sys.exit(0 if importlib.util.find_spec("mcp") is not None else 1)
PY
  then
    return 0
  fi

  echo "Missing Python package: mcp" >&2
  echo "Install requirements with 'pip install -r requirements.txt' or set MCP_PYTHONPATH to a local MCP SDK path." >&2
  exit 1
}

assert_port_free() {
  local host="$1"
  local port="$2"
  if "${PYTHON_BIN}" - "${host}" "${port}" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
  then
    return 0
  fi

  echo "Port conflict detected: ${host}:${port} is already in use" >&2
  exit 1
}

if [[ -f "${MCP_PID_FILE}" ]]; then
  existing_pid="$(cat "${MCP_PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" >/dev/null 2>&1; then
    echo "MCP server already running with PID ${existing_pid}" >&2
    exit 1
  fi
  rm -f "${MCP_PID_FILE}"
fi

RUNTIME_PYTHONPATH="$(build_pythonpath)"
assert_mcp_sdk_installed "${RUNTIME_PYTHONPATH}"
assert_port_free "${MCP_HOST}" "${MCP_PORT}"

cd "${ROOT_DIR}"

echo "Starting Memory Graph MCP server (streamable-http)..."
echo "Host: ${MCP_HOST}"
echo "Port: ${MCP_PORT}"
echo "Endpoint: ${MCP_STREAMABLE_HTTP_PATH}"

export MEMORY_GRAPH_MCP_TRANSPORT="streamable-http"
export MEMORY_GRAPH_MCP_HOST="${MCP_HOST}"
export MEMORY_GRAPH_MCP_PORT="${MCP_PORT}"
export MEMORY_GRAPH_MCP_MOUNT_PATH="${MCP_MOUNT_PATH}"
export MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH="${MCP_STREAMABLE_HTTP_PATH}"
export MEMORY_GRAPH_MCP_STATELESS_HTTP="${MCP_STATELESS_HTTP}"
export MEMORY_GRAPH_MCP_BEARER_TOKEN="${MCP_BEARER_TOKEN}"

nohup env \
  PYTHONPATH="${RUNTIME_PYTHONPATH}" \
  "${PYTHON_BIN}" -m src.mcp \
  --transport streamable-http \
  --host "${MCP_HOST}" \
  --port "${MCP_PORT}" \
  --mount-path "${MCP_MOUNT_PATH}" \
  --streamable-http-path "${MCP_STREAMABLE_HTTP_PATH}" \
  --stateless-http "${MCP_STATELESS_HTTP}" >"${MCP_LOG_FILE}" 2>&1 < /dev/null &
echo $! >"${MCP_PID_FILE}"

if ! MEMORY_GRAPH_MCP_HOST="${MCP_HOST}" \
  MEMORY_GRAPH_MCP_PORT="${MCP_PORT}" \
  MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH="${MCP_STREAMABLE_HTTP_PATH}" \
  MEMORY_GRAPH_MCP_BEARER_TOKEN="${MCP_BEARER_TOKEN}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  MCP_PYTHONPATH="${MCP_PYTHONPATH:-}" \
  bash "${ROOT_DIR}/scripts/deployment/mcp-health-check.sh"; then
  pid="$(cat "${MCP_PID_FILE}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${MCP_PID_FILE}"
  echo "MCP server failed health check; process stopped. See ${MCP_LOG_FILE}" >&2
  exit 1
fi

echo "MCP server started with PID $(cat "${MCP_PID_FILE}")"
echo "Logs: ${MCP_LOG_FILE}"
