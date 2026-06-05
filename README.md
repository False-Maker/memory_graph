# Memory Graph

基于 GraphRAG 的个人 AI 记忆系统，将 AI 对话、文件和 IDE 痕迹持续导入、整理为知识图谱，通过三层检索（Local/Global/Hybrid）帮助找回过去的信息。

**产品形态**：React Web + FastAPI 后端 + NestJS Sidecar，单机自托管，单用户。
**当前阶段**：主链路与增强阶段四个增强包已全部收口，当前仓库已具备单用户自托管场景下的产品级交付条件。

---

## 快速启动

```bash
# 1. 安装 Python 依赖并准备配置
pip install -r requirements.txt
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
# 编辑 config/settings.yaml 填写 LLM provider 信息

# 2. 启动后端
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload

# 3. 启动前端（开发模式）
npm --prefix frontend install
npm --prefix frontend run dev

# 4. （可选）启动 Sidecar 健康探针
npm --prefix frontend/api install && npm --prefix frontend/api run build
HOST=127.0.0.1 PORT=3001 npm --prefix frontend/api run start

# 5. （可选）启动 MCP Server
python3 -m src.mcp --transport stdio
```

默认访问：`http://127.0.0.1:5173`（开发）或 `http://127.0.0.1:8000`（生产构建后）

### 生产构建

```bash
npm --prefix frontend run build
npm --prefix frontend/api run build
SIDECAR_BASE_URL=http://127.0.0.1:3001 \
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

---

## 项目结构

```
Memory_graph/
├── src/
│   ├── api/          # FastAPI 路由（79 paths / 86 operations），托管 frontend/dist
│   └── core/         # GraphRAG 核心：Collectors, EntityExtractor,
│                     # GraphStore, VectorStore, CommunityDetector,
│                     # RetrievalFacade, SyncService, QueryTrace
│   └── mcp/          # FastMCP server（stdio / streamable-http）
├── frontend/
│   ├── src-react/    # React Web (Dashboard/Inbox/Search/Graph/Communities/Memory/Settings/Startup)
│   └── api/          # NestJS Sidecar
├── config/
│   └── settings.example.yaml
├── tests/            # pytest
├── scripts/
│   ├── generate_api_docs.py
│   └── deployment/
└── docs/
    ├── ARCHITECTURE.md   # 系统设计全貌
    ├── DEVELOPMENT.md    # 开发者操作手册
    ├── ROADMAP.md        # 开发路线图
    └── API.md            # API 文档（自动生成）
```

---

## 文档导航

| 文档 | 内容 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 技术栈、架构图、核心模块、数据模型、GraphRAG 检索、社区检测、Eleanor 同步、MemPalace 融合扩展、技术决策记录 |
| [docs/DELIVERY.md](docs/DELIVERY.md) | 当前交付范围、推荐部署路径、交付前验收命令、镜像体积与已知边界 |
| [docs/FINAL_ACCEPTANCE.md](docs/FINAL_ACCEPTANCE.md) | 最终验收范围、真实运行证据、交付结论与当前保留边界 |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发启动、配置管理、测试 QA 命令大全、CI 门控、API 文档维护、部署指南、整改队列 |
| [docs/MCP_CLIENTS.md](docs/MCP_CLIENTS.md) | Claude Desktop / Cursor / OpenAI Agents 的最小 MCP 接入样例 |
| [docs/ENGRAM_PLATFORM_INTEGRATION_CHECKLIST.md](docs/ENGRAM_PLATFORM_INTEGRATION_CHECKLIST.md) | 作为 `engram-platform` 外部 memory service 时仍需补齐的服务端 contract 清单 |
| [docs/deployment/t18-mcp-streamable-http.md](docs/deployment/t18-mcp-streamable-http.md) | MCP streamable-http 启动、健康检查、停止与验收 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 当前状态、产品范围、MemPalace 融合 5 个 Phase 详细计划、里程碑、验收标准、风险矩阵 |
| [docs/API.md](docs/API.md) | 当前公开 HTTP 端点参考（自动生成，始终同步） |

---

## 关键命令速查

```bash
# 验证基线（每次改动必跑）
python3 -m pytest tests/test_*api*.py tests/test_config.py
python3 -m pytest tests/test_query_trace.py tests/test_retrieval_facade.py tests/test_mcp_server.py tests/test_mcp_service.py tests/test_mcp_integration.py
python3 scripts/generate_api_docs.py --check
npm --prefix frontend run build

# 全链路真实 smoke
npm --prefix frontend run qa:real-stack-smoke

# GraphRAG 检索评测
python -m src.core.graphrag_retriever_eval

# 重新生成 API 文档
python3 scripts/generate_api_docs.py
```

---

## 配置

- **后端环境变量**：见 `.env.example`
- **YAML 配置**：见 `config/settings.example.yaml`（LLM provider、embedding 模型、社区检测参数等）
- API key 保存优先进入系统 keyring，不建议明文写入 YAML

详细配置说明见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#配置管理)。
