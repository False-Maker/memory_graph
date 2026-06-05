# Deployment Standardization

## 状态

`Deployment Standardization` 已落地。当前仓库已经同时提供：

- shell 单节点交付件
- systemd 服务模板
- Docker Compose 模板
- Nginx / Caddy 反向代理示例

统一目标只有一个：让不同部署形态都映射到同一套运行边界和同一套健康检查契约，而不是再发明第二套运行模型。

## 统一服务边界

标准服务名：

- `memory-graph-api`
- `memory-graph-sidecar`
- `memory-graph-mcp`

职责边界：

- `memory-graph-api`
  - 托管 FastAPI 与 `frontend/dist`
  - 对外提供 `/`、`/health`、`/api/v1/*`、`/sidecar/*` 代理
- `memory-graph-sidecar`
  - 提供 sidecar `/health`、`/ready`
  - 只作为 API 的内部依赖，不建议直接公网暴露
- `memory-graph-mcp`
  - 独立运行 `streamable-http` MCP 协议面
  - 不并入 FastAPI 进程

## 统一环境变量模型

默认入口仍然是项目根目录的 `.env.intranet`。

相关样例：

- `scripts/deployment/.env.intranet.example`
- `scripts/deployment/.env.mcp.example`
- `scripts/deployment/compose/.env.compose.example`
- `requirements-runtime.txt`
- `requirements-local-embedding.txt`

使用约定：

- `.env.intranet`
  - Web/API/Sidecar 的默认部署入口
  - 也可以承载 MCP 的共享运行变量
- `.env.mcp`
  - 可选
  - 只在你希望把 MCP transport 参数独立出来时使用
- `scripts/deployment/compose/.env.compose`
  - 只存 Compose 自己的端口与 project name 覆盖
  - 不替代 `.env.intranet`
  - 推荐只放 `COMPOSE_*` 这类宿主机发布端口，不覆盖应用运行时端口
  - `COMPOSE_INCLUDE_LOCAL_EMBEDDING=true` 时才把 `sentence-transformers` 装进运行镜像

当前 MCP canonical 脚本优先读取：

1. shell 显式覆盖
2. `.env.intranet`
3. `.env.mcp`
4. 默认值

兼容性约定：

- 现在推荐使用 `MEMORY_GRAPH_MCP_*` 变量
- 旧 `MCP_*` 变量仍然兼容读取

## 统一健康检查契约

所有部署模板最终都要映射到下面这组验收：

HTTP / Web：

- `GET /`
- `GET /health`
- `GET /api/v1/diagnostics/runtime`
- `GET /sidecar/health`
- `GET /sidecar/ready`
- `POST /api/v1/query`

MCP：

- `initialize`
- `list_tools`
- `read_resource(memory-graph://stats)`

当前脚本落点：

- HTTP 契约：`bash scripts/deployment/intranet-health-check.sh`
- Cloud smoke：`bash scripts/deployment/cloud-smoke-check.sh`
- MCP 协议级检查：`bash scripts/deployment/mcp-health-check.sh`
- Docker 内 nginx 反向代理联调：`bash scripts/deployment/nginx-proxy-docker-smoke.sh`

说明：

- `mcp-health-check.sh` 现在已经不是端口级探测，而是通过官方 Python MCP SDK 做真实协议检查。
- `mcp-streamable-http-health-check.sh` 仍保留，但已经退化为兼容包装，最终委托 `mcp-health-check.sh`。

## Shell 交付件

