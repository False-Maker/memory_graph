# T17 Big-Bang 切换彩排与回滚资产准备

> **目标**: 执行 Big-Bang 切换彩排与回滚资产准备，包括切换彩排成功验证、回滚演练验证，产出回滚脚本、旧版本保留策略、失败决策树。

## 概述

T17 提供完整的 Big-Bang 部署切换彩排和回滚能力，确保从旧版本到新版本的平滑过渡，并在失败时能够快速回滚。

## 1. 交付物清单

### 1.1 脚本文件

- `scripts/deployment/bigbang-rehearsal.sh` - Big-Bang 切换彩排脚本
- `scripts/deployment/bigbang-rollback.sh` - Big-Bang 回滚脚本
- `scripts/deployment/bigbang-rehearsal-verify.sh` - 彩排验证检查脚本

### 1.2 文档

- `docs/deployment/t17-bigbang-rehearsal-rollback.md` - 本文档（包含旧版本保留策略和失败决策树）

### 1.3 运行时产物

- `.sisyphus/runtime/backups/` - 备份文件存储目录
- `.sisyphus/runtime/pids/` - 进程 PID 文件
- `.sisyphus/runtime/logs/` - 日志文件
- `.sisyphus/runtime/rehearsal-*.json` - 彩排结果记录
- `.sisyphus/runtime/rollback-*.json` - 回滚结果记录
- `.sisyphus/runtime/verification-report-*.json` - 验证报告

---

## 2. 旧版本保留策略

### 2.1 备份内容

每次执行 Big-Bang 切换彩排时，自动备份以下内容：

| 内容 | 备份路径 | 说明 |
|------|---------|------|
| Python 依赖 | `requirements.txt.v{TIMESTAMP}` | Python 包依赖列表 |
| 前端依赖 | `frontend/package.json.v{TIMESTAMP}` | Node.js 包依赖列表 |
| 环境变量 | `.env.intranet.v{TIMESTAMP}` | 内网部署环境配置 |
| 配置文件 | `config.v{TIMESTAMP}/` | 应用配置文件目录 |
| 备份清单 | `backup-manifest.v{TIMESTAMP}.txt` | 备份内容和元数据 |

### 2.2 备份存储

- **备份目录**: `.sisyphus/runtime/backups/`
- **命名格式**: `v{YYYYMMDD}_{HHMMSS}` (例如: `v20240322_143025`)
- **备份清单**: 每个备份都有一个对应的 `backup-manifest.{TAG}.txt` 文件

### 2.3 备份保留期限

| 备份类型 | 保留期限 | 说明 |
|---------|---------|------|
| 最近 7 天的备份 | 7 天 | 所有备份自动保留 |
| 7-30 天的备份 | 保留最多 3 个 | 保留最重要的 3 个 |
| 30 天以上的备份 | 保留最多 1 个 | 仅保留最后一次成功部署 |
| 失败彩排的备份 | 立即清理 | 彩排失败的备份不长期保留 |

### 2.4 备份清理策略

#### 自动清理（推荐）

```bash
# 清理 30 天以上的备份（保留最新的 1 个）
find .sisyphus/runtime/backups/ -name "backup-manifest.v*.txt" -mtime +30 -type f | \
  sort -r | tail -n +2 | \
  xargs -I {} bash -c 'tag=$(basename {} .txt); rm -f .sisyphus/runtime/backups/*${tag#backup-manifest.}*'

# 清理失败彩排的备份
grep -l '"result": "FAILED"' .sisyphus/runtime/rehearsal-*.json 2>/dev/null | \
  xargs -I {} bash -c 'tag=$(jq -r .backup_tag {}); rm -f .sisyphus/runtime/backups/*${tag}*'
```

#### 手动清理

```bash
# 列出所有备份
ls -lht .sisyphus/runtime/backups/backup-manifest.v*.txt

# 删除特定备份
BACKUP_TAG="v20240322_143025"
rm -f .sisyphus/runtime/backups/*${BACKUP_TAG}*

# 清空所有备份（谨慎操作！）
rm -rf .sisyphus/runtime/backups/*
```

### 2.5 恢复流程

#### 使用回滚脚本（推荐）

```bash
# 1. 查看可用备份
bash scripts/deployment/bigbang-rollback.sh

# 2. 回滚到特定备份
bash scripts/deployment/bigbang-rollback.sh v20240322_143025
```

#### 手动恢复

