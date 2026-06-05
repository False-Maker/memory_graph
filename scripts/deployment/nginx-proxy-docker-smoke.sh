#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/scripts/deployment/compose/docker-compose.yml"
COMPOSE_ENV_FILE="${ROOT_DIR}/scripts/deployment/compose/.env.compose.example"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"
TEMP_DIR="$(mktemp -d "${RUNTIME_DIR}/nginx-proxy-smoke.XXXXXX")"
NGINX_CONTAINER_NAME="memory-graph-nginx-proxy-smoke"
PUBLISHED_HTTP_PORT="${NGINX_SMOKE_PUBLISHED_PORT:-39080}"
COMPOSE_API_PUBLISHED_PORT="${COMPOSE_API_PUBLISHED_PORT:-38000}"
COMPOSE_MCP_PUBLISHED_PORT="${COMPOSE_MCP_PUBLISHED_PORT:-38001}"
MEMORY_GRAPH_MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN:-nginx-proxy-smoke-token}"
MCP_PYTHONPATH="${MCP_PYTHONPATH:-/tmp/mcp-sdk}"
API_HEALTH_URL="http://127.0.0.1:${PUBLISHED_HTTP_PORT}/health"
API_RUNTIME_URL="http://127.0.0.1:${PUBLISHED_HTTP_PORT}/api/v1/diagnostics/runtime"
WEB_URL="http://127.0.0.1:${PUBLISHED_HTTP_PORT}/"

wait_for_http_ok() {
  local label="$1"
  local url="$2"
  local timeout_seconds="${3:-20}"
  local deadline=$((SECONDS + timeout_seconds))

  while (( SECONDS < deadline )); do
    if curl --max-time 5 -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "[nginx-smoke] ${label} did not become ready within ${timeout_seconds}s: ${url}" >&2
  return 1
}

cleanup() {
  docker rm -f "${NGINX_CONTAINER_NAME}" >/dev/null 2>&1 || true
  COMPOSE_API_PUBLISHED_PORT="${COMPOSE_API_PUBLISHED_PORT}" \
  COMPOSE_MCP_PUBLISHED_PORT="${COMPOSE_MCP_PUBLISHED_PORT}" \
  MEMORY_GRAPH_MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN}" \
  docker compose \
    --env-file "${ROOT_DIR}/.env.intranet" \
    --env-file "${COMPOSE_ENV_FILE}" \
    -f "${COMPOSE_FILE}" \
    down >/dev/null 2>&1 || true
  rm -rf "${TEMP_DIR}"
}

trap cleanup EXIT

mkdir -p "${RUNTIME_DIR}"

cat > "${TEMP_DIR}/default.conf" <<'CONF'
server {
    listen 80;
    server_name _;

    client_max_body_size 32m;

    location / {
        proxy_pass http://memory-graph-api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /mcp {
        proxy_pass http://memory-graph-mcp:8001;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
CONF

echo "[nginx-smoke] starting compose stack"
COMPOSE_API_PUBLISHED_PORT="${COMPOSE_API_PUBLISHED_PORT}" \
COMPOSE_MCP_PUBLISHED_PORT="${COMPOSE_MCP_PUBLISHED_PORT}" \
MEMORY_GRAPH_MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN}" \
docker compose \
  --env-file "${ROOT_DIR}/.env.intranet" \
  --env-file "${COMPOSE_ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  up -d >/dev/null

echo "[nginx-smoke] starting nginx proxy container on port ${PUBLISHED_HTTP_PORT}"
docker rm -f "${NGINX_CONTAINER_NAME}" >/dev/null 2>&1 || true
docker run -d \
  --name "${NGINX_CONTAINER_NAME}" \
  --network memory-graph_default \
  -p "${PUBLISHED_HTTP_PORT}:80" \
  -v "${TEMP_DIR}/default.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:1.27-alpine >/dev/null

wait_for_http_ok "proxied web shell" "${WEB_URL}" 30

echo "[nginx-smoke] checking proxied web shell"
curl --max-time 20 -sS "${WEB_URL}" >/dev/null

echo "[nginx-smoke] checking proxied API health"
curl --max-time 20 -sS "${API_HEALTH_URL}" >/dev/null

echo "[nginx-smoke] checking proxied runtime diagnostics"
curl --max-time 20 -sS "${API_RUNTIME_URL}" >/dev/null

echo "[nginx-smoke] checking proxied MCP endpoint via protocol health"
MEMORY_GRAPH_MCP_HOST=127.0.0.1 \
MEMORY_GRAPH_MCP_PORT="${PUBLISHED_HTTP_PORT}" \
MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH=/mcp \
MEMORY_GRAPH_MCP_BEARER_TOKEN="${MEMORY_GRAPH_MCP_BEARER_TOKEN}" \
MCP_PYTHONPATH="${MCP_PYTHONPATH}" \
bash "${ROOT_DIR}/scripts/deployment/mcp-health-check.sh"

echo "[nginx-smoke] all checks passed"
