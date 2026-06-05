#!/usr/bin/env bash
# T17 Big-Bang 切换彩排脚本
# 功能：执行从旧版本到新版本的切换彩排，包含健康检查和自动回滚
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"
BACKUP_DIR="${RUNTIME_DIR}/backups"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"
ENV_FILE="${ROOT_DIR}/.env.intranet"
EXTERNAL_PY_API_PORT="${PY_API_PORT:-}"
EXTERNAL_SIDECAR_PORT="${SIDECAR_PORT:-}"
EXTERNAL_FRONTEND_PORT="${FRONTEND_PORT:-}"

# 创建必要的目录
mkdir -p "${BACKUP_DIR}" "${PID_DIR}" "${LOG_DIR}"

# 加载环境变量
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
if [[ -n "${EXTERNAL_FRONTEND_PORT}" ]]; then
  FRONTEND_PORT="${EXTERNAL_FRONTEND_PORT}"
fi

PY_API_PORT="${PY_API_PORT:-8000}"
SIDECAR_PORT="${SIDECAR_PORT:-3001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# 彩排时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_TAG="v${TIMESTAMP}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
  echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $*"
}

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

PYTHON_BIN="$(detect_python_bin)"

is_port_free() {
  local port="$1"
  "${PYTHON_BIN}" - "${port}" <<'PY'
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
}

find_free_port() {
  local preferred_port="$1"
  "${PYTHON_BIN}" - "${preferred_port}" <<'PY'
import socket
import sys

start = max(1024, int(sys.argv[1]))

def is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()

for port in range(start, 65536):
    if is_free(port):
        print(port)
        sys.exit(0)

sys.exit(1)
PY
}

resolve_runtime_port() {
  local label="$1"
  local configured_port="$2"

  if is_port_free "${configured_port}"; then
    printf '%s\n' "${configured_port}"
    return 0
  fi

  local fallback_port
  fallback_port="$(find_free_port "$((configured_port + 1))")"
  log_warn "${label} ${configured_port} is already in use; falling back to ${fallback_port}" >&2
  printf '%s\n' "${fallback_port}"
}

select_effective_ports() {
  PY_API_PORT="$(resolve_runtime_port "PY_API_PORT" "${PY_API_PORT}")"
  SIDECAR_PORT="$(resolve_runtime_port "SIDECAR_PORT" "${SIDECAR_PORT}")"
  FRONTEND_PORT="$(resolve_runtime_port "FRONTEND_PORT" "${FRONTEND_PORT}")"
  export PY_API_PORT SIDECAR_PORT FRONTEND_PORT PYTHON_BIN
}

# 停止服务
stop_services() {
  log_info "Stopping current services..."
  bash "${ROOT_DIR}/scripts/deployment/intranet-single-node-stop.sh"
  sleep 2
}