```bash
BACKUP_TAG="v20240322_143025"
BACKUP_DIR=".sisyphus/runtime/backups"

# 停止服务
bash scripts/deployment/intranet-single-node-stop.sh

# 恢复文件
cp ${BACKUP_DIR}/requirements.txt.${BACKUP_TAG} requirements.txt
cp ${BACKUP_DIR}/package.json.${BACKUP_TAG} frontend/package.json
cp ${BACKUP_DIR}/.env.intranet.${BACKUP_TAG} .env.intranet

# 恢复配置
cp -r ${BACKUP_DIR}/config.${BACKUP_TAG}/* config/

# 重新安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 启动服务
bash scripts/deployment/intranet-single-node-start.sh
```

### 2.6 备份验证

每次备份后，验证以下内容：

```bash
# 1. 验证备份文件完整性
BACKUP_TAG="v20240322_143025"
for file in requirements.txt.${BACKUP_TAG} package.json.${BACKUP_TAG} .env.intranet.${BACKUP_TAG}; do
  [ -f ".sisyphus/runtime/backups/${file}" ] && echo "✓ ${file}" || echo "✗ ${file} missing"
done

# 2. 验证备份清单
cat .sisyphus/runtime/backups/backup-manifest.${BACKUP_TAG}.txt

# 3. 验证文件哈希（可选）
sha256sum .sisyphus/runtime/backups/*${BACKUP_TAG}* > .sisyphus/runtime/backups/checksum-${BACKUP_TAG}.txt
```

### 2.7 数据快照恢复（导出 / 恢复 / 重建索引）

Big-Bang 脚本当前主要覆盖依赖与配置回滚；记忆数据建议通过 API 快照完成恢复演练。

```bash
# 1) 导出当前记忆快照
curl -sS "http://127.0.0.1:8000/api/v1/data/export" \
  -o .sisyphus/runtime/backups/memory-export.$(date +%Y%m%d_%H%M%S).json

# 2) 先做 dry-run 预校验（不落库、不清空、不重建）
curl -sS -X POST "http://127.0.0.1:8000/api/v1/data/restore?dry_run=true" \
  -F "file=@.sisyphus/runtime/backups/memory-export.20260402_120000.json"

# 3) 使用导出快照恢复（默认先清空并重建索引）
curl -sS -X POST "http://127.0.0.1:8000/api/v1/data/restore" \
  -F "file=@.sisyphus/runtime/backups/memory-export.20260402_120000.json"
```

`/api/v1/data/export` 的快照会包含 `manifest`，至少包括：

- `format`：导出格式标识（当前为 `memory_graph_export`）
- `version`：导出格式版本
- `exported_at`：导出时间（UTC ISO 8601）
- `counts`：`memories/entities/relationships` 条目数

可选参数：

- `dry_run=true`：只做 payload + manifest 校验，不写入数据。
- `clear_existing=false`：不清空现有数据，直接恢复快照中的 memories。
- `reindex=false`：恢复后不触发索引重建。
- `reembed=true&batch_size=32`：恢复后重建索引并重算 embedding。

示例：

```bash
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/data/restore?clear_existing=true&reindex=true&reembed=true&batch_size=32" \
  -F "file=@.sisyphus/runtime/backups/memory-export.20260402_120000.json"
```

---

## 3. 失败决策树

### 3.1 切换彩排失败处理流程

```
开始切换彩排
    │
    ├─ 1. 停止服务
    │       ├─ 成功 → 继续
    │       └─ 失败 → 手动清理进程，重新执行
    │
    ├─ 2. 备份当前版本
    │       ├─ 成功 → 继续
    │       └─ 失败 → 检查磁盘空间/权限，重试或中止
    │
    ├─ 3. 启动新版本
    │       ├─ 成功 → 继续
    │       └─ 失败 → 检查依赖/配置，回滚到备份
    │
    ├─ 4. 运行健康检查
    │       ├─ 全部通过 → 继续
    │       └─ 失败 → 查看日志，自动回滚
    │
    └─ 5. 运行冒烟测试
            ├─ 全部通过 → ✓ 彩排成功
            └─ 失败 → 查看日志，自动回滚
```

### 3.2 回滚失败处理流程

