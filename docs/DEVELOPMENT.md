# Memory Graph 开发指南

**最后更新**: 2026-04-18

---

## 目录

1. [本地开发启动](#本地开发启动)
2. [配置管理](#配置管理)
3. [项目结构](#项目结构)
4. [测试与 QA](#测试与-qa)
5. [CI 门控](#ci-门控)
6. [API 文档维护](#api-文档维护)
7. [部署指南](#部署指南)
8. [当前整改队列](#当前整改队列)

---

## 本地开发启动

### 后端（FastAPI）

```bash
pip install -r requirements.txt
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
# 编辑 config/settings.yaml 填写 LLM provider 配置
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### 前端（React Web）

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

### Sidecar（NestJS）

```bash
npm --prefix frontend/api install
npm --prefix frontend/api run build
HOST=127.0.0.1 PORT=3001 npm --prefix frontend/api run start
```

### MCP Server（FastMCP）

```bash
# stdio（Claude Desktop / 本地 agent）
python3 -m src.mcp --transport stdio

# streamable-http（远程 agent / Cursor 类客户端）
python3 -m src.mcp --transport streamable-http --host 127.0.0.1 --port 8001 --streamable-http-path /mcp
```

客户端接法见 [MCP_CLIENTS.md](./MCP_CLIENTS.md)。

### 默认访问地址

| 服务 | 地址 |
|------|------|
| React Web | `http://127.0.0.1:5173` |
| FastAPI | `http://127.0.0.1:8000` |
| Swagger | `http://127.0.0.1:8000/docs` |
| Sidecar | `http://127.0.0.1:3001` |
| MCP (streamable-http) | `http://127.0.0.1:8001/mcp` |

---

## 配置管理

### 环境变量（`.env`）

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | OpenAI 或 OpenAI-compatible 提供商 key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SIDECAR_BASE_URL` | Sidecar 地址（默认 `http://127.0.0.1:3001`） |
| `MEMORY_GRAPH_SETTINGS_PATH` | 显式指定 YAML 配置路径（多环境隔离用） |
| `MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE` | 设为 `1` 强制 `environment_only` 模式 |

> **注**：当前图存储为 NetworkX + SQLite，不再需要 `NEO4J_PASSWORD`。

### 配置 API Contract（设置页 / `/api/v1/config`）

设置页和自动化脚本看到的是 **API contract**，不是 YAML 原始结构。当前公开字段以 [docs/API.md](./API.md) 为准，常用字段包括：

- `llm_provider`
- `openai_base_url`
- `openai_model`
- `anthropic_base_url`
- `anthropic_model`
- `ollama_url`
- `ollama_model`

这些字段会由后端在 `src/api/routes/config.py` 中映射回嵌套 YAML：

- `llm_provider` -> `llm.provider`
- `openai_base_url` -> `llm.openai.base_url`
- `openai_model` -> `llm.openai.model`
- `anthropic_base_url` -> `llm.anthropic.base_url`
- `anthropic_model` -> `llm.anthropic.model`
- `ollama_url` -> `llm.ollama.url`
- `ollama_model` -> `llm.ollama.model`

API key 不直接作为常规 YAML 字段管理，优先写入系统 keyring；当 secure secret store 不可用时，接口会返回 `503` 和回退环境变量提示。

### YAML Schema（`config/settings.yaml`）

`config/settings.yaml` 是 **运行时配置文件**，结构与设置页字段不同。当前示例以 `config/settings.example.yaml` 为准，最小常见形态如下：

```yaml
llm:
  provider: "openai"  # openai | anthropic | ollama
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
    base_url: "https://api.openai.com/v1"
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-20250514"
    base_url: "https://api.anthropic.com"
  ollama:
    url: "http://127.0.0.1:11434"
    model: "qwen2.5:14b"

embedding:
  model: "Qwen/Qwen3-Embedding-0.6B"
  dimensions: 1024
  provider_preference: "local_first"
  cloud_model: "text-embedding-3-small"
  cloud_dimensions: 2048
  cloud_api_key: "${OPENAI_API_KEY}"
  cloud_base_url: "https://api.openai.com/v1"
```

当前建议按下面的边界理解配置来源：

- 设置页优先维护 `llm.provider` 与各 provider 的连接参数。
- `collectors.*`、`embedding.*`、`advanced.community_detection.*` 仍以 YAML 为主。
- `config/settings.example.yaml` 是仓库内真实示例；文档只做说明，不再重复维护另一套伪 schema。

### 前端运行时地址

由 `frontend/src-react/runtime-config.js` 统一管理：

- **本地**：检测到 Vite 端口（5173+/4173+）时自动连本机 FastAPI/Sidecar
- **部署**：走同源 `/api/v1`、`/health`、`/sidecar/health`

覆盖变量：
- `VITE_API_BASE_URL`
- `VITE_BACKEND_HEALTH_URL`
- `VITE_SIDECAR_HEALTH_URL`

### API Key 安全存储

API key 保存时优先进入**系统密钥库**（keyring），不以明文写入 YAML。

`GET /api/v1/config` 返回 `secret_storage` 字段（`system_keyring` 或 `environment_only`），设置页会据此提示。

### MCP 运行配置

MCP server 当前支持两种 transport：

- `stdio`：默认值，适合本地桌面客户端或本地 agent 进程。
- `streamable-http`：适合远程或通过 HTTP 直连的 agent 客户端。

常用环境变量：

- `MEMORY_GRAPH_MCP_TRANSPORT`
- `MEMORY_GRAPH_MCP_HOST`
- `MEMORY_GRAPH_MCP_PORT`
- `MEMORY_GRAPH_MCP_MOUNT_PATH`
- `MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH`
- `MEMORY_GRAPH_MCP_JSON_RESPONSE`
- `MEMORY_GRAPH_MCP_STATELESS_HTTP`
- `MEMORY_GRAPH_MCP_BEARER_TOKEN`

---

## 项目结构

```
Memory_graph/
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI 应用入口，托管 frontend/dist
│   │   ├── routes/              # 路由模块（memories/search/communities/sync/...）
│   │   └── schemas/             # Pydantic 数据模型
│   └── core/
│       ├── memory_service.py    # 核心摄入接口
│       ├── graph_store/         # NetworkX + SQLite 图操作
│       ├── vector_store/        # FAISS 向量操作
│       ├── entity_extractor.py  # LLM 实体/关系提取
│       ├── community_detection.py
│       ├── community_summarizer.py
│       ├── graphrag_retriever.py
│       ├── graphrag_retriever_flows.py
│       ├── collectors/          # IDE 采集器适配器
│       └── sync/                # Eleanor 双向同步
├── frontend/
│   ├── src-react/               # React Web 源码
│   │   ├── pages/               # Inbox/Search/Graph/Communities/Memory/Settings
│   │   ├── api/                 # API 客户端
│   │   ├── runtime-config.js    # 运行时地址管理
│   │   └── qa/                  # Playwright 脚本
│   ├── api/                     # NestJS Sidecar 源码
│   ├── vite.config.js
│   └── package.json
├── config/
│   ├── settings.yaml            # 运行时配置（不提交 git）
│   └── settings.example.yaml   # 配置示例（提交 git）
├── data/
│   ├── faiss/graph.db           # FAISS 索引
│   └── dbms/                    # SQLite 数据库
├── tests/                       # pytest 测试
├── scripts/
│   ├── generate_api_docs.py     # API 文档自动生成
│   └── deployment/              # 部署脚本
└── docs/
    ├── ARCHITECTURE.md
    ├── DEVELOPMENT.md           # 本文件
    ├── ROADMAP.md
    └── API.md                   # 自动生成，勿手动修改
```

---

## 测试与 QA

### 验证基线（每次改默认链路必跑）

```bash
# Python 测试
python3 -m pytest tests/test_*api*.py tests/test_config.py tests/test_secret_store.py
python3 -m pytest tests/test_query_trace.py tests/test_retrieval_facade.py tests/test_mcp_server.py tests/test_mcp_service.py tests/test_mcp_integration.py

# API 文档漂移检查
python3 scripts/generate_api_docs.py --check

# 前端 contract 测试
npm --prefix frontend run test:mainline-contract
npm --prefix frontend run test:startup-contract
npm --prefix frontend run test:import-contract
npm --prefix frontend run test:settings-contract

# 构建验证
npm --prefix frontend run build
npm --prefix frontend/api run build
```

### Phase 1 导入样本回归（改动导入链路时必跑）

```bash
python3 -m pytest tests/test_parsers.py tests/test_data_api.py tests/test_data_directory_api.py -q
```

样本 fixture 位于 `tests/fixtures/phase1_import/`，当前覆盖：
- ChatGPT：单会话 + `conversations[]` 包装变体
- Claude：`messages` + `chat` 变体
- Claude Code：JSONL 标准 + 带空行/附加字段变体
- Slack：基础导出 + thread 变体
- Codex：基础导出 + 弱字段变体

### Playwright Smoke（完整真实联调）

```bash
# 全链路 smoke（自动构建并启动服务）
npm --prefix frontend run qa:real-stack-smoke

# 设置页统一验收
npm --prefix frontend run qa:settings-playwright

# 各页面 mocked smoke
npm --prefix frontend run qa:search-playwright
npm --prefix frontend run qa:graph-playwright
npm --prefix frontend run qa:communities-playwright
npm --prefix frontend run qa:memories-playwright
npm --prefix frontend run qa:startup-playwright
npm --prefix frontend run qa:import-playwright
```

### Provider 专项验证

```bash
# 快速可用性摘要
npm --prefix frontend run qa:real-stack-smoke:readiness

# 全 provider 矩阵
npm --prefix frontend run qa:real-stack-smoke:matrix

# 单 provider（带参数）
npm --prefix frontend run qa:real-stack-smoke:openai -- --base-url https://open.bigmodel.cn/api/paas/v4 --model glm-4.7
npm --prefix frontend run qa:real-stack-smoke:anthropic:bigmodel
npm --prefix frontend run qa:real-stack-smoke:ollama -- --url http://127.0.0.1:11434 --model qwen2.5:32b

# 远程 provider 主链路一键判绿
npm --prefix frontend run qa:real-stack-smoke:remote:verify
```

### 页面级真实链路（按需运行）

```bash
# Import
npm --prefix frontend run qa:real-stack-smoke:import:diagnostics

# Collectors
npm --prefix frontend run qa:real-stack-smoke:collectors:official

# Search
npm --prefix frontend run qa:real-stack-smoke:search:navigation
npm --prefix frontend run qa:real-stack-smoke:search:source-detail:failure

# Graph
npm --prefix frontend run qa:real-stack-smoke:graph

# Communities
npm --prefix frontend run qa:real-stack-smoke:communities:summary
npm --prefix frontend run qa:real-stack-smoke:communities:navigation

# Memory
npm --prefix frontend run qa:real-stack-smoke:memories:communities
npm --prefix frontend run qa:real-stack-smoke:memories:list
npm --prefix frontend run qa:real-stack-smoke:memories:write-path

# Dashboard
npm --prefix frontend run qa:real-stack-smoke:dashboard
npm --prefix frontend run qa:real-stack-smoke:dashboard:search:aggregate
```

### Smoke 环境参数

```bash
# 覆盖端口（避免冲突）
T14_BACKEND_PORT=38000 T14_SIDECAR_PORT=38001 npm --prefix frontend run qa:real-stack-smoke

# 切换 provider 且结束后自动恢复
T14_OVERRIDE_PROVIDER=openai \
T14_OVERRIDE_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4 \
T14_OVERRIDE_OPENAI_MODEL=glm-4.7 \
npm --prefix frontend run qa:real-stack-smoke
```

### Smoke 通过标准

- 命令退出码 `0`
- `backend_health_status=healthy`
- `sidecar_health_status=UP`
- `settings_save_status=200`
- `browser_smoke=passed`

失败时看：
- `.sisyphus/evidence/task-14-real-smoke-error.txt`
- `.sisyphus/evidence/task-14-backend.log`

### GraphRAG 检索评测

```bash
# 运行基线查询集，输出 recall@k / 延迟 / 空结果率
python -m src.core.graphrag_retriever_eval

# 保存当前结果为新基线
python -m src.core.graphrag_retriever_eval --write-baseline docs/graphrag_retrieval_baseline.json

# 对比基线，回归失败时报错
python -m src.core.graphrag_retriever_eval --baseline docs/graphrag_retrieval_baseline.json --strict

# 检查绝对期望阈值
python -m src.core.graphrag_retriever_eval --expectations docs/graphrag_retrieval_expectations.sample.json --strict
```

---

## CI 门控

每个代码切片上线前必须通过：

| 门控 | 命令 | 范围 |
|------|------|------|
| Python 测试 | `python3 -m pytest tests/test_*api*.py tests/test_config.py tests/test_secret_store.py` | 所有改动 |
| API 文档不漂移 | `python3 scripts/generate_api_docs.py --check` | 所有改动 |
| 前端 contract | `npm --prefix frontend run test:mainline-contract` | 所有改动 |
| 前端构建 | `npm --prefix frontend run build` | 所有改动 |
| Sidecar 构建 | `npm --prefix frontend/api run build` | 所有改动 |
| 设置页 smoke | `npm --prefix frontend run qa:settings-playwright` | 改动涉及设置页 |
| Secret store 真实链路 | `npm --prefix frontend run qa:real-stack-smoke:settings:secret-store` | 改动涉及 secret 存储 |
| 部署脚本 | `bash scripts/deployment/intranet-baseline.sh` | 改动涉及部署 |

---

## API 文档维护

`docs/API.md` 由 `scripts/generate_api_docs.py` 从 OpenAPI schema 自动生成，**不要手动修改**。

```bash
# 重新生成
python3 scripts/generate_api_docs.py

# 只检查是否漂移（CI 用）
python3 scripts/generate_api_docs.py --check
```

漂移检测由 `tests/test_api_docs.py` 在 pytest 中自动执行。

---

## 部署指南

正式交付入口见 [DELIVERY.md](./DELIVERY.md)。
最终验收结论见 [FINAL_ACCEPTANCE.md](./FINAL_ACCEPTANCE.md)。

### 单节点部署

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
bash scripts/deployment/intranet-single-node-start.sh
bash scripts/deployment/intranet-health-check.sh
bash scripts/deployment/intranet-single-node-stop.sh
```

访问：
- Web 应用：`http://127.0.0.1:8000/`
- API 健康：`http://127.0.0.1:8000/health`
- Sidecar 健康：`http://127.0.0.1:8000/sidecar/health`
- Runtime diagnostics：`http://127.0.0.1:8000/api/v1/diagnostics/runtime`

### MCP streamable-http 部署

```bash
bash scripts/deployment/mcp-start.sh
bash scripts/deployment/mcp-health-check.sh
bash scripts/deployment/mcp-stop.sh
```

统一入口见 [standardization.md](./deployment/standardization.md)。

### 彩排与回滚

```bash
# Big-Bang 全量彩排（推荐上线前运行）
bash scripts/deployment/bigbang-rehearsal.sh
bash scripts/deployment/bigbang-rehearsal-verify.sh

# 内网基线部署
bash scripts/deployment/intranet-baseline.sh

# 云端基线部署
bash scripts/deployment/cloud-baseline.sh
```

已知最近一次彩排成功记录：
- 彩排：`.sisyphus/runtime/rehearsal-20260330_010816.json`
- 回滚：`.sisyphus/runtime/rollback-20260330_011314.json`

---

## 当前整改队列

### P0（阻塞产品级可用）

1. **官方 collector 真实 smoke 持续判绿**
   - 当前基线命令：`npm --prefix frontend run qa:real-stack-smoke:collectors:official`
   - 覆盖范围：Claude Code / Windsurf / Aider

### P1（产品化完善）

1. **Phase 1 剩余模块暂不恢复排期**
   - `entity_detector_regex.py` 已接入主链路
   - `aaak_dialect.py`、`conversation_miner.py` 继续维持延期，等待主链路稳定后再评估

2. 运行诊断页和健康证据继续产品化
3. Inbox/Search/Memory/Settings/Collector 验收矩阵持续更新
4. 导入/同步可靠性按主链路收缩
5. API 测试质量提升（消除重复类定义和 `status_code in [200, 500]` 弱断言）

> 已收口：配置契约、`entity_detector_regex.py` 主链路接入、实验态 collector 公共 API 封口、`/health` 真实检查、`graph_store.py` 结构拆分、`config/test-connection` 的 Neo4j 误导字段、向量存储原子写入。
