# Memory Graph 开发路线图

**最后更新**: 2026-04-18  
**当前状态**: Web 主链路与增强阶段四个增强包均已收口；当前仓库已具备单用户自托管场景下的产品级交付入口

---

## 目录

1. [当前状态](#当前状态)
2. [产品范围](#产品范围)
3. [MemPalace 融合计划](#mempalace-融合计划)
4. [依赖关系与时间表](#依赖关系与时间表)
5. [验收标准](#验收标准)
6. [风险矩阵](#风险矩阵)

---

## 当前状态

### 已完成功能

| 功能 | 状态 |
|------|------|
| React Web 前端（Inbox/Search/Graph/Communities/Memory/Settings/Dashboard） | ✅ 发布 |
| FastAPI 后端（79 paths / 86 operations） | ✅ 发布 |
| NestJS Sidecar 健康探针 | ✅ 发布 |
| NetworkX + SQLite 图存储 | ✅ 发布（从 Neo4j 迁移完成） |
| FAISS 向量存储（可配置维度，IndexIDMap2） | ✅ 发布 |
| LLM 实体/关系提取 | ✅ 发布 |
| Leiden 社区检测（多层级递归） | ✅ 发布 |
| LLM 社区摘要生成 | ✅ 发布 |
| GraphRAG 三层检索（Local/Global/Hybrid） | ✅ 发布 |
| IDE Collectors 框架（适配器模式） | ✅ 框架完成 |
| Eleanor 双向同步（服务端 + 客户端） | ✅ 已完成 |
| 系统 keyring 密钥存储 | ✅ 发布 |
| 单节点部署脚本 + Big-Bang 彩排 | ✅ 已验证 |
| GraphRAG 检索评测工具 | ✅ 发布 |
| Query run tracing + `/api/v1/query/runs*` | ✅ 已接入并持久化 |
| 统一 RetrievalFacade + `Retriever` 兼容层 | ✅ 已接入 |
| MCP server（stdio + streamable-http + 可选 Bearer auth） | ✅ 已前置落地 |
| 40+ Playwright E2E 测试 | ✅ 发布 |
| Phase 1 导入兼容接入（Claude Code / Slack / Codex） | ✅ 已接入现有导入主链路 |
| Phase 1 样本回归（多平台多变体 fixture） | ✅ 已补齐聚焦测试 |
| Phase 1 regex entity hints 接入导入主链路 | ✅ 已接入 |
| 官方 collector 真实 smoke + 验收矩阵（Claude Code / Windsurf / Aider） | ✅ 已接入 |
| 实验态 collector 公共 API 封口 | ✅ 已完成 |
| Phase 2 时序 KG 后端切片（schema + API） | ✅ 已接入 |

### 当前主要短板（P0/P1 整改队列）

**P0 — 阻塞产品级可用**：
1. **官方 collector 真实 smoke 持续判绿**：Claude Code / Windsurf / Aider 的验收矩阵需要持续保持可执行

**P1 — 产品化完善**：
1. **Phase 1 剩余模块继续延期**：`entity_detector_regex.py` 已接入主链路；`aaak_dialect.py`、`conversation_miner.py` 现阶段不恢复排期
2. 运行诊断页和健康证据继续产品化
3. Inbox/Search/Memory/Settings/Collector 验收矩阵持续更新
4. 导入/同步可靠性按主链路收缩
5. Collector 支持面维持收口：Claude Code / Windsurf / Aider 为正式支持，其余 AI IDE collectors 维持实验态且不暴露公共 API
6. MCP 当前已覆盖常用读写工具，但 19 工具与 memory layer stack 继续延期

> 说明：`/health` 真实检查、`graph_store.py` 结构损坏、`config/test-connection` 的 Neo4j 误导字段、向量存储原子写入，已按当前主链路收口，不再列为整改项。

---

## 产品范围

### In Scope（v1 范围内）

- 单机自托管，单用户
- 本地文件与对话数据导入
- 基于 GraphRAG 的搜索和问答
- 答案来源可追溯
- 备份、导出、回滚、重建索引
- 基础运行诊断
- MemPalace 融合（Phase 1-5）

### Out of Scope（v1 不做）

- 登录、注册、权限系统
- 多用户协作
- SaaS 化计费与租户管理
- 大量新 Collector 扩张（仅完成已计划的 8 个）
- 移动端或浏览器插件
- 面向外部生态的平台化

---

## MemPalace 融合计划

> **背景**：MemPalace 是另一个个人记忆系统（CLI + MCP Server），具备 Memory Graph 缺少的能力：5 种格式对话导入、时序知识图、AAAK 压缩方言、4 层内存栈、19 个 MCP 工具、96.6% LongMemEval R@5 召回率。
>
> **策略**：以 Memory Graph 为主体引入 MemPalace 的能力，统一用 FAISS（不引 ChromaDB），向后兼容现有 API。

### Phase 1：对话导入 [P0，3-5 天]

**目标**：移植 MemPalace 独立模块，支持 5 种格式对话导入。

**依赖**：无（可立即开始）

#### 当前进展（截至 2026-04-17）

- `src/core/chat_normalizer.py` 已落地，并通过 `ConversationDetector` fallback 接入现有文件导入链路
- 现有导入入口已覆盖 ChatGPT / Claude / DeepSeek / Claude Code / Slack / Codex / Generic JSON
- `tests/fixtures/phase1_import/` 已补多平台多变体样本回归，覆盖解析器、文件导入、目录扫描三条主链路
- `src/core/entity_detector_regex.py` 已通过 regex entity hints 接入现有导入主链路
- 官方 collector（Claude Code / Windsurf / Aider）已补真实 smoke 和验收矩阵
- 实验态 collectors 已从公共 API 面收口，不再作为当前产品支持面开放
- `aaak_dialect.py`、`conversation_miner.py` 经当前阶段评估后继续延期，暂不恢复排期
- Phase 2 已完成后端首段切片：`temporal_triples` 表、`TemporalKnowledgeGraph`、以及 `/api/v1/temporal/*` 最小 API

#### 已落地文件

```
src/core/
├── chat_normalizer.py           # 5 格式归一化
└── entity_detector_regex.py     # 正则 + 频率实体检测

tests/
├── test_parsers.py
└── test_data_directory_api.py
```

#### 继续规划但未落地

```text
src/core/aaak_dialect.py
src/core/conversation_miner.py
tests/test_aaak_dialect.py
tests/test_conversation_miner.py
```

#### 已修改文件

```
src/core/sync/source_parser.py
src/api/routes/data.py
```

#### 功能详情

**ChatNormalizer** — 5 格式 → TranscriptSession 标准格式：
- Claude JSON (claude.com)
- ChatGPT (chat.openai.com)
- Claude Code JSONL
- Slack 导出
- GitHub Codex

**EntityDetector** — 正则模式 + 频率分析：
- Email / URL / IP / Phone / Timestamp / UUID
- 人名识别（Title patterns）
- 组织名识别
- 置信度计分

**AAKDialect** — 有损压缩：
- Token 计数优化
- 上下文窗口管理
- 支持解压缩恢复

**ConversationMiner** — 管线编排：
- normalize → chunk by exchange → entity detect → ingest
- 支持后台处理 + 进度跟踪

#### 当前 API 策略

```
POST   /api/v1/data/import/conversations
POST   /api/v1/data/import/conversations/json
GET    /api/v1/data/import/formats
POST   /api/v1/data/import-directory
```

当前阶段优先保持现有 API 兼容，通过扩展现有导入入口完成格式接入；会话级 CRUD 端点暂未实现。

#### 验收标准

- ✅ 5 种格式全部正常导入
- ✅ 多变体样本回归固定在仓库内，可重复执行
- ✅ 实体检测准确率 > 85%
- ✅ 现有测试回归通过 100%
- ✅ 新测试覆盖率 ≥ 80%

---

### Phase 2：时序知识图谱 [P1，5-7 天]

**目标**：实体和关系加上时间窗口，支持 "as of" 查询。

**依赖**：Phase 1（间接）/ 可并行

#### 已落地文件

```
src/core/
└── temporal_kg.py               # TemporalKnowledgeGraph 类

src/api/
├── routes/temporal.py
└── schemas/temporal.py
```

#### 继续规划但未落地

```text
src/core/temporal_kg_schema.py
src/core/temporal_query_builder.py
```

#### 表结构

```sql
CREATE TABLE temporal_triples (
  id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL REFERENCES entities(id),
  relation_type TEXT,
  target_entity_id TEXT REFERENCES entities(id),
  valid_from DATETIME,
  valid_to DATETIME,
  confidence FLOAT,
  source TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_entity_temporal ON temporal_triples(entity_id, valid_from, valid_to);
```

#### 新增 API 端点

```
POST   /api/v1/temporal/triples
GET    /api/v1/temporal/entities/{id}/timeline
GET    /api/v1/temporal/entities/{id}?as_of=2026-03-01
DELETE /api/v1/temporal/triples/{id}
GET    /api/v1/temporal/stats
```

#### 验收标准

- ✅ "As of" 查询返回正确历史状态
- ✅ Timeline 视图无错误
- ✅ 查询性能 < 100ms（百万级数据）
- ✅ 新测试覆盖率 ≥ 80%

---

### Phase 3：检索收敛与混合增强 [P2，5-7 天]

**目标**：先完成公共检索入口收敛，再在 GraphRAG 上叠加 keyword overlap、temporal recency、preference booster。

**依赖**：Phase 1、Phase 2

#### 当前进展

- `src/core/retrieval_facade.py` 已落地，`/api/v1/query` 已收敛到统一 facade
- `src/core/retriever.py` 已降为兼容层
- booster / reranker 仍未落地

#### 规划中文件

```
src/core/
├── graphrag_retriever_boosters.py   # KeywordBooster, TemporalBooster, PreferenceExtractor
└── graphrag_retriever_reranker.py   # HybridReranker
```

#### 修改文件

```
src/core/graphrag_retriever_flows.py  # run_hybrid_retrieval() 末尾加 rerank
src/core/config.py                    # 增加 HybridRetrievalConfig
config/settings.example.yaml         # 增加 hybrid_retrieval 配置段
```

#### 权重配置

```yaml
hybrid_retrieval:
  enabled: true
  weights:
    similarity: 0.50      # FAISS 向量相似度
    keyword: 0.15         # 关键词重叠
    temporal: 0.10        # 时间新近度（指数衰减）
    preference: 0.05      # 用户偏好
  temporal_decay:
    half_life_days: 30
  keyword_min_overlap: 2
```

#### 验收标准

- ✅ 各 Booster 独立测试通过
- ✅ 加权融合无 NaN
- ✅ 检索质量提升（对比 Phase 前基线）
- ✅ 性能无退化（< 50ms 额外开销）

---

### Phase 4：MCP Server + 4-Layer Memory Stack [P2，7-10 天]

**目标**：最小 MCP server 已前置落地；后续阶段补 full tool surface 与 L0-L3 memory stack。

**依赖**：Phase 1、2、3

#### 当前已落地

```
src/mcp/
├── __init__.py
├── __main__.py
├── server.py
└── service.py
```

当前 MCP server 已提供：

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
- 只读 resources：`memory-graph://stats`、`memory-graph://memories/recent`、`memory-graph://query-runs/recent`

#### 继续规划

```
src/core/memory_layers.py
src/core/mcp_tool_impl.py
src/api/routes/mcp.py
src/api/routes/memory_layers.py
```

#### 4-Layer 设计

| Layer | Token 预算 | 内容 | 触发 |
|-------|-----------|------|------|
| **L0 Identity** | ~100 | 用户 profile 文本 | 始终加载 |
| **L1 Essential** | ~500-800 | 高置信实体 + 社区摘要 | 始终加载 |
| **L2 On-Demand** | ~200-500 | FAISS 检索 + hybrid boost | 按 query |
| **L3 Deep Search** | 无限 | GraphRAG 完整遍历 | 按 query |

#### Full Tool Surface（继续规划）

| MCP Tool | 目标 REST Endpoint | 委托 |
|----------|---------------|------|
| mempalace_status | GET /api/v1/mcp/status | System.stats |
| mempalace_search | POST /api/v1/mcp/search | MemoryLayerStack.retrieve |
| mempalace_kg_query | POST /api/v1/mcp/kg/query | TemporalKG.query_entity |
| mempalace_kg_timeline | GET /api/v1/mcp/kg/timeline/{id} | TemporalKG.get_timeline |
| mempalace_traverse | POST /api/v1/mcp/traverse | GraphStore.traverse |
| mempalace_list_wings | GET /api/v1/mcp/wings | Communities.list |
| mempalace_check_duplicate | POST /api/v1/mcp/check-duplicate | VectorStore.similarity_search |
| ... (完整工具面后续按优先级补齐) | | |

#### 验收标准

- ✅ 19 个端点全部实现
- ✅ 分层加载无 bug
- ✅ Token 预算准确
- ✅ 层查询 < 200ms

---

### Phase 5：Auto-save Hooks + 前端时间线 [P3，3-5 天]

**目标**：Claude Code 自动存档集成 + Timeline 可视化页面。

**依赖**：Phase 1-4

#### 新增文件

```
scripts/hooks/
├── claude-code-stop.sh
├── claude-code-precompact.sh
└── install-hooks.sh

frontend/src-react/
├── pages/TimelinePage.jsx
├── components/TimelineVisualization.jsx
└── api/temporalApi.js
```

#### Hooks 集成

**Stop Hook**：Claude Code 会话结束时，自动调用未来的 diary tool / diary REST wrapper，持久化会话摘要。

**PreCompact Hook**：上下文压缩前，保存当前上下文摘要，更新实体关系。

#### 前端新增

- **Timeline 页面**：选择实体 → 显示历史状态 + 状态转换动画
- **搜索页增强**：新增 "As of date" 时间过滤
- **Dashboard 增强**：时序 KG 统计卡

#### 验收标准

- ✅ Timeline 页面加载正常
- ✅ Hooks 安装脚本可靠
- ✅ E2E 测试通过
- ✅ Timeline 渲染 < 1s

---

## 依赖关系与时间表

> 注：下面的依赖图和时间表描述的是“full memory-layer roadmap”。最小 MCP server、query trace、retrieval facade 已经前置落地，不再受这个线性阶段图约束。

### 依赖图

```
┌────────────────────────────────────┐
│     Phase 1: 对话导入              │  ← 当前起点
│  (chat_normalizer, entity_regex,   │
│   aaak, conversation_miner)        │
└───────────┬────────────────────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
┌─────────┐  ┌──────────────┐
│ Phase 2 │  │   Phase 3    │
│ 时序 KG │  │ 混合检索增强  │
└────┬────┘  └──────┬───────┘
     │              │
     └──────┬───────┘
            ▼
    ┌───────────────┐
    │    Phase 4    │
    │ MCP + L0-L3   │
    └───────┬───────┘
            ▼
    ┌───────────────┐
    │    Phase 5    │
    │ Hooks + 前端  │
    └───────────────┘
```

### 时间表

| Phase | 工作量 | 可并行 |
|-------|--------|--------|
| 1 对话导入 | 3-5 天 | 无前置 |
| 2 时序 KG | 5-7 天 | Phase 2/3 可并行 |
| 3 检索增强 | 5-7 天 | Phase 2/3 可并行 |
| 4 Full MCP + 层栈 | 7-10 天 | 依赖 1/2/3 |
| 5 Hooks + 前端 | 3-5 天 | 依赖 1-4 |
| **总计** | **~4 周** | |

### 里程碑

- **M1**（Week 1 末）：Phase 1 完成，5 种格式导入测试通过
- **M2**（Week 2 末）：Phase 2/3 完成，时序查询和检索增强 API 文档更新
- **M3**（后续阶段）：full MCP tool surface 与 memory layers 补齐
- **M4**（后续阶段）：Hooks / Timeline / 发布准备完成

---

## 验收标准

达到以下条件，才建议对外称为 Self-Hosted v1：

| 条件 | 指标 |
|------|------|
| 新用户启动 | 10 分钟内完成启动与第一次导入 |
| 重复导入 | 不产生明显重复污染 |
| 搜索结果 | 默认展示来源证据（memory / entity / community） |
| 检索质量 | 存在固定回归集和最低基线（见 `docs/graphrag_retrieval_baseline.json`） |
| 故障定位 | 用户可识别主要故障类型并看到下一步建议 |
| 数据恢复 | 备份、导出、回滚、索引重建都做过真实演练 |
| 代码覆盖率 | 整体 ≥ 80% |
| 向后兼容 | 现有 Web / API 主链路保持兼容 |
| 关键 bug | 0 个 critical |

---

## 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| SQLite 时序查询性能 | 中 | 高 | 添加复合索引，查询优化 |
| FAISS 适配 ChromaDB 功能差异 | 低 | 中 | 提前 PoC，特性梳理 |
| 向量维度不匹配（融合后） | 低 | 高 | 向量 normalize，导入前校验 |
| MCP 19 工具功能缺失 | 中 | 中 | 分阶段实现，按优先级排序 |
| 前端 Timeline 渲染性能 | 低 | 低 | 虚拟化列表，分页加载 |
| P0 整改拖延影响 Phase 1 | 中 | 高 | P0 整改与 Phase 1 并行，不互相阻塞 |

---

## 当前验证入口

路线图相关改动当前建议至少跑以下命令：

```bash
python3 -m pytest tests/test_query_api.py tests/test_query_trace.py tests/test_retrieval_facade.py tests/test_mcp_server.py tests/test_mcp_service.py tests/test_mcp_integration.py
npm --prefix frontend run test:mainline-contract
```
