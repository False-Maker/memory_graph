# T17 Big-Bang 切换彩排与回滚资产准备

## 概述

本任务为 Desktop-to-Web 重构计划的最后关口任务，在正式执行 Big-Bang 切换前，必须完成完整的彩排演练并准备回滚资产。

## 执行时间

**创建时间**: 2026-03-22 03:06:00
**脚本位置**: `scripts/deployment/`

## 交付物

### 1. 彩排脚本

**文件**: `scripts/deployment/bigbang-rehearsal.sh`

**功能**:
- 停止当前服务
- 备份当前版本（依赖、配置、环境变量）
- 启动新版本
- 运行健康检查
- 运行冒烟测试
- 自动回滚（失败时）

**使用方法**:
```bash
# 执行彩排
bash scripts/deployment/bigbang-rehearsal.sh
```

**输出**:
- 备份目录: `.sisyphus/runtime/backups/`
- 彩排结果: `.sisyphus/runtime/rehearsal-<TIMESTAMP>.json`
- 健康检查日志: `.sisyphus/runtime/logs/rehearsal-health-check-<TIMESTAMP>.log`

### 2. 回滚脚本

**文件**: `scripts/deployment/bigbang-rollback.sh`

**功能**:
- 验证备份存在
- 停止当前服务
- 恢复依赖文件
- 恢复配置文件
- 恢复环境变量
- 启动恢复后的服务
- 运行回滚验证

**使用方法**:
```bash
# 查看可用备份
bash scripts/deployment/bigbang-rollback.sh

# 回滚到指定备份
bash scripts/deployment/bigbang-rollback.sh v20260322_030600
```

**输出**:
- 回滚结果: `.sisyphus/runtime/rollback-<TIMESTAMP>.json`
- 验证日志: `.sisyphus/runtime/logs/rollback-verify-<TIMESTAMP>.log`

### 3. 彩排验证脚本

**文件**: `scripts/deployment/bigbang-rehearsal-verify.sh`

**功能**:
- 查找最新的彩排结果
- 解析彩排结果状态
- 验证备份文件完整性
- 验证彩排日志存在
- 打印彩排摘要

**使用方法**:
```bash
# 验证彩排结果
bash scripts/deployment/bigbang-rehearsal-verify.sh
```

## 旧版本保留策略

### 保留内容

在每次彩排/部署前，自动备份以下内容：

1. **Python 依赖**
   - 文件: `requirements.txt`
   - 备份位置: `.sisyphus/runtime/backups/requirements.txt.<BACKUP_TAG>`

2. **前端依赖**
   - 文件: `frontend/package.json`
   - 备份位置: `.sisyphus/runtime/backups/package.json.<BACKUP_TAG>`
   - 注: `node_modules` 不备份，回滚时重新安装

3. **环境变量**
   - 文件: `.env.intranet`
   - 备份位置: `.sisyphus/runtime/backups/.env.intranet.<BACKUP_TAG>`
   - 注: 敏感信息需手动过滤（API 密钥、密码等）

4. **配置文件**
   - 目录: `config/`
   - 备份位置: `.sisyphus/runtime/backups/config.<BACKUP_TAG>/`

5. **备份清单**
   - 文件: `.sisyphus/runtime/backups/backup-manifest.<BACKUP_TAG>.txt`
   - 内容: 备份时间戳、备份标签、文件清单、部署元数据

### 保留策略

| 类型 | 保留周期 | 数量限制 | 清理策略 |
|------|---------|---------|---------|
| 彩排备份 | 7 天 | 无限制 | 7 天后自动清理 |
| 正式部署备份 | 30 天 | 保留最近 5 个 | 30 天后自动清理 |
| 回滚记录 | 30 天 | 无限制 | 30 天后自动清理 |

### 手动清理

如需手动清理旧备份：

```bash
# 删除指定备份
rm .sisyphus/runtime/backups/*.<BACKUP_TAG>*

# 清理 7 天前的备份
find .sisyphus/runtime/backups -name "*.*" -mtime +7 -delete
```

## 失败决策树

### 决策树图

```
[彩排开始]
    |
    v
[停止服务]
    |
    v
[备份当前版本] --> 失败 --> [终止彩排] --> [检查磁盘空间/权限]
    |
    v
[启动新版本] --> 失败 --> [自动回滚] --> [检查依赖/配置]
    |
    v
[等待 30 秒]
    |
    v
[健康检查]
    |
    +--> 失败 --> [自动回滚]
    |              |
    |              v
    |         [停止新版本]
    |              |
    |              v
    |         [恢复旧版本]
    |              |
    |              v
    |         [启动旧版本]
    |              |
    |              v
    |         [验证回滚]
    |              |
    |              +--> 失败 --> [人工介入]
    |
    v
[冒烟测试]
    |
    +--> 失败 --> [自动回滚]
    |
    v
[记录成功]
    |
    v
[彩排通过]
```

### 失败类型与处理