```
开始回滚
    │
    ├─ 1. 验证备份
    │       ├─ 成功 → 继续
    │       └─ 失败 → 查找其他备份或手动恢复
    │
    ├─ 2. 停止当前服务
    │       ├─ 成功 → 继续
    │       └─ 失败 → 强制终止进程
    │
    ├─ 3. 恢复文件
    │       ├─ 成功 → 继续
    │       └─ 失败 → 检查备份完整性，尝试手动恢复
    │
    ├─ 4. 重装依赖
    │       ├─ 成功 → 继续
    │       └─ 失败 → 检查网络/权限，使用缓存重试
    │
    ├─ 5. 启动旧版本
    │       ├─ 成功 → 继续
    │       └─ 失败 → 检查端口/配置，排查冲突
    │
    └─ 6. 验证回滚
            ├─ 全部通过 → ✓ 回滚成功
            └─ 失败 → 查看日志，人工介入处理
```

### 3.3 失败场景决策树

#### 场景 A: 健康检查失败

```
健康检查失败
    │
    ├─ 检查日志文件
    │   ├─ 有明显错误信息 →
    │   │   ├─ 依赖缺失 → 重新安装依赖
    │   │   ├─ 配置错误 → 修复配置文件
    │   │   ├─ 端口冲突 → 修改端口配置
    │   │   └─ 其他错误 → 查看详细日志
    │   └─ 无错误信息 →
    │       ├─ 服务未完全启动 → 增加等待时间
    │       └─ 网络问题 → 检查防火墙/代理
    │
    ├─ 快速修复后
    │   ├─ 再次运行健康检查 → 通过 → 继续冒烟测试
    │   └─ 再次运行健康检查 → 失败 → 自动回滚
    │
    └─ 自动回滚
        ├─ 成功 → 分析失败原因，修复后重新彩排
        └─ 失败 → 人工介入处理
```

#### 场景 B: 冒烟测试失败

```
冒烟测试失败
    │
    ├─ 检查失败的端点
    │   ├─ /health 失败 → 服务未正常启动
    │   ├─ /ready 失败 → 服务未完全就绪
    │   ├─ 前端失败 → 构建或静态文件问题
    │   └─ /api/v1/query 失败 → API 逻辑问题
    │
    ├─ 端点级别排查
    │   ├─ 端点不存在 → 代码版本问题
    │   ├─ 返回状态码错误 → 逻辑或权限问题
    │   └─ 返回数据错误 → 数据格式问题
    │
    ├─ 判断修复难度
    │   ├─ 可快速修复 → 修复后继续验证
    │   └─ 需要长时间 → 自动回滚
    │
    └─ 自动回滚
        ├─ 成功 → 记录失败原因，修复后重新彩排
        └─ 失败 → 人工介入处理
```

#### 场景 C: 回滚失败

```
回滚失败
    │
    ├─ 确定失败阶段
    │   ├─ 备份验证失败 →
    │   │   ├─ 备份文件损坏 → 尝试其他备份
    │   │   └─ 备份清单缺失 → 手动重建清单
    │   ├─ 文件恢复失败 →
    │   │   ├─ 磁盘空间不足 → 清理临时文件
    │   │   └─ 权限问题 → 检查文件权限
    │   ├─ 依赖重装失败 →
    │   │   ├─ 网络问题 → 使用 pip/npm 缓存
    │   │   └─ 依赖冲突 → 手动解决冲突
    │   └─ 服务启动失败 →
    │       ├─ 端口冲突 → 终止占用进程
    │       └─ 配置问题 → 验证环境变量
    │
    ├─ 尝试备用方案
    │   ├─ 使用其他备份
    │   ├─ 手动恢复文件
    │   └─ 重新安装环境
    │
    └─ 所有方案失败
        ├─ 联系运维团队
        ├─ 查看系统日志
        ├─ 检查系统资源
        └─ 考虑紧急降级方案
```

### 3.4 紧急降级流程

如果所有回滚方案都失败，使用紧急降级流程：

```bash
# 1. 停止所有服务
bash scripts/deployment/intranet-single-node-stop.sh

# 2. 切换到已知的稳定版本（如果有）
git checkout <stable-branch-tag>
bash scripts/deployment/intranet-single-node-start.sh

# 3. 或者从 Git 历史中恢复
git log --oneline -10
git checkout <previous-working-commit>

# 4. 重新安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 5. 启动服务
bash scripts/deployment/intranet-single-node-start.sh
```

---

## 4. QA 场景

### 4.1 场景 1: 切换彩排成功验证

**目标**: 验证 Big-Bang 切换彩排能够成功完成

**步骤**:

