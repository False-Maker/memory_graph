# Memory Graph MCP 客户端接入

**最后更新**: 2026-04-18

本文只覆盖当前仓库已经实现并验证过的 MCP 运行方式：

- 本地 `stdio`：由客户端直接拉起 `python3 -m src.mcp`
- 本地 `streamable-http`：先手动启动 `python3 -m src.mcp --transport streamable-http ...`，再由客户端连 `http://127.0.0.1:8001/mcp`

本文不虚构尚未实现的接口，也不覆盖部署脚本、反向代理、systemd、OAuth、公网暴露。

---

## 当前 MCP 面

当前 MCP server 位于 [src/mcp/](/home/elucid/projects/web/Memory_graph/src/mcp)，对外暴露的是**常用读写 memory surface**。

当前 tools：

- `save_memory`
- `delete_memory`
- `archive_memory`
- `unarchive_memory`
- `answer_question`
- `search_memories`
- `get_memory`
- `get_memory_context`
- `list_memories`
- `get_graph_stats`
- `list_entities`
- `get_entity`
- `get_entity_neighbors`
- `list_communities`
- `get_community`
- `get_community_entities`
- `get_community_relationships`
- `list_query_runs`
- `get_query_run`
- `get_entity_timeline`
- `get_entity_state_as_of`

当前 resources：

- `memory-graph://stats`
- `memory-graph://memories/recent`
- `memory-graph://query-runs/recent`

---

## 接入前准备

先保证仓库本身能在本机正常启动：

```bash
pip install -r requirements.txt
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
```

再确认下面两点：

- 仓库根目录下已经有可用的 `config/settings.yaml`
- 仓库根目录下的 `.env` 或系统环境变量里已经有当前 provider 需要的 API key

如果客户端不是从仓库根目录启动 MCP 进程，最稳妥的做法是显式传：

- `PYTHONPATH=/absolute/path/to/Memory_graph`
- `MEMORY_GRAPH_SETTINGS_PATH=/absolute/path/to/Memory_graph/config/settings.yaml`

如果你要启用 HTTP 鉴权，再额外配置：

- `MEMORY_GRAPH_MCP_BEARER_TOKEN=your-shared-token`

---

## Claude Desktop

Claude Desktop 这里使用 `stdio`，因为这是当前仓库最直接、最稳定的本地接法。  
这条链路下不需要你先手动启动 MCP server，Claude Desktop 会自己拉起进程。

把下面这段加入 `claude_desktop_config.json` 的 `mcpServers`：

```json
{
  "mcpServers": {
    "memory-graph": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "src.mcp", "--transport", "stdio"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/Memory_graph",
        "MEMORY_GRAPH_SETTINGS_PATH": "/absolute/path/to/Memory_graph/config/settings.yaml"
      }
    }
  }
}
```

说明：

- 把 `/absolute/path/to/Memory_graph` 替换成你的仓库绝对路径。
- 如果 `python3` 不在 PATH 里，把 `command` 改成 Python 可执行文件的绝对路径。
- 如果你本机已经通过仓库根目录的 `.env` 管理 key，通常不需要把 API key 再写进这里。
- 当前文档**不覆盖** Claude.ai Connectors / 公网 HTTP connector，因为这要求公网可达地址和额外发布面，不属于当前仓库已经收口的本地最小接法。

---

## Cursor

Cursor 这里使用 `streamable-http`，因为当前仓库已经提供了独立的 HTTP MCP 入口，适合 IDE 侧直接连接。

先在仓库根目录启动 MCP server：

```bash
python3 -m src.mcp --transport streamable-http --host 127.0.0.1 --port 8001 --streamable-http-path /mcp
```

然后在项目级 `.cursor/mcp.json` 或全局 `~/.cursor/mcp.json` 里加入：

```json
{
  "mcpServers": {
    "memory-graph": {
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

说明：

- 如果你启用了 `MEMORY_GRAPH_MCP_BEARER_TOKEN`，就在客户端配置里补 `Authorization: Bearer <token>` 对应的 header。
- 如果你把 MCP server 改成了别的 host、port 或 path，这里的 `url` 也要一起改。
- 当前文档不展开 Cursor 的 OAuth / 远程托管配置，因为仓库里还没有配套的公网发布与鉴权方案。

---

## OpenAI Agents

OpenAI Agents 这里同样使用 `streamable-http`，这样和 Cursor 的接法保持一致，也符合当前仓库独立 MCP server 的运行方式。

先在仓库根目录启动 MCP server：

```bash
python3 -m src.mcp --transport streamable-http --host 127.0.0.1 --port 8001 --streamable-http-path /mcp
```

再在你的 agent 项目里安装 SDK：

```bash
pip install openai-agents
```

最小 Python 示例：

```python
import asyncio

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp


async def main() -> None:
    async with MCPServerStreamableHttp(
        name="memory-graph",
        params={
            "url": "http://127.0.0.1:8001/mcp",
            # 如果启用了 MEMORY_GRAPH_MCP_BEARER_TOKEN，再加 headers
            # "headers": {"Authorization": "Bearer your-shared-token"},
        },
        cache_tools_list=True,
    ) as server:
        agent = Agent(
            name="Memory Graph Assistant",
            instructions=(
                "Use the Memory Graph MCP server when you need prior memories, "
                "entity context, communities, or temporal history."
            ),
            mcp_servers=[server],
        )

        result = await Runner.run(
            agent,
            "先列出最近 3 条 query runs，再按需查看其中一条的详情。",
        )
        print(result.final_output)


asyncio.run(main())
```

说明：

- 如果你不想单独启动 HTTP server，OpenAI Agents 也支持 `stdio` transport；但本文统一按当前仓库已经跑通的独立 MCP server 方式给样例。
- 当前文档**不覆盖** `HostedMCPTool`，因为那要求 MCP server 是公网可达地址；当前仓库默认形态仍是本地/内网自托管。

---

## 最小自检

任一客户端接好后，先验证这 4 类能力：

1. 基础统计：`get_graph_stats`
2. 检索：`search_memories` 或 `answer_question`
3. 可观测性：`list_query_runs` / `get_query_run`
4. 写路径：`save_memory`，必要时再验证 `archive_memory` / `delete_memory`

如果只想验证 resources，先看这 3 个 URI：

- `memory-graph://stats`
- `memory-graph://memories/recent`
- `memory-graph://query-runs/recent`

---

## 有意不覆盖的内容

这份文档故意不展开下面这些主题：

- Claude.ai Connectors / Claude Desktop extension 打包
- Cursor 远程托管 + OAuth
- OpenAI Responses API 的 `HostedMCPTool`
- systemd / Docker / Nginx / 反向代理 / 公网发布

这些不是“没想到”，而是当前仓库还没把对应交付面做成正式标准件；这份文档只对齐当前真实可用的最小接法。