### Web/API/Sidecar 单节点

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
bash scripts/deployment/intranet-single-node-start.sh
bash scripts/deployment/intranet-health-check.sh
bash scripts/deployment/intranet-single-node-stop.sh
```

对应文件：

- `scripts/deployment/intranet-single-node-start.sh`
- `scripts/deployment/intranet-single-node-stop.sh`
- `scripts/deployment/intranet-health-check.sh`
- `scripts/deployment/intranet-port-conflict-check.sh`

### MCP 独立部署

推荐 canonical 命令：

```bash
cp scripts/deployment/.env.mcp.example .env.mcp  # 可选
bash scripts/deployment/mcp-start.sh
bash scripts/deployment/mcp-health-check.sh
bash scripts/deployment/mcp-stop.sh
```

兼容命令仍可用，但只是包装：

```bash
bash scripts/deployment/mcp-streamable-http-start.sh
bash scripts/deployment/mcp-streamable-http-health-check.sh
bash scripts/deployment/mcp-streamable-http-stop.sh
```

## systemd 模板

模板路径：

- `scripts/deployment/systemd/memory-graph-api.service.example`
- `scripts/deployment/systemd/memory-graph-sidecar.service.example`
- `scripts/deployment/systemd/memory-graph-mcp.service.example`

建议安装流程：

```bash
sudo cp scripts/deployment/systemd/memory-graph-api.service.example /etc/systemd/system/memory-graph-api.service
sudo cp scripts/deployment/systemd/memory-graph-sidecar.service.example /etc/systemd/system/memory-graph-sidecar.service
sudo cp scripts/deployment/systemd/memory-graph-mcp.service.example /etc/systemd/system/memory-graph-mcp.service
sudo systemctl daemon-reload
sudo systemctl enable --now memory-graph-sidecar.service
sudo systemctl enable --now memory-graph-api.service
sudo systemctl enable --now memory-graph-mcp.service
```

systemd 模板默认假设：

- 仓库路径是 `/srv/memory-graph`
- 运行用户/组是 `memorygraph`
- `.env.intranet` 与 `.env.mcp` 放在仓库根目录

部署后验收仍使用同一套 shell 健康脚本：

```bash
bash scripts/deployment/intranet-health-check.sh
bash scripts/deployment/mcp-health-check.sh
```

## Docker Compose 模板

模板路径：

- `scripts/deployment/compose/docker-compose.yml`
- `scripts/deployment/compose/.env.compose.example`
- `scripts/deployment/compose/Dockerfile.api`
- `scripts/deployment/compose/Dockerfile.sidecar`
- `scripts/deployment/compose/Dockerfile.mcp`

依赖拆分：

- `requirements-runtime.txt`
  - 默认运行镜像安装
  - 不包含 `sentence-transformers`
- `requirements-local-embedding.txt`
  - 只在 `COMPOSE_INCLUDE_LOCAL_EMBEDDING=true` 时附加安装
  - 用于需要本地 embedding provider 的部署

建议启动流程：

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
cp scripts/deployment/.env.mcp.example .env.mcp  # 可选
cp scripts/deployment/compose/.env.compose.example scripts/deployment/compose/.env.compose

docker compose \
  --env-file ./.env.intranet \
  --env-file ./scripts/deployment/compose/.env.compose \
  -f scripts/deployment/compose/docker-compose.yml \
  up -d --build
```

停止：

```bash
docker compose \
  --env-file ./.env.intranet \
  --env-file ./scripts/deployment/compose/.env.compose \
  -f scripts/deployment/compose/docker-compose.yml \
  down
```

Compose 模板特点：

- 服务名直接对齐 `memory-graph-api` / `memory-graph-sidecar` / `memory-graph-mcp`
- API 与 MCP 共享 `config` 与 `data` 挂载
- sidecar 只做容器内暴露，不默认单独发布到公网
- 容器健康检查仍映射到统一 HTTP/MCP 契约
- 宿主机发布端口通过 `COMPOSE_API_PUBLISHED_PORT` / `COMPOSE_MCP_PUBLISHED_PORT` 控制，不再覆盖 `.env.intranet` 内部运行端口
- 默认运行镜像不安装本地 `sentence-transformers` 栈，先用远程 embedding 路径换取更小镜像

## 反向代理示例

样例路径：

- `docs/deployment/reverse-proxy-nginx.sample.conf`
- `docs/deployment/reverse-proxy-caddy.sample`

约束：

- Web/API 代理到 `127.0.0.1:8000`
- MCP 代理到 `127.0.0.1:8001`
- `Authorization` 头需要透传到 MCP
- 不单独对外暴露 sidecar

当前额外验证入口：

```bash
bash scripts/deployment/nginx-proxy-docker-smoke.sh
```

这个脚本会在 Docker 网络内真实起一个 `nginx` 容器，验证：

- `/` 代理到 FastAPI
- `/health` 与 `/api/v1/diagnostics/runtime` 代理链路
- `/mcp` 代理到 MCP server，且 Bearer token 能透传

## 关联文档

- [t15-intranet-deployment.md](./t15-intranet-deployment.md)
- [t18-mcp-deployment.md](./t18-mcp-deployment.md)
- [t18-mcp-streamable-http.md](./t18-mcp-streamable-http.md)
- [t6-dual-deployment-baseline.md](./t6-dual-deployment-baseline.md)