1. 确保服务当前运行正常
   ```bash
   bash scripts/deployment/intranet-health-check.sh
   ```

2. 执行切换彩排
   ```bash
   bash scripts/deployment/bigbang-rehearsal.sh
   ```

3. 验证彩排结果
   ```bash
   # 查看彩排日志
   cat .sisyphus/runtime/logs/rehearsal-health-check-*.log

   # 查看彩排结果记录
   cat .sisyphus/runtime/rehearsal-*.json | jq .
   ```

4. 运行验证检查
   ```bash
   bash scripts/deployment/bigbang-rehearsal-verify.sh
   ```

**预期结果**:

- ✓ 所有健康检查通过
- ✓ 所有冒烟测试通过
- ✓ 彩排结果记录显示 `"result": "SUCCESS"`
- ✓ 验证报告显示 `"overall_status": "PASS"`
- ✓ 备份文件创建在 `.sisyphus/runtime/backups/`

**失败指标**:

- ✗ 任何健康检查失败
- ✗ 任何冒烟测试失败
- ✗ 彩排结果记录显示 `"result": "FAILED"`
- ✗ 验证报告显示 `"overall_status": "FAIL"`
- ✗ 备份文件未创建或损坏

**证据文件**: `.sisyphus/evidence/task-17-rehearsal-success.txt`

### 4.2 场景 2: 回滚演练验证

**目标**: 验证 Big-Bang 回滚能够成功执行

**步骤**:

1. 确保服务当前运行正常
   ```bash
   bash scripts/deployment/intranet-health-check.sh
   ```

2. 获取最新备份标签
   ```bash
   ls -lht .sisyphus/runtime/backups/backup-manifest.v*.txt | head -1
   # 提取备份标签，例如: v20240322_143025
   ```

3. 执行回滚
   ```bash
   bash scripts/deployment/bigbang-rollback.sh <BACKUP_TAG>
   ```

4. 验证回滚结果
   ```bash
   # 查看回滚日志
   cat .sisyphus/runtime/logs/rollback-verify-*.log

   # 查看回滚结果记录
   cat .sisyphus/runtime/rollback-*.json | jq .
   ```

5. 运行验证检查
   ```bash
   bash scripts/deployment/bigbang-rehearsal-verify.sh
   ```

6. 验证文件已恢复到备份版本
   ```bash
   # 检查 requirements.txt 是否恢复
   diff requirements.txt .sisyphus/runtime/backups/requirements.txt.<BACKUP_TAG>

   # 检查 package.json 是否恢复
   diff frontend/package.json .sisyphus/runtime/backups/package.json.<BACKUP_TAG>
   ```

**预期结果**:

- ✓ 回滚成功完成
- ✓ 所有服务启动正常
- ✓ 所有健康检查通过
- ✓ 回滚结果记录显示 `"result": "SUCCESS"`
- ✓ 验证报告显示 `"overall_status": "PASS"`
- ✓ 文件已恢复到备份版本

**失败指标**:

- ✗ 回滚过程中任何步骤失败
- ✗ 服务无法启动
- ✗ 健康检查失败
- ✗ 回滚结果记录显示 `"result": "FAILED"`
- ✗ 文件未正确恢复

**证据文件**: `.sisyphus/evidence/task-17-rollback-success.txt`

---

## 5. 使用指南

### 5.1 日常使用流程

#### 正式发布前

```bash
# 1. 更新代码
git pull origin main

# 2. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 3. 执行切换彩排
bash scripts/deployment/bigbang-rehearsal.sh

# 4. 如果彩排成功，执行验证
bash scripts/deployment/bigbang-rehearsal-verify.sh

# 5. 记录彩排标签（用于可能的回滚）
BACKUP_TAG=$(cat .sisyphus/runtime/rehearsal-*.json | jq -r '.backup_tag' | tail -1)
echo "Rehearsal backup tag: ${BACKUP_TAG}"
```

#### 发布后出现问题

```bash
# 1. 执行回滚
bash scripts/deployment/bigbang-rollback.sh <BACKUP_TAG>

# 2. 验证回滚
bash scripts/deployment/bigbang-rehearsal-verify.sh

# 3. 分析问题原因
cat .sisyphus/runtime/logs/rehearsal-health-check-*.log
```

### 5.2 定期维护

