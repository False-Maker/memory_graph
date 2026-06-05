#!/usr/bin/env bash
# T17 彩排验证检查脚本
# 功能：验证彩排结果是否通过所有检查
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.sisyphus/runtime"
LOG_DIR="${RUNTIME_DIR}/logs"

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

json_field() {
  local file="$1"
  local field="$2"

  if command -v jq &> /dev/null; then
    jq -r ".${field}" "${file}"
    return
  fi

  python3 - "${file}" "${field}" <<'PY'
import json
import sys

file_path = sys.argv[1]
field_name = sys.argv[2]

with open(file_path, "r", encoding="utf-8") as fh:
    payload = json.load(fh)

value = payload.get(field_name, "")
if value is None:
    value = ""

print(value)
PY
}

# 查找最新的彩排结果
find_latest_rehearsal() {
  find "${RUNTIME_DIR}" -name "rehearsal-*.json" -type f -printf '%T@ %p\n' | \
    sort -rn | head -1 | cut -d' ' -f2-
}

# 解析彩排结果
parse_rehearsal_result() {
  local rehearsal_file=$1

  if [[ ! -f "${rehearsal_file}" ]]; then
    echo "NONE"
    return
  fi

  json_field "${rehearsal_file}" "result"
}

# 验证彩排日志存在
verify_rehearsal_logs() {
  local rehearsal_file=$1

  local timestamp
  timestamp=$(json_field "${rehearsal_file}" "timestamp")

  local health_check_log="${LOG_DIR}/rehearsal-health-check-${timestamp}.log"

  if [[ ! -f "${health_check_log}" ]]; then
    log_warn "Health check log not found: ${health_check_log}"
    return 1
  fi

  log_info "Health check log found: ${health_check_log}"
  return 0
}

# 验证备份文件
verify_backup_files() {
  local rehearsal_file=$1

  local backup_tag
  backup_tag=$(json_field "${rehearsal_file}" "backup_tag")

  local backup_dir="${RUNTIME_DIR}/backups"

  if [[ ! -d "${backup_dir}" ]]; then
    log_error "Backup directory not found: ${backup_dir}"
    return 1
  fi

  # 检查关键备份文件
  local missing_files=0

  if [[ ! -f "${backup_dir}/backup-manifest.${backup_tag}.txt" ]]; then
    log_error "Backup manifest not found: backup-manifest.${backup_tag}.txt"
    missing_files=$((missing_files + 1))
  fi

  if [[ ! -f "${backup_dir}/requirements.txt.${backup_tag}" ]]; then
    log_error "Requirements backup not found: requirements.txt.${backup_tag}"
    missing_files=$((missing_files + 1))
  fi

  if [[ ! -f "${backup_dir}/package.json.${backup_tag}" ]]; then
    log_error "Package.json backup not found: package.json.${backup_tag}"
    missing_files=$((missing_files + 1))
  fi

  if [[ ${missing_files} -gt 0 ]]; then
    log_error "Missing ${missing_files} backup files"
    return 1
  fi

  log_info "All backup files verified"
  return 0
}

# 打印彩排摘要
print_rehearsal_summary() {
  local rehearsal_file=$1

  log_info "=== 彩排摘要 ==="
  log_info "文件: ${rehearsal_file}"

  if command -v jq &> /dev/null; then
    jq -r 'to_entries[] | "  \(.key): \(.value)"' "${rehearsal_file}"
  else
    cat "${rehearsal_file}"
  fi
}

# 主流程
main() {
  log_info "=== T17 彩排验证检查 ==="
  log_info "验证时间: $(date)"

  # 1. 查找最新的彩排结果
  local latest_rehearsal
  latest_rehearsal=$(find_latest_rehearsal)

  if [[ -z "${latest_rehearsal}" ]]; then
    log_error "No rehearsal results found"
    log_info "Please run the rehearsal script first: bash scripts/deployment/bigbang-rehearsal.sh"
    exit 1
  fi

  log_info "Latest rehearsal: ${latest_rehearsal}"

  # 2. 解析彩排结果
  local result
  result=$(parse_rehearsal_result "${latest_rehearsal}")

  if [[ "${result}" == "NONE" ]]; then
    log_error "Failed to parse rehearsal result"
    exit 1
  fi

  log_info "Rehearsal result: ${result}"

  # 3. 验证备份文件
  if ! verify_backup_files "${latest_rehearsal}"; then
    log_error "Backup verification failed"
    exit 1
  fi

  # 4. 验证彩排日志
  if ! verify_rehearsal_logs "${latest_rehearsal}"; then
    log_warn "Rehearsal log verification failed (non-critical)"
  fi

  # 5. 打印摘要
  print_rehearsal_summary "${latest_rehearsal}"

  # 6. 最终判定
  if [[ "${result}" == "SUCCESS" ]]; then
    log_info "=== 彩排验证: 通过 ==="
    log_info "所有检查项已通过，可以执行正式切换"
    exit 0
  else
    log_error "=== 彩排验证: 失败 ==="
    log_error "彩排未通过，请检查日志并修复问题"
    exit 1
  fi
}

# 执行主流程
main "$@"
