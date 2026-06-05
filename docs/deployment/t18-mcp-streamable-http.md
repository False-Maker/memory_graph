# T18 MCP Streamable HTTP Deployment

统一入口见 [standardization.md](./standardization.md)。

## 范围

当前交付的是独立于 FastAPI 的 MCP 协议面，面向：

- Claude Desktop / 本地 agent 的 `stdio`
- Cursor / OpenAI Agents / 远程 agent 的 `streamable-http`

本文档只覆盖 `streamable-http` 部署与验收；`stdio` 仍以本地开发命令为主。

## 文件清单

- `scripts/deployment/mcp-start.sh`
- `scripts/deployment/mcp-stop.sh`
- `scripts/deployment/mcp-health-check.sh`
- `scripts/deployment/mcp-streamable-http-start.sh`
- `scripts/deployment/mcp-streamable-http-stop.sh`
- `scripts/deployment/mcp-streamable-http-health-check.sh`

## 启动前准备

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
cp scripts/deployment/.env.mcp.example .env.mcp  # 可选
```

常用变量：

- `MEMORY_GRAPH_MCP_HOST`，默认 `127.0.0.1`
- `MEMORY_GRAPH_MCP_PORT`，默认 `8001`
- `MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH`，默认 `/mcp`
- `MEMORY_GRAPH_MCP_MOUNT_PATH`，默认 `/`
- `MEMORY_GRAPH_MCP_STATELESS_HTTP`，默认 `true`
- `MEMORY_GRAPH_MCP_BEARER_TOKEN`，启用后要求客户端带 `Authorization: Bearer <token>`
- `PYTHON_BIN`

## 启动

推荐 canonical 命令：

```bash
bash scripts/deployment/mcp-start.sh
```

兼容包装命令仍可使用：

```bash
bash scripts/deployment/mcp-streamable-http-start.sh
```

当前行为：

1. `mcp-start.sh` 读取 `.env.intranet`，再读取 `.env.mcp`（如果存在）
2. 解析 MCP host / port / path
3. 检查端口占用
4. 以 `python -m src.mcp --transport streamable-http` 启动 MCP server
5. 立即执行协议级健康检查

`mcp-streamable-http-start.sh` 现在只是兼容包装，最终委托 `mcp-start.sh`。

运行时产物：

- PID: `.sisyphus/runtime/pids/mcp.pid`
- 日志: `.sisyphus/runtime/logs/mcp.log`

## 健康检查 / 冒烟

```bash
bash scripts/deployment/mcp-health-check.sh
```

健康检查会通过官方 Python MCP SDK 完成：

1. `initialize`
2. `list_tools`
3. 校验核心工具存在
4. `read_resource(memory-graph://stats)`

这不是简单端口探测，而是真实协议级检查。

如果设置了 `MEMORY_GRAPH_MCP_BEARER_TOKEN`，健康检查脚本会自动带上对应 Bearer token。

## 停止

推荐 canonical 命令：

```bash
bash scripts/deployment/mcp-stop.sh
```

兼容包装命令：

```bash
bash scripts/deployment/mcp-streamable-http-stop.sh
```

## 当前建议验收命令

```bash
bash scripts/deployment/mcp-start.sh
bash scripts/deployment/mcp-health-check.sh
bash scripts/deployment/mcp-stop.sh
```
