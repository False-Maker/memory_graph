# Memory Graph 交付手册

**最后更新**: 2026-04-18  
**交付结论**: 当前仓库已经完成主链路与增强阶段四个增强包收口，具备单用户、自托管场景下的产品级交付条件。

---

## 1. 当前交付范围

当前交付件包含：

- React Web 主应用
- FastAPI 后端与公开 HTTP API
- NestJS Sidecar 健康探针
- 独立 MCP Server（`stdio` + `streamable-http` + 可选 Bearer auth）
- Query run tracing、runtime diagnostics、Diagnostics 页面
- shell / systemd / Docker Compose / reverse proxy 四类部署标准件

当前默认交付边界：

- 单机自托管
- 单用户
- 不包含多租户、登录、计费或 SaaS 运营面

---

## 2. 推荐交付路径

推荐按下面顺序交付：

1. shell 单节点
   - 最容易首发
   - 最适合先完成业务验收和用户接收
2. systemd
   - 适合稳定驻留和服务管理
3. Docker Compose
   - 适合集成部署和环境复制
4. reverse proxy
   - 适合需要对外暴露 Web/API/MCP 时接入

如果只是第一次落地，我建议先交付 `shell 单节点 + MCP 独立部署`。

---

## 3. 交付前静态验收

最小交付前回归：

```bash
bash scripts/deployment/final-delivery-check.sh
```

当前仓库内已经真实跑通过的关键回归基线：

- `tests/test_deployment_standardization.py`
- `tests/test_llm_manager.py`
- `tests/test_main_api.py`

最终验收结论见 [FINAL_ACCEPTANCE.md](./FINAL_ACCEPTANCE.md)。

---

## 4. shell 单节点交付

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
bash scripts/deployment/intranet-single-node-start.sh
bash scripts/deployment/intranet-health-check.sh
bash scripts/deployment/intranet-single-node-stop.sh
```

验收项：

- `GET /`
- `GET /health`
- `GET /api/v1/diagnostics/runtime`
- `GET /sidecar/health`
- `GET /sidecar/ready`
- `POST /api/v1/query`

相关文档：

- [standardization.md](./deployment/standardization.md)
- [t15-intranet-deployment.md](./deployment/t15-intranet-deployment.md)

---

## 5. MCP 独立交付

```bash
cp scripts/deployment/.env.mcp.example .env.mcp  # 可选
bash scripts/deployment/mcp-start.sh
bash scripts/deployment/mcp-health-check.sh
bash scripts/deployment/mcp-stop.sh
```

MCP 协议级验收包含：

- `initialize`
- `list_tools`
- `read_resource(memory-graph://stats)`

说明：

- 如果主机 Python 环境里没有官方 `mcp` SDK，先执行 `pip install -r requirements.txt`
- 也可以通过 `MCP_PYTHONPATH=/path/to/sdk` 注入本地 SDK

相关文档：

- [t18-mcp-deployment.md](./deployment/t18-mcp-deployment.md)
- [t18-mcp-streamable-http.md](./deployment/t18-mcp-streamable-http.md)

---

## 6. Docker Compose 交付

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

注意两件事：

- 宿主机发布端口由 `COMPOSE_API_PUBLISHED_PORT` 和 `COMPOSE_MCP_PUBLISHED_PORT` 控制
- 默认镜像不安装本地 `sentence-transformers` 栈；如果必须启用本地 embedding，再设置 `COMPOSE_INCLUDE_LOCAL_EMBEDDING=true`

---

## 7. 当前镜像体积

2026-04-18 的实测结果：

- `memory-graph-api`: 约 `570MB`
- `memory-graph-mcp`: 约 `569MB`
- `memory-graph-sidecar`: 约 `354MB`

说明：

- 默认运行镜像已经去掉本地 `sentence-transformers/torch/CUDA` 依赖链
- 如果显式开启 `COMPOSE_INCLUDE_LOCAL_EMBEDDING=true`，镜像会重新变大

---

## 8. 已知边界

- 当前是单用户交付，不是 SaaS 平台
- `nginx` 已支持通过 Docker 做真实代理联调；`caddy` 仍是模板级交付
- Compose 默认假设当前配置可走远程 embedding；如果交付环境必须依赖本地 embedding，需要显式开启 `COMPOSE_INCLUDE_LOCAL_EMBEDDING=true`

如果需要复测 `nginx` 代理链路：

```bash
bash scripts/deployment/nginx-proxy-docker-smoke.sh
```

---

## 9. 交付清单

交付时至少确认下面这些项：

1. `config/settings.yaml` 已填写实际 provider 配置
2. `.env.intranet` / `.env.mcp` 已按目标环境配置
3. 选定一种主交付方式：shell、systemd 或 Compose
4. 跑完对应健康检查
5. MCP 协议级检查通过
6. README / API / deployment 文档与实际部署方式一致

---

## 10. 关联文档

- [README.md](../README.md)
- [DEVELOPMENT.md](./DEVELOPMENT.md)
- [API.md](./API.md)
- [ROADMAP.md](./ROADMAP.md)
- [ENHANCEMENT_STAGE.md](./ENHANCEMENT_STAGE.md)
- [deployment/standardization.md](./deployment/standardization.md)
