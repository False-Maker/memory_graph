# T18 MCP Server 部署与运维

统一入口见 [standardization.md](./standardization.md)。

## 范围

这组脚本只负责 `src.mcp` 的最小可交付运维面，不接管现有 Web / Sidecar 部署。

当前提供：

- `scripts/deployment/mcp-start.sh`
- `scripts/deployment/mcp-stop.sh`
- `scripts/deployment/mcp-health-check.sh`

默认模式是 `streamable-http`，目标是给远程 agent、HTTP 直连客户端和联调环境提供独立 MCP 进程。

## 前提

至少满足下面两点：

- 已安装仓库 Python 依赖：`pip install -r requirements.txt`
- Python 运行环境里可导入 `mcp` 包；如果 SDK 不在默认环境里，设置 `MCP_PYTHONPATH=/path/to/sdk`

> 当前脚本不会安装依赖；如果 `mcp` 缺失，会直接失败并给出提示。

## 默认地址

- Host: `127.0.0.1`
- Port: `8001`
- streamable-http path: `/mcp`

最终地址：

```text
http://127.0.0.1:8001/mcp
```

## 可覆盖变量

脚本会先读项目根目录的 `.env.intranet`，再读 `.env.mcp`（如果存在），最后允许 shell 环境变量覆盖。

常用变量：

- `MEMORY_GRAPH_MCP_HOST`
- `MEMORY_GRAPH_MCP_PORT`
- `MEMORY_GRAPH_MCP_MOUNT_PATH`
- `MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH`
- `MEMORY_GRAPH_MCP_STATELESS_HTTP`
- `MEMORY_GRAPH_MCP_BEARER_TOKEN`
- `MCP_STARTUP_TIMEOUT_SECONDS`
- `PYTHON_BIN`
- `MCP_PYTHONPATH`

兼容性：

- 旧 `MCP_*` 变量仍然兼容
- 推荐统一切到 `MEMORY_GRAPH_MCP_*`

## 启动

```bash
bash scripts/deployment/mcp-start.sh
```

启动脚本会执行：

1. 读取 `.env.intranet`，再读取 `.env.mcp`（如果存在）
2. 检查 `mcp` SDK 是否可导入
3. 检查端口是否空闲
4. 后台启动 `python3 -m src.mcp --transport streamable-http`
5. 立即调用 `mcp-health-check.sh` 做协议级健康检查

运行产物：

- PID: `.sisyphus/runtime/pids/mcp.pid`
- 日志: `.sisyphus/runtime/logs/mcp.log`

## 健康检查 / 冒烟

```bash
bash scripts/deployment/mcp-health-check.sh
```

检查项：

- 端口是否在 `MCP_STARTUP_TIMEOUT_SECONDS` 内打开
- `initialize`
- `list_tools`
- 校验核心工具存在
- `read_resource(memory-graph://stats)`

如果设置了 `MEMORY_GRAPH_MCP_BEARER_TOKEN`，健康检查会自动带上 Bearer token。

## 停止

```bash
bash scripts/deployment/mcp-stop.sh
```

## 典型覆盖写法

```bash
MEMORY_GRAPH_MCP_HOST=0.0.0.0 \
MEMORY_GRAPH_MCP_PORT=8011 \
MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH=/memory-graph/mcp \
bash scripts/deployment/mcp-start.sh
```

```bash
MEMORY_GRAPH_MCP_HOST=127.0.0.1 \
MEMORY_GRAPH_MCP_PORT=8011 \
MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH=/memory-graph/mcp \
bash scripts/deployment/mcp-health-check.sh
```

## stdio 说明

这组运维脚本默认只覆盖 `streamable-http`。  
如果客户端使用 `stdio`，直接运行：

```bash
python3 -m src.mcp --transport stdio
```

`stdio` 模式通常由桌面客户端或父进程托管，不适合复用这里的后台守护脚本。
