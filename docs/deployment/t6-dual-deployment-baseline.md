# T6 双部署基线（内网 + 云端）

统一入口见 [standardization.md](./standardization.md)。

## 当前基线

默认部署对象已经统一为：

- React Web 构建产物：`frontend/dist`
- Python API：`src/api/main.py`
- Nest sidecar：`frontend/api`

React Web 不再以 Vite 开发服务器作为默认部署形态。生产时由 FastAPI 直接托管 `frontend/dist`。

## 服务与端口

### 生产/部署基线

- Web 首页：`http://127.0.0.1:${PY_API_PORT:-8000}/`
- Python 健康检查：`http://127.0.0.1:${PY_API_PORT:-8000}/health`
- Runtime diagnostics：`http://127.0.0.1:${PY_API_PORT:-8000}/api/v1/diagnostics/runtime`
- Sidecar 健康代理：`http://127.0.0.1:${PY_API_PORT:-8000}/sidecar/health`
- Sidecar 就绪代理：`http://127.0.0.1:${PY_API_PORT:-8000}/sidecar/ready`
- Sidecar 原生地址：`http://127.0.0.1:${SIDECAR_PORT:-3001}`

### 本地开发基线

- React Web dev server：`http://127.0.0.1:5173`
- React Web preview：`http://127.0.0.1:4173`

## 环境变量

### intranet

必填：

- `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`

可选：

- `PY_API_PORT`，默认 `8000`
- `SIDECAR_PORT`，默认 `3001`
- `LOG_LEVEL`，默认 `INFO`
- `NEO4J_URI` / `NEO4J_PASSWORD`，仅在你显式接入非默认 Neo4j 兼容路径时需要

### cloud

在 intranet 基础上额外要求：

- `PRIVATE_NETWORK_ONLY=true`
- `ALLOWLIST_CIDRS`

## 启动模板

### 内网

```bash
bash scripts/deployment/intranet-baseline.sh
```

脚本会打印：

1. React Web 构建命令
2. Sidecar 启动命令
3. Python API 托管 Web 的启动命令
4. 健康检查命令

### 云端

```bash
cp scripts/deployment/cloud.env.template .env.cloud
set -a && source .env.cloud && set +a
bash scripts/deployment/cloud-baseline.sh
```

## 健康检查

```bash
curl -sf "http://127.0.0.1:${PY_API_PORT:-8000}/"
curl -sf "http://127.0.0.1:${PY_API_PORT:-8000}/health"
curl -sf "http://127.0.0.1:${PY_API_PORT:-8000}/api/v1/diagnostics/runtime"
curl -sf "http://127.0.0.1:${PY_API_PORT:-8000}/sidecar/health"
curl -sf "http://127.0.0.1:${PY_API_PORT:-8000}/sidecar/ready"
```

## 验证命令

### Happy path

```bash
OPENAI_API_KEY=dummy bash scripts/deployment/intranet-baseline.sh
OPENAI_API_KEY=dummy PRIVATE_NETWORK_ONLY=true ALLOWLIST_CIDRS=10.0.0.0/16 bash scripts/deployment/cloud-baseline.sh
```

### Failure path

```bash
unset OPENAI_API_KEY ANTHROPIC_API_KEY
bash scripts/deployment/intranet-baseline.sh

PY_API_PORT=8000 bash scripts/deployment/cloud-network-fail-sim.sh
```
