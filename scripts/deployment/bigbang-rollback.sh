#!/usr/bin/env bash
# T17 Big-Bang 回滚脚本
# 功能：将系统回滚到指定的备份版本
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

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <BACKUP_TAG>"
  echo ""
  echo "Available backups:"
  ls -1 "${BACKUP_DIR}" | grep -E "backup-manifest.*\.txt$" | sed 's/backup-manifest\.//' | sed 's/\.txt$//'
  exit 1
fi

BACKUP_TAG=$1
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
  echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $*"
}

load_runtime_port_config() {
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

# 验证备份存在
validate_backup() {
  local backup_tag=$1

  if [[ ! -f "${BACKUP_DIR}/backup-manifest.${backup_tag}.txt" ]]; then
    log_error "Backup not found: ${backup_tag}"
    exit 1
  fi

  log_info "Backup validated: ${backup_tag}"
}

# 停止当前服务
stop_services() {
  log_info "Stopping current services..."

  if [[ -f "${ROOT_DIR}/scripts/deployment/intranet-single-node-stop.sh" ]]; then
    bash "${ROOT_DIR}/scripts/deployment/intranet-single-node-stop.sh"
  else
    log_warn "Stop script not found, skipping service stop"
  fi

  sleep 2
}

# 恢复依赖文件
restore_dependencies() {
  local backup_tag=$1

  log_info "Restoring dependencies from ${backup_tag}..."

  # 恢复 Python 依赖
  if [[ -f "${BACKUP_DIR}/requirements.txt.${backup_tag}" ]]; then
    cp "${BACKUP_DIR}/requirements.txt.${backup_tag}" "${ROOT_DIR}/requirements.txt"
    log_info "Restored requirements.txt"
  fi

  # 恢复前端依赖
  if [[ -f "${BACKUP_DIR}/package.json.${backup_tag}" ]]; then
    cp "${BACKUP_DIR}/package.json.${backup_tag}" "${ROOT_DIR}/frontend/package.json"
    log_info "Restored frontend/package.json"

    # 重新安装前端依赖
    log_info "Reinstalling frontend dependencies..."
    cd "${ROOT_DIR}/frontend"
    npm install --silent
    cd "${ROOT_DIR}"
  fi
}

# 恢复配置文件
restore_config() {
  local backup_tag=$1

  log_info "Restoring configuration files from ${backup_tag}..."

  if [[ -d "${BACKUP_DIR}/config.${backup_tag}" ]]; then
    rm -rf "${ROOT_DIR}/config"
    cp -r "${BACKUP_DIR}/config.${backup_tag}" "${ROOT_DIR}/config"
    log_info "Restored config/"
  fi
}

# 恢复环境变量（可选）
restore_env() {
  local backup_tag=$1

  if [[ -f "${BACKUP_DIR}/.env.intranet.${backup_tag}" ]]; then
    cp "${BACKUP_DIR}/.env.intranet.${backup_tag}" "${ROOT_DIR}/.env.intranet"
    log_info "Restored .env.intranet"
  fi
}

# 启动恢复后的服务
start_services() {
  log_info "Starting services..."

  if [[ -f "${ROOT_DIR}/scripts/deployment/intranet-single-node-start.sh" ]]; then
    bash "${ROOT_DIR}/scripts/deployment/intranet-single-node-start.sh"
  else
    log_warn "Start script not found, skipping service start"
  fi

  # 等待服务启动
  log_info "Waiting for services to initialize (30 seconds)..."
  sleep 30
}

# 运行回滚验证
run_verification() {
  log_info "Running rollback verification..."

  local verification_result=0

  if [[ -f "${ROOT_DIR}/scripts/deployment/intranet-health-check.sh" ]]; then
    if ! bash "${ROOT_DIR}/scripts/deployment/intranet-health-check.sh" > "${LOG_DIR}/rollback-verify-${TIMESTAMP}.log" 2>&1; then
      log_error "Rollback verification failed!"
      verification_result=1
    else
      log_info "Rollback verification passed!"
    fi
  else
    log_warn "Health check script not found, skipping verification"
  fi

  return ${verification_result}
}

# 记录回滚操作
record_rollback() {
  local backup_tag=$1
  local result=$2

  cat > "${RUNTIME_DIR}/rollback-${TIMESTAMP}.json" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "backup_tag": "${backup_tag}",
  "result": "${result}",
  "logs": "${LOG_DIR}/rollback-verify-${TIMESTAMP}.log"
}
EOF

  log_info "Rollback recorded: ${RUNTIME_DIR}/rollback-${TIMESTAMP}.json"
}

# 主流程
main() {
  load_runtime_port_config
  select_effective_ports
  log_info "=== Big-Bang 回滚开始 ==="
  log_info "回滚时间: $(date)"
  log_info "备份标签: ${BACKUP_TAG}"
  log_info "Using runtime ports: PY=${PY_API_PORT}, SIDECAR=${SIDECAR_PORT}, FRONTEND=${FRONTEND_PORT}"

  # 1. 验证备份存在
  validate_backup "${BACKUP_TAG}"

  # 2. 停止当前服务
  stop_services

  # 3. 恢复依赖文件
  restore_dependencies "${BACKUP_TAG}"

  # 4. 恢复配置文件
  restore_config "${BACKUP_TAG}"

  # 5. 恢复环境变量
  restore_env "${BACKUP_TAG}"

  load_runtime_port_config
  select_effective_ports

  # 6. 启动恢复后的服务
  start_services

  # 7. 运行回滚验证
  if ! run_verification; then
    record_rollback "${BACKUP_TAG}" "FAILED"
    log_error "Rollback verification failed!"
    log_error "Please check logs: ${LOG_DIR}/rollback-verify-${TIMESTAMP}.log"
    exit 1
  fi

  # 8. 记录成功
  record_rollback "${BACKUP_TAG}" "SUCCESS"

  log_info "=== Big-Bang 回滚成功 ==="
  log_info "系统已回滚到备份版本: ${BACKUP_TAG}"
  log_info "回滚日志: ${LOG_DIR}/rollback-verify-${TIMESTAMP}.log"
}

# 执行主流程
main "$@"
