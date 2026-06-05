# Memory Graph 架构设计

**最后更新**: 2026-04-17

---

## 目录

1. [系统定义](#系统定义)
2. [技术栈](#技术栈)
3. [整体架构](#整体架构)
4. [核心模块](#核心模块)
5. [数据模型](#数据模型)
6. [IDE Collectors](#ide-collectors)
7. [GraphRAG 检索](#graphrag-检索)
8. [社区检测](#社区检测)
9. [Eleanor 双向同步](#eleanor-双向同步)
10. [MemPalace 融合扩展（进行中）](#mempalace-融合扩展进行中)
11. [性能基线](#性能基线)
12. [技术决策记录](#技术决策记录)

---

## 系统定义

Memory Graph 是一个面向个人使用的 AI 记忆系统，将 AI 对话、文件和 IDE 痕迹持续导入、整理为知识图谱与向量索引，通过 GraphRAG 三层检索帮助用户稳定找回过去的信息。

**核心承诺**：
- 导入可信（幂等、可重试、来源可追踪）
- 检索可验证（本地/全局/混合三层，固定回归基线）
- 来源可解释（答案展示 memory、entity、community 来源）
- 数据可恢复（备份、导出、回滚、索引重建）

**产品形态**：React Web + FastAPI 后端 + NestJS Sidecar，单机自托管，单用户。

---

## 技术栈

| 层级 | 技术 | 角色 |
|------|------|------|
| **前端** | React 18 + Vite + 自定义 CSS + D3.js | Web UI (Dashboard, Inbox, Search, Graph, Communities, Memory, Settings, Startup) |
| **后端 API** | FastAPI (Python asyncio) + Pydantic v2 | 数据处理、图操作、检索引擎、静态文件托管 |
| **Sidecar** | NestJS (TypeScript) | 健康探针服务，代理到 `/sidecar/health` |
| **MCP Server** | FastMCP（官方 Python MCP SDK） | 独立的 stdio / streamable-http agent 协议面 |
| **图存储** | NetworkX + SQLite | 图结构与关系持久化 |
| **向量存储** | FAISS (CPU) | 密集向量检索，`IndexIDMap2` 支持 upsert/delete |
| **图算法** | python-igraph + leidenalg | Leiden 社区检测，多层级递归层次结构 |
| **LLM 提供商** | OpenAI / Anthropic / Ollama / BigModel | 实体提取、社区摘要、GraphRAG 问答 |
| **嵌入模型** | Qwen/Qwen3-Embedding-0.6B（本地默认）+ OpenAI-compatible cloud embeddings（可选） | 向量嵌入，本地优先，可按配置切云端 |
| **测试** | pytest + Playwright E2E | 单元/集成测试 + 前端 smoke |
| **配置** | YAML (settings.yaml) + 系统 keyring | 运行配置 + 安全密钥存储 |

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户界面层                               │
│  React Web (Dashboard / Inbox / Search / Graph / Communities │
│             / Memory / Settings / Startup)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI 后端                               │
│  routes: memories / query / graph / communities / config /   │
│          data / sync / evals / collectors                    │
└──────┬──────────────┬─────────────────┬──────────────────────┘
       │              │                 │
┌──────▼───┐  ┌───────▼──────┐  ┌──────▼──────────────────┐
│ 向量存储  │  │   图存储      │  │  核心引擎                │
│  FAISS   │  │ NetworkX +   │  │  - EntityExtractor       │
│ (config) │  │   SQLite     │  │  - CommunityDetector     │
└──────────┘  └──────────────┘  │  - CommunitySummarizer   │
                                │  - GraphRAGRetriever      │
                                │  - RetrievalFacade        │
                                │  - MemoryService          │
                                │  - SyncService            │
                                │  - QueryTraceStore        │
                                └─────────────┬────────────┘
                                              │
                                ┌─────────────▼────────────┐
                                │    数据采集层             │
                                │  4 类基础通道 + 8 类      │
                                │  AI IDE collectors        │
                                │  Eleanor Sync Client      │
                                └──────────────────────────┘
```

补充：

- NestJS Sidecar 独立提供 `/health` 与 `/ready`；FastAPI 额外代理为 `/sidecar/health` 与 `/sidecar/ready`，供 Web 前端统一探测。
- `src/mcp/` 是独立协议面，不走 FastAPI router；当前已经提供常用读写工具面，并支持 `streamable-http` 下的可选 Bearer auth。
- `/api/v1/query` 已通过 `RetrievalFacade` 收敛成单入口，`Retriever` 仅保留兼容层角色。

---

## 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| MemoryService | `src/core/memory_service.py` | 核心摄入接口，幂等 upsert |
| GraphStore | `src/core/graph_store.py` + `graph_store_*.py` | NetworkX + SQLite 图 CRUD |
| VectorStore | `src/core/vector_store.py` + `vector_store_*.py` | FAISS 向量操作，upsert/delete/rebuild |
| EntityExtractor | `src/core/entity_extractor.py` | LLM 实体/关系提取 |
| CommunityDetector | `src/core/community_detection.py` | Leiden 社区检测 |
| CommunitySummarizer | `src/core/community_summarizer.py` | LLM 社区摘要生成 |
| GraphRAGRetriever | `src/core/graphrag_retriever.py` | 三层检索编排 |
| RetrievalFacade | `src/core/retrieval_facade.py` | 统一检索入口，收敛 legacy / GraphRAG 策略 |
| GraphRAGFlows | `src/core/graphrag_retriever_flows.py` | Local / Global / Hybrid 实现 |
| SyncService | `src/core/sync/` | Eleanor 外部同步协议 |
| TemporalKnowledgeGraph | `src/core/temporal_kg.py` | 时序三元组持久化与 as-of / timeline 查询 |
| QueryTraceStore | `src/core/query_trace.py` | 基于 SQLite 的 query run/session/failure 持久化 trace |
| Collectors | `src/core/collectors/` | 采集器框架（4 类基础通道 + 8 类 AI IDE collectors） |
| MCP Server | `src/mcp/` | FastMCP 工具与 resources，对外暴露常用读写 memory surface |

---

## 数据模型

### SQLite 核心表

```sql
-- 实体
CREATE TABLE entities (
  id TEXT PRIMARY KEY,              -- hash(normalized_name + type)
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  description TEXT,
  source_ids TEXT,                  -- JSON array of memory_id
  embedding_id INTEGER,
  created_at DATETIME,
  updated_at DATETIME,
  metadata TEXT                     -- JSON
);

-- 关系
CREATE TABLE relationships (
  id TEXT PRIMARY KEY,              -- hash(source_id + type + target_id)
  source_entity_id TEXT REFERENCES entities(id),
  target_entity_id TEXT REFERENCES entities(id),
  relation_type TEXT NOT NULL,
  weight REAL DEFAULT 1.0,
  source_ids TEXT,                  -- JSON array
  created_at DATETIME,
  metadata TEXT
);

-- 社区
CREATE TABLE communities (
  id TEXT PRIMARY KEY,
  title TEXT,
  summary TEXT,
  level INTEGER NOT NULL,           -- 0=原始实体层，1-N=递归层级
  parent_community_id TEXT REFERENCES communities(id),
  entity_count INTEGER,
  created_at DATETIME,
  updated_at DATETIME
);

-- 记忆
CREATE TABLE memory_registry (
  memory_id TEXT PRIMARY KEY,
  source_system TEXT NOT NULL,      -- 来源系统（ide/eleanor/manual）
  workspace_id TEXT,
  external_id TEXT,                 -- 外部稳定 ID
  source_path TEXT,
  record_type TEXT,
  title TEXT,
  tags_json TEXT,
  content_checksum TEXT NOT NULL,
  timestamp TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,                  -- soft delete
  server_version INTEGER NOT NULL,
  UNIQUE(source_system, workspace_id, external_id)
);

-- 时序知识图（Phase 2 已落地最小切片）
CREATE TABLE temporal_triples (
  id TEXT PRIMARY KEY,
  entity_id TEXT REFERENCES entities(id),
  relation_type TEXT,
  target_entity_id TEXT REFERENCES entities(id),
  valid_from DATETIME,
  valid_to DATETIME,
  confidence FLOAT,
  source TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  metadata TEXT
);
```

### 同步专用表（已实现）

```sql
-- 同步状态
CREATE TABLE memory_sync_state (
  memory_id TEXT PRIMARY KEY,
  sync_mode TEXT NOT NULL,
  sync_status TEXT NOT NULL,        -- synced | pending_push | conflict | deleted
  last_client_mutation_id TEXT,
  server_version INTEGER,
  tombstone INTEGER DEFAULT 0
);

-- 实体证据（memory -> entity 归属）
CREATE TABLE memory_entity_mentions (
  memory_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  mention_text TEXT,
  confidence REAL,
  PRIMARY KEY(memory_id, entity_id)
);

-- 关系证据（memory -> relationship 归属）
CREATE TABLE memory_relationship_evidence (
  memory_id TEXT NOT NULL,
  relationship_id TEXT NOT NULL,
  PRIMARY KEY(memory_id, relationship_id)
);

-- 变更日志（支持增量拉取）
CREATE TABLE sync_change_log (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT NOT NULL,
  workspace_id TEXT,
  external_id TEXT,
  change_type TEXT NOT NULL,        -- created | updated | deleted | conflict
  origin TEXT NOT NULL,             -- client | server
  client_mutation_id TEXT,
  server_version INTEGER NOT NULL,
  occurred_at TEXT NOT NULL
);
```

---

## IDE Collectors

当前代码层面已存在 12 种 collector type：4 类基础通道（Cursor / Browser / WebSocket / FileWatcher）和 8 类 AI IDE collectors。当前产品支持面已明确收缩为高优先级来源优先：Claude Code / Windsurf / Aider 归入正式支持，其余 AI IDE collectors 明确为实验态。

### 支持列表

| IDE | 数据位置 | 格式 | 实现状态 | 优先级 |
|-----|---------|------|---------|--------|
| **Windsurf** | `~/.windsurf/` 或项目 `.windsurf/` | JSONL/JSON | 正式支持（高优先级） | 高 |
| **Claude Code** | `~/.claude/` + 项目 `.claude/` | JSONL | 正式支持（高优先级） | 高 |
| **Aider** | 项目 `.aider.chat.history` | Markdown | 正式支持（高优先级） | 高 |
| **Cline** | `~/.vscode/extensions/saoudrizwan.claude-dev/` | JSON | 实验态 | 中 |
| **OpenCode** | 项目 `.opencode/` | JSON/ACP | 实验态 | 中 |
| **Antigravity** | 应用数据目录 (OS 差异) | VS Code fork | 实验态 | 低 |
| **Trace** | 项目 `.trace/` | JSON | 实验态 | 低 |
| **Augment** | `~/.augment/` 或项目 `.augment/` | SQLite/JSON | 实验态 | 低 |

### 适配器架构

```
BaseCollector (抽象基类)
├── 基础通道
│   ├── CursorCollector      ✅ 已实现
│   ├── BrowserCollector     ✅ 已实现
│   ├── WebSocketCollector   ✅ 已实现
│   └── FileWatcher          ✅ 已实现
└── AI IDE collectors
    ├── WindsurfCollector    ✅ 基础类已存在
    ├── ClaudeCodeCollector  ✅ 基础类已存在
    ├── AiderCollector       ✅ 基础类已存在
    ├── ClineCollector       ✅ 基础类已存在
    ├── OpenCodeCollector    ✅ 基础类已存在
    ├── AntigravityCollector ✅ 基础类已存在
    ├── TraceCollector       ✅ 基础类已存在
    └── AugmentCollector     ✅ 基础类已存在

CollectorRegistry — 统一管理所有采集器
```

### 增量同步机制

- **文件去重**：扫描型 collectors 普遍以文件路径 MD5 标记已处理文件，避免重复处理
- **扫描调度**：各 collector 自带 scan loop，扫描间隔由各自配置决定
- **统一处理**：collector 通过 handler 把对话送入 `UnifiedCollector` 队列
- **运行控制**：通过 `/api/collectors/start`、`/api/collectors/stop` 及单 collector start/stop 端点进行控制

---

## GraphRAG 检索

### 三层策略

#### Local Retrieval（本地检索）

从 query 提取实体 → 查询图数据库 → 获取实体所属社区 → 返回社区上下文。

适合：以具体实体为中心的精确查询，例如"X 项目最近做了什么"。

#### Global Retrieval（全局检索）

对 query 生成向量嵌入 → FAISS 检索所有社区摘要 → 返回最相关社区。

适合：主题性/宏观性查询，例如"系统最近有哪些架构变更"。

#### Hybrid Retrieval（混合检索）

当前公共查询入口已经通过 `RetrievalFacade` 收敛；`graphrag` / `local` / `global` 走 GraphRAG backend，`vector` / `graph` / `hybrid` 仍保留 legacy backend 作为兼容层。

下面的多维加权公式代表 **Phase 3 目标方向**，不是当前生产代码中已经落地的 booster / reranker：

```python
relevance_score = (
    0.40 * entity_match_score +    # 实体匹配度
    0.30 * vector_similarity +     # FAISS 向量相似度
    0.20 * community_importance +  # 社区重要性（节点数/连接数）
    0.10 * recency_score           # 时间新近度
)
```

**Phase 3 规划**中将增加 KeywordBooster（关键词重叠）、TemporalBooster（时间衰减）、PreferenceExtractor（用户偏好学习）。

### 返回结构

```python
@dataclass
class GraphRAGRetrievalResult:
    answer: str                          # 最终答案
    sources: List[GraphRAGSource]        # 来源 memories
    entities: List[str]                  # 识别的实体
    communities: List[CommunityContext]  # 社区上下文
    strategy_used: str                   # local/global/hybrid
    processing_time_ms: int
```

---

## 社区检测

### Leiden 算法

```yaml
community_detection:
  algorithm: "leiden"
  resolution: 1.0        # 社区粒度，越低越粗粒
  max_levels: 5          # 最大递归层级
  min_community_size: 5
```

**多层次结构**：

```
Level 0: 原始实体 (Entity nodes)
  ↓ Leiden
Level 1: 一级社区
  ↓ 把社区作为新节点再次运行 Leiden
Level 2: 二级社区
  ↓ ...（重复直到 < 2 个社区）
```

**关系类型**：
- `BELONGS_TO`：Entity → Community
- `HAS_CHILD`：Community → Community（父子关系）

**社区摘要**：LLM 对每个社区节点生成文本摘要，存入 `communities.summary`，用于 Global Retrieval 的向量检索。

---

## Eleanor 双向同步

> **状态**: 已实现（2026-03-24 完成服务端主干）

### 设计原则

Eleanor 作为**外部同步客户端**，而非内部 Collector。支持：全量 bootstrap、增量同步、删除传播、冲突检测与回写。

### 同步协议

- **同步单位**：记录级（decision / preference / daily_note / weekly_summary 等）
- **稳定 ID**：`eleanor:{workspace_id}:{record_id}`
- **版本控制**：`server_version` 递增 + `client_mutation_id` echo 去重
- **冲突策略**：第一阶段保守策略，服务端返回 `409`，不做静默覆盖

### Sync API 端点（当前）

```
GET    /api/v1/sync/sources/settings                        # 列出已保存 source 配置
POST   /api/v1/sync/sources/settings                        # 新增 source 配置
POST   /api/v1/sync/sources/settings/{source_id}/push       # 推送本地状态
POST   /api/v1/sync/sources/settings/{source_id}/pull       # 拉取远端状态
POST   /api/v1/sync/sources/settings/{source_id}/sync       # 双向同步
POST   /api/v1/sync/sources/memories:batch-upsert           # 批量幂等写入
DELETE /api/v1/sync/sources/{source_system}/memories/{workspace_id}/{external_id}
GET    /api/v1/sync/sources/{source_system}/changes         # 增量拉取变更
POST   /api/v1/sync/sources/{source_system}/reconcile       # 全量对账
GET    /api/v1/sync/sources/{source_system}/state           # 同步统计
```

### 向量索引可变更化

改用 `faiss.IndexIDMap2(IndexFlatIP)` + `memory_id → int64 vector_id` 映射，支持真正的 upsert/delete/rebuild_index。

---

## MemPalace 融合扩展（进行中）

> 详见 [ROADMAP.md](./ROADMAP.md)

融合后将在 Memory Graph 主体上新增以下模块，技术栈保持 FAISS + SQLite（不引入 ChromaDB）：

| 模块 | 来源 | Phase | 状态 |
|------|------|-------|------|
| `chat_normalizer.py` | MemPalace normalize.py | Phase 1 | 已落地（导入链路已接入） |
| `entity_detector_regex.py` | MemPalace entity_detector.py | Phase 1 | 已落地（已接入主链路） |
| `aaak_dialect.py` | MemPalace dialect.py | Phase 1 | 规划 |
| `conversation_miner.py` | MemPalace convo_miner.py | Phase 1 | 规划 |
| `temporal_kg.py` | MemPalace knowledge_graph.py | Phase 2 | 已落地（后端最小切片） |
| `graphrag_retriever_boosters.py` | MemPalace searcher.py 算法 | Phase 3 | 规划 |
| `memory_layers.py` | MemPalace layers.py | Phase 4 | 规划 |
| `src/mcp/` 常用 MCP tool surface | MemPalace mcp_server.py 思路对齐 | Phase 4 | 已前置落地（常用读写工具集 + 可选 HTTP 鉴权） |

当前导入主链路通过 `ConversationDetector` fallback 接入 Claude Code / Slack / Codex 兼容解析；样本回归位于 `tests/fixtures/phase1_import/`。

当前 MCP 工具面已覆盖：

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

---

## 性能基线

**测试环境**: 1,000 entities，5,000 relationships，12 communities，单一固定维度嵌入基线

| 操作 | 耗时 | 瓶颈 |
|------|------|------|
| Community Detection (Leiden, 3 级) | ~2,500 ms | LLM 嵌入 |
| Community Summarization (12 社区) | ~15,000 ms | LLM 生成 |
| Local Retrieval | ~150 ms | 图查询 |
| Global Retrieval | ~800 ms | FAISS 向量搜索 |
| Hybrid Retrieval | ~1,000 ms | 合并排名 |

**缓存策略**：内存缓存（TTL 5 分钟）+ FAISS 持久索引 + SQLite 页面缓存。

**可扩展边界**：图规模 < 100K entities 性能稳定；超过需评估分片或迁移至 Milvus。

---

## 技术决策记录

### D1：REST 优先于未来 MCP 扩展

当前代码已经暴露独立的 `src/mcp/` FastMCP server，但尚未引入 `/api/v1/mcp/*` 这一层 REST 包装；当前策略仍是 REST/HTTP 主体不变，MCP 作为可选薄壳协议面。

### D2：FAISS 统一（不引入 ChromaDB）

MemPalace 使用 ChromaDB，融合时不引入新依赖，统一用现有 FAISS VectorStore 适配所有向量操作。

### D3：时序表独立（新建 temporal_triples）

不修改现有 entities/relationships 表，新建独立 `temporal_triples` 表，向后兼容，易于独立索引优化。

### D4：Leiden 优于 Louvain

更优的模块度、不产生孤立社区、收敛更快、支持层次递归。✅ 采用 Leiden。

### D5：向量 2048 维

当前默认本地 embedding 配置是 1024 维；云端 embedding 维度取决于 provider 与 YAML 配置（示例文件当前为 2048）。文档与示例应以 `config/settings.example.yaml` 和 `src/core/config.py` 为准。

---

## 验证入口

用于验证当前架构主链路的最小命令入口：

```bash
python3 -m pytest tests/test_query_api.py tests/test_query_trace.py tests/test_retrieval_facade.py tests/test_mcp_server.py tests/test_mcp_service.py tests/test_mcp_integration.py
npm --prefix frontend run test:mainline-contract
```
