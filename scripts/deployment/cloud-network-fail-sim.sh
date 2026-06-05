#!/usr/bin/env bash
set -euo pipefail

PY_API_PORT="${PY_API_PORT:-8000}"

echo "[cloud-network-fail] simulate tightened network: query blocked target 127.0.0.1:${PY_API_PORT}"
echo "[cloud-network-fail] expected result: connectivity failure indicates network policy/access issue"

set +e
curl -sS --connect-timeout 1 "http://127.0.0.1:${PY_API_PORT}/health" --interface 203.0.113.10
curl_rc="$?"
set -e

if [[ "$curl_rc" -eq 0 ]]; then
  echo "[cloud-network-fail] unexpected success: simulation did not produce connectivity failure" >&2
  exit 1
fi

echo "[cloud-network-fail] expected failure captured (curl exit=${curl_rc})"
echo "[cloud-network-fail] network policy/path must be reviewed before allowing access"