| 失败阶段 | 失败类型 | 自动处理 | 人工介入 |
|---------|---------|---------|---------|
| 停止服务 | 进程无响应 | 否 | 检查进程状态，手动 kill |
| 备份版本 | 磁盘空间不足 | 否 | 清理磁盘空间 |
| 备份版本 | 权限不足 | 否 | 检查文件权限 |
| 启动版本 | 依赖缺失 | 否 | 检查 requirements.txt / package.json |
| 启动版本 | 端口冲突 | 否 | 检查端口占用 |
| 健康检查 | API 超时 | 是 | 检查日志，调整超时时间 |
| 健康检查 | 错误码 | 是 | 检查错误原因 |
| 冒烟测试 | 端点异常 | 是 | 检查 API 路由配置 |
| 回滚验证 | 恢复失败 | 否 | 检查备份文件完整性 |
| 回滚验证 | 启动失败 | 否 | 检查依赖/配置 |

### 人工介入清单

当自动处理失败时，需要人工介入：

1. **检查日志**
   ```bash
   # 查看彩排日志
   cat .sisyphus/runtime/logs/rehearsal-health-check-<TIMESTAMP>.log

   # 查看回滚日志
   cat .sisyphus/runtime/logs/rollback-verify-<TIMESTAMP>.log
   ```

2. **检查服务状态**
   ```bash
   # 检查 Python API
   curl http://127.0.0.1:8000/health

   # 检查 Sidecar
   curl http://127.0.0.1:3001/health

   # 检查前端（FastAPI 托管）
   curl http://127.0.0.1:8000/
   ```

3. **检查进程**
   ```bash
   # 查看进程状态
   ps aux | grep -E "python|uvicorn|nest|node"

   # 查看端口占用（FastAPI 托管后不再需要 5173 端口）
   netstat -tlnp | grep -E "8000|3001"
   ```

4. **检查环境变量**
   ```bash
   # 检查环境变量加载
   bash scripts/deployment/check-required-env.sh
   ```

## QA 场景验证

### 场景 1: 切换彩排成功

**前置条件**:
- 内网环境已准备
- 环境变量已配置
- 服务依赖已安装

**执行步骤**:
```bash
# 1. 执行彩排脚本
cd ~/projects/web/Memory_graph
bash scripts/deployment/bigbang-rehearsal.sh

# 2. 等待彩排完成（约 2-3 分钟）

# 3. 验证彩排结果
bash scripts/deployment/bigbang-rehearsal-verify.sh
```

**预期结果**:
- 彩排脚本执行完成
- 所有健康检查通过
- 所有冒烟测试通过
- 备份文件已创建
- 彩排结果记录为 SUCCESS

**证据文件**:
- `.sisyphus/runtime/rehearsal-<TIMESTAMP>.json`
- `.sisyphus/runtime/logs/rehearsal-health-check-<TIMESTAMP>.log`
- `.sisyphus/runtime/backups/backup-manifest.<BACKUP_TAG>.txt`

### 场景 2: 回滚演练

**前置条件**:
- 彩排已成功执行
- 备份文件已创建

**执行步骤**:
```bash
# 1. 在新版本中注入故障（模拟失败）
# 例如：修改配置文件为错误值
sed -i 's/8000/9999/' .env.intranet

# 2. 停止服务
bash scripts/deployment/intranet-single-node-stop.sh

# 3. 尝试启动（预期失败）
bash scripts/deployment/intranet-single-node-start.sh
# 应该启动失败

# 4. 执行回滚
bash scripts/deployment/bigbang-rollback.sh <BACKUP_TAG>

# 5. 验证回滚结果
bash scripts/deployment/intranet-health-check.sh
```

**预期结果**:
- 模拟的故障导致启动失败
- 回滚脚本成功执行
- 旧版本依赖和配置已恢复
- 旧版本服务启动成功
- 健康检查通过

**证据文件**:
- `.sisyphus/runtime/rollback-<TIMESTAMP>.json`
- `.sisyphus/runtime/logs/rollback-verify-<TIMESTAMP>.log`

## 验收标准

### 必须完成 (MUST HAVE)

- [x] 彩排脚本 (`bigbang-rehearsal.sh`) 已创建并可执行
- [x] 回滚脚本 (`bigbang-rollback.sh`) 已创建并可执行
- [x] 验证脚本 (`bigbang-rehearsal-verify.sh`) 已创建并可执行
- [ ] 场景 1: 切换彩排成功验证已执行并生成证据
- [ ] 场景 2: 回滚演练验证已执行并生成证据
- [ ] 旧版本保留策略文档完整
- [ ] 失败决策树文档完整

### 禁止行为 (MUST NOT HAVE)

- [ ] 不在未彩排前直接执行正式切换
- [ ] 不在备份验证失败时继续切换
- [ ] 不在回滚失败时继续使用问题版本
- [ ] 不删除 7 天内的彩排备份
- [ ] 不删除 30 天内的正式部署备份

## 下一步

完成 T17 后，继续执行 **T18: 全量功能对照验收与证据打包**。

T18 将基于 T1 的功能对照矩阵，逐项执行验证并收集证据。
