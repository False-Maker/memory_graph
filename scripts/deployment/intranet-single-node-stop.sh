#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PID_DIR="${ROOT_DIR}/.sisyphus/runtime/pids"
ENV_FILE="${ROOT_DIR}/.env.intranet"
EXTERNAL_PY_API_PORT="${PY_API_PORT:-}"
EXTERNAL_SIDECAR_PORT="${SIDECAR_PORT:-}"

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

stop_pid_file() {
  local file="$1"
  if [[ ! -f "${file}" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "${file}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      if ! kill -0 "${pid}" 2>/dev/null; then
        break
      fi
      sleep 0.5
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
      for _ in $(seq 1 10); do
        if ! kill -0 "${pid}" 2>/dev/null; then
          break
        fi
        sleep 0.2
      done
    fi
  fi
  rm -f "${file}"
}

stop_tcp_listener() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi

  local pid
  for pid in ${pids}; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done

  for _ in $(seq 1 20); do
    if ! lsof -ti "tcp:${port}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done

  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  for pid in ${pids}; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  done

  for _ in $(seq 1 10); do
    if ! lsof -ti "tcp:${port}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done

  return 1
}

stop_pid_file "${PID_DIR}/frontend.pid"
stop_pid_file "${PID_DIR}/sidecar.pid"
stop_pid_file "${PID_DIR}/py-api.pid"
stop_tcp_listener "${SIDECAR_PORT}" || true
stop_tcp_listener "${PY_API_PORT}" || true

echo "Intranet single-node services stopped (if running)."
