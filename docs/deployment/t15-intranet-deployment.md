# T15 内网部署实现（单节点）

统一入口见 [standardization.md](./standardization.md)。

## 范围

当前脚本实现的是：

- 构建 React Web 到 `frontend/dist`
- 构建并启动 Nest sidecar
- 启动 FastAPI，并由 FastAPI 托管 React Web 构建产物

## 文件清单

- `scripts/deployment/.env.intranet.example`
- `scripts/deployment/intranet-single-node-start.sh`
- `scripts/deployment/intranet-single-node-stop.sh`
- `scripts/deployment/intranet-health-check.sh`
- `scripts/deployment/intranet-port-conflict-check.sh`

## 启动前准备

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
```

至少保证：

- `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` 至少一个已设置
- 如果你显式接入非默认 Neo4j 兼容路径，再额外设置 `NEO4J_URI` / `NEO4J_PASSWORD`

## 启动

```bash
bash scripts/deployment/intranet-single-node-start.sh
```

脚本会执行：

1. 读取 `.env.intranet`
2. 检查必需环境变量
3. 检查 `PY_API_PORT` 和 `SIDECAR_PORT`
4. 构建 React Web
5. 构建并启动 Sidecar
6. 启动 FastAPI，并注入 `SIDECAR_BASE_URL`

如需覆盖 Python 可执行文件，可在 `.env.intranet` 中设置 `PYTHON_BIN`。

## 健康检查

```bash
bash scripts/deployment/intranet-health-check.sh
```

检查项：

- `GET /`
- `GET /health`
- `GET /api/v1/diagnostics/runtime`
- `GET /sidecar/health`
- `GET /sidecar/ready`
- `POST /api/v1/query`

## 停止

```bash
bash scripts/deployment/intranet-single-node-stop.sh
```

## 端口冲突验证

```bash
bash scripts/deployment/intranet-port-conflict-check.sh
```

预期：

- 启动脚本非 0 退出
- 输出包含端口冲突提示
