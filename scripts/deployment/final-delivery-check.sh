#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

cd "${ROOT_DIR}"

echo "[final-delivery] deployment / runtime regression"
python3 -m pytest tests/test_deployment_standardization.py tests/test_llm_manager.py tests/test_main_api.py -q

echo "[final-delivery] api docs drift"
python3 scripts/generate_api_docs.py --check

echo "[final-delivery] frontend production build"
npm --prefix frontend run build

cat <<'EOF'
[final-delivery] static checks passed

Optional runtime verification entrypoints:

- shell single-node:
  bash scripts/deployment/intranet-single-node-start.sh
  bash scripts/deployment/intranet-health-check.sh
  bash scripts/deployment/intranet-single-node-stop.sh

- mcp:
  bash scripts/deployment/mcp-start.sh
  bash scripts/deployment/mcp-health-check.sh
  bash scripts/deployment/mcp-stop.sh

- nginx in docker:
  bash scripts/deployment/nginx-proxy-docker-smoke.sh
EOF