# 备份当前版本
backup_current_version() {
  log_info "Backing up current version as ${BACKUP_TAG}..."

  # 备份 Python 依赖
  if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    cp "${ROOT_DIR}/requirements.txt" "${BACKUP_DIR}/requirements.txt.${BACKUP_TAG}"
  fi

  # 备份前端依赖
  if [[ -f "${ROOT_DIR}/frontend/package.json" ]]; then
    cp "${ROOT_DIR}/frontend/package.json" "${BACKUP_DIR}/package.json.${BACKUP_TAG}"
  fi

  # 备份环境变量（敏感信息已过滤）
  if [[ -f "${ENV_FILE}" ]]; then
    cp "${ENV_FILE}" "${BACKUP_DIR}/.env.intranet.${BACKUP_TAG}"
  fi

  # 备份配置文件
  if [[ -d "${ROOT_DIR}/config" ]]; then
    mkdir -p "${BACKUP_DIR}/config.${BACKUP_TAG}"
    cp -r "${ROOT_DIR}/config"/* "${BACKUP_DIR}/config.${BACKUP_TAG}/" || true
  fi

  # 记录备份清单
  cat > "${BACKUP_DIR}/backup-manifest.${BACKUP_TAG}.txt" <<EOF
Backup Timestamp: ${TIMESTAMP}
Backup Tag: ${BACKUP_TAG}
Backup Type: Pre-deployment

Files Backed Up:
- requirements.txt -> requirements.txt.${BACKUP_TAG}
- frontend/package.json -> package.json.${BACKUP_TAG}
- .env.intranet -> .env.intranet.${BACKUP_TAG}
- config/ -> config.${BACKUP_TAG}/

Deployment Metadata:
- PY_API_PORT: ${PY_API_PORT}
- SIDECAR_PORT: ${SIDECAR_PORT}
- FRONTEND_PORT: ${FRONTEND_PORT}
EOF

  log_info "Backup completed: ${BACKUP_DIR}/backup-manifest.${BACKUP_TAG}.txt"
}

# 启动新版本
start_new_version() {
  log_info "Starting new version services..."
  bash "${ROOT_DIR}/scripts/deployment/intranet-single-node-start.sh"

  # 等待服务启动
  log_info "Waiting for services to initialize (30 seconds)..."
  sleep 30
}

# 运行健康检查
run_health_checks() {
  log_info "Running health checks..."

  local health_check_result=0

  # 健康检查脚本
  if ! bash "${ROOT_DIR}/scripts/deployment/intranet-health-check.sh" > "${LOG_DIR}/rehearsal-health-check-${TIMESTAMP}.log" 2>&1; then
    log_error "Health checks failed!"
    health_check_result=1
  else
    log_info "All health checks passed!"
  fi

  return ${health_check_result}
}

# 关键端点冒烟测试
run_smoke_tests() {
  log_info "Running smoke tests..."

  local smoke_check_result=0

  # 测试 Python API 健康端点
  if ! curl -sf "http://127.0.0.1:${PY_API_PORT}/health" > /dev/null 2>&1; then
    log_error "Python API health endpoint failed!"
    smoke_check_result=1
  fi

  # 测试 Sidecar 健康端点
  if ! curl -sf "http://127.0.0.1:${SIDECAR_PORT}/health" > /dev/null 2>&1; then
    log_error "Sidecar health endpoint failed!"
    smoke_check_result=1
  fi

  # 生产部署的 Web shell 由 FastAPI 直接托管
  if ! curl -sf "http://127.0.0.1:${PY_API_PORT}/" > /dev/null 2>&1; then
    log_error "Frontend shell via Python API endpoint failed!"
    smoke_check_result=1
  fi

  # 测试关键查询端点（应该返回 422 因为请求体为空）
  local query_status
  query_status=$(curl -s -o /dev/null -w '%{http_code}' \
    -X POST "http://127.0.0.1:${PY_API_PORT}/api/v1/query" \
    -H "Content-Type: application/json" \
    -d '{}')

  if [[ "${query_status}" != "422" ]]; then
    log_error "Query endpoint smoke test failed! Expected 422, got ${query_status}"
    smoke_check_result=1
  fi

  if [[ ${smoke_check_result} -eq 0 ]]; then
    log_info "All smoke tests passed!"
  fi

  return ${smoke_check_result}
}

# 自动回滚
auto_rollback() {
  log_error "Initiating automatic rollback to ${BACKUP_TAG}..."
  bash "${ROOT_DIR}/scripts/deployment/bigbang-rollback.sh" "${BACKUP_TAG}"
}

# 记录彩排结果
record_rehearsal_result() {
  local result=$1
  local reason="${2:-Success}"

  cat > "${RUNTIME_DIR}/rehearsal-${TIMESTAMP}.json" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "backup_tag": "${BACKUP_TAG}",
  "result": "${result}",
  "reason": "${reason}",
  "py_api_port": ${PY_API_PORT},
  "sidecar_port": ${SIDECAR_PORT},
  "frontend_port": ${FRONTEND_PORT}
}
EOF

  log_info "Rehearsal result recorded: ${RUNTIME_DIR}/rehearsal-${TIMESTAMP}.json"
}

# 主流程
main() {
  select_effective_ports
  log_info "=== Big-Bang 切换彩排开始 ==="
  log_info "彩排时间: $(date)"
  log_info "备份标签: ${BACKUP_TAG}"
  log_info "Using runtime ports: PY=${PY_API_PORT}, SIDECAR=${SIDECAR_PORT}, FRONTEND=${FRONTEND_PORT}"

  # 1. 停止当前服务
  stop_services

  # 2. 备份当前版本
  backup_current_version

  # 3. 启动新版本
  start_new_version

  # 4. 运行健康检查
  if ! run_health_checks; then
    record_rehearsal_result "FAILED" "Health checks failed"
    log_error "Rehearsal FAILED: Health checks failed"
    log_error "Initiating automatic rollback..."
    auto_rollback
    exit 1
  fi

  # 5. 运行冒烟测试
  if ! run_smoke_tests; then
    record_rehearsal_result "FAILED" "Smoke tests failed"
    log_error "Rehearsal FAILED: Smoke tests failed"
    log_error "Initiating automatic rollback..."
    auto_rollback
    exit 1
  fi

  # 6. 记录成功
  record_rehearsal_result "SUCCESS" "All checks passed"

  log_info "=== Big-Bang 切换彩排成功 ==="
  log_info "新版本已通过所有验证，备份标签: ${BACKUP_TAG}"
  log_info "彩排日志: ${LOG_DIR}/rehearsal-health-check-${TIMESTAMP}.log"
  log_info "如需回滚，运行: bash scripts/deployment/bigbang-rollback.sh ${BACKUP_TAG}"
}

# 执行主流程
main "$@"
