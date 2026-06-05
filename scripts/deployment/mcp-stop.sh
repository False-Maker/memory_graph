#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PID_DIR="${ROOT_DIR}/.sisyphus/runtime/pids"

stop_pid_file() {
  local file="$1"
  if [[ ! -f "${file}" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "${file}")"
  if [[ -z "${pid}" ]]; then
    rm -f "${file}"
    return 1
  fi

  if kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        break
      fi
      sleep 0.5
    done
  fi

  if kill -0 "${pid}" >/dev/null 2>&1; then
    echo "MCP process ${pid} did not exit after SIGTERM" >&2
    return 1
  fi

  rm -f "${file}"
  echo "Stopped MCP server PID ${pid}"
  return 0
}

if stop_pid_file "${PID_DIR}/mcp.pid"; then
  exit 0
fi

if stop_pid_file "${PID_DIR}/mcp-streamable-http.pid"; then
  exit 0
fi

echo "MCP server is not running (missing canonical or legacy PID file)." >&2
exit 1