```bash
# 每周清理旧备份
find .sisyphus/runtime/backups/ -name "backup-manifest.v*.txt" -mtime +30 -type f | \
  sort -r | tail -n +2 | \
  xargs -I {} bash -c 'tag=$(basename {} .txt); rm -f .sisyphus/runtime/backups/*${tag#backup-manifest.}*'

# 每月检查备份完整性
for manifest in .sisyphus/runtime/backups/backup-manifest.v*.txt; do
  BACKUP_TAG=$(basename "${manifest}" .txt | sed 's/backup-manifest.//')
  echo "Checking backup: ${BACKUP_TAG}"
  for file in requirements.txt.${BACKUP_TAG} package.json.${BACKUP_TAG} .env.intranet.${BACKUP_TAG}; do
    [ -f ".sisyphus/runtime/backups/${file}" ] && echo "  ✓ ${file}" || echo "  ✗ ${file} missing"
  done
done
```

---

## 6. 故障排查

### 6.1 常见问题

#### 问题 1: 彩排脚本无法执行

```bash
# 错误: Permission denied
# 解决: 添加执行权限
chmod +x scripts/deployment/bigbang-rehearsal.sh
chmod +x scripts/deployment/bigbang-rollback.sh
chmod +x scripts/deployment/bigbang-rehearsal-verify.sh
```

#### 问题 2: 备份目录不存在

```bash
# 错误: No such file or directory
# 解决: 创建备份目录
mkdir -p .sisyphus/runtime/backups
```

#### 问题 3: 端口冲突

```bash
# 错误: Port conflict detected
# 解决: 终止占用端口的进程或修改端口配置
# 查找占用端口的进程
lsof -ti :8000 | xargs kill -9
lsof -ti :3001 | xargs kill -9
# 注意：前端现在由 FastAPI 托管，不再需要 5173 端口
```

#### 问题 4: 依赖安装失败

```bash
# 错误: pip install failed / npm install failed
# 解决: 检查网络连接，使用镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cd frontend && npm install --registry=https://registry.npmmirror.com && cd ..
```

### 6.2 日志文件位置

| 日志类型 | 文件路径 | 说明 |
|---------|---------|------|
| Python API | `.sisyphus/runtime/logs/py-api.log` | 后端 API 日志 |
| Sidecar API | `.sisyphus/runtime/logs/sidecar.log` | Sidecar 服务日志 |
| Frontend | `.sisyphus/runtime/logs/frontend.log` | 前端开发服务器日志 |
| 彩排健康检查 | `.sisyphus/runtime/logs/rehearsal-health-check-*.log` | 彩排健康检查日志 |
| 回滚验证 | `.sisyphus/runtime/logs/rollback-verify-*.log` | 回滚验证日志 |
| 依赖重装 | `.sisyphus/runtime/logs/rollback-*-install-*.log` | 回滚时的依赖安装日志 |

---

## 7. 安全注意事项

1. **环境变量安全**: 备份包含 `.env.intranet` 文件，可能包含敏感信息
   - 确保备份目录权限正确 (`chmod 700 .sisyphus/runtime`)
   - 不要将备份目录提交到 Git

2. **备份数据保护**:
   - 定期清理旧备份
   - 限制备份目录访问权限
   - 考虑对敏感备份进行加密

3. **回滚权限**:
   - 仅授权运维人员执行回滚
   - 回滚操作应在监控下进行
   - 记录所有回滚操作

---

## 8. T17 证据文件

### QA 场景证据

- `.sisyphus/evidence/task-17-rehearsal-success.txt` - 切换彩排成功验证证据
- `.sisyphus/evidence/task-17-rollback-success.txt` - 回滚演练验证证据

### 运行时证据

- `.sisyphus/runtime/rehearsal-*.json` - 彩排结果记录
- `.sisyphus/runtime/rollback-*.json` - 回滚结果记录
- `.sisyphus/runtime/verification-report-*.json` - 验证报告

---

## 9. 结论

T17 完成了 Big-Bang 切换彩排与回滚资产准备，提供了：

✅ 完整的切换彩排流程（备份、升级、验证）
✅ 可靠的回滚机制（自动回滚、手动回滚）
✅ 清晰的旧版本保留策略（备份内容、保留期限、清理策略）
✅ 详细的失败决策树（失败场景、处理流程、紧急降级）
✅ 全面的 QA 场景（切换彩排验证、回滚演练验证）

这些资产为 Memory Graph 项目的平滑升级提供了保障，确保在部署失败时能够快速恢复服务。
