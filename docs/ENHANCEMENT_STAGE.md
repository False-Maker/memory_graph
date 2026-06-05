# Memory Graph 增强阶段详细设计

**最后更新**: 2026-04-18  
**适用前提**: 当前版本已经达到可交付状态；本文件只描述交付后的增强阶段，不覆盖当前已完成主链路。

---

## 目标

增强阶段的目标不是继续“补完 v1 主链路”，而是在不推翻当前结构的前提下，把现有可交付版本提升为更强的记忆系统平台。

当前代码已经具备的增强起点：

- Web 主链路
- GraphRAG 检索主链路
- 时序 KG 最小切片
- query trace 持久化
- MCP 常用读写工具
- Claude Desktop / Cursor / OpenAI Agents 最小接入
- streamable-http 运行、健康检查、可选 Bearer auth
- 部署脚本与单节点验收链路

增强阶段从这些已落地能力继续往上加，不重做主链路。

---

## 设计原则

增强阶段统一遵守下面几个原则：

1. **增量增强，不改主骨架**
   - 继续以 `FastAPI + React Web + 独立 MCP server + SQLite/FAISS` 为主体。
   - 不引入第二套检索入口，不引入第二套 memory service，不引入新的核心基础设施依赖。

2. **现有入口优先扩展，不并行发明新入口**
   - 检索继续收敛在 `src/core/retrieval_facade.py`。
   - MCP 继续收敛在 `src/mcp/server.py` 和 `src/mcp/service.py`。
   - 运行诊断继续基于 `/health`、`/api/v1/diagnostics/runtime`、`/api/v1/query/runs*` 扩展。

3. **优先加可选字段和新页面，不破坏已有契约**
   - 现有 Web / API / MCP 主链路默认保持兼容。
   - 能通过可选字段扩展的，不新增 breaking route 或 breaking schema。

4. **增强项必须有运营证据**
   - 每个增强包都要落到具体模块、测试、文档和验收命令。
   - 不接受只有“概念设计”而没有实现锚点和验证路径的增强项。

---

## 增强包总览

| 包 | 优先级 | 目标 | 主要依赖 | 预期结果 |
|----|--------|------|----------|----------|
| `Memory Layers` | P1 | 把统一 retrieval 升级成分层记忆加载模型 | 现有 `RetrievalFacade` / GraphRAG / temporal / query trace | 统一 layer contract，支持 token 预算、回退与 layer-aware 查询 |
| `Expanded MCP Surface` | P1 | 把当前高频 MCP 工具面扩展成更完整的 agent 操作面 | `Memory Layers` 基础 contract，现有 MCP service | 更完整的 write / inspect / layer-aware tool surface（已完成，Slice 1-4 已落地） |
| `Observability & Operator UX` | P1 | 把“能查”提升成“能运营和定位问题” | query trace、runtime diagnostics、sidecar / collector 状态 | Operator 页面、错误分型、可追踪 query run 与 MCP 状态（已完成，Slice 1-3 已落地） |
| `Deployment Standardization` | P2 | 把现有脚本交付提升成标准部署件 | 当前 deployment scripts 与 docs | systemd / compose / 反代模板 / 统一健康检查（已完成，Slice 1-3 已落地） |

建议执行顺序：

1. `Memory Layers`
2. `Expanded MCP Surface`
3. `Observability & Operator UX`
4. `Deployment Standardization`

原因：

- `Memory Layers` 是检索、MCP 和未来 agent 体验的共同底座。
- `Expanded MCP Surface` 直接建立在 layer contract 之上。
- `Observability & Operator UX` 需要基于新的 query / MCP 行为补运营面。
- `Deployment Standardization` 不阻塞产品增强，但决定后续落地成本。

---

## 增强包一：Memory Layers

### 目标

把当前统一 memory surface 提升为分层加载模型，支持不同 token 预算、不同深度和不同调用场景，同时继续复用现有 `RetrievalFacade`。

### 现有锚点

- `src/core/retrieval_facade.py`
- `src/core/graphrag_retriever.py`
- `src/core/temporal_kg.py`
- `src/api/routes/query.py`
- `src/api/schemas/query.py`
- `src/core/query_trace.py`
- `src/mcp/service.py`

### 非目标

- 不新增第二套检索 service
- 不立刻落地完整 4-layer memory stack 持久化系统
- 不引入新的外部向量库或新的数据库
- 不改变现有 `/api/v1/query` 默认行为

### 详细设计

#### 1. 设计一个统一的 Layer Contract

新增模块建议：

```text
src/core/memory_layers.py
```

建议核心对象：

- `MemoryLayerRequest`
- `MemoryLayerResult`
- `MemoryLayerBudget`
- `MemoryLayerContextItem`
- `MemoryLayerDiagnostics`

建议语义：

- `requested_layer`: `auto | l0 | l1 | l2 | l3`
- `resolved_layer`: 本次实际执行层
- `fallback_chain`: 实际经历的回退链
- `context_items`: 进入最终上下文的内容片段
- `token_budget`: 本次预算
- `token_estimate`: 本次估算
- `diagnostics`: 命中数、截断数、是否触发回退

#### 2. Layer 定义

| Layer | 目标 | 默认预算 | 数据来源 | 触发方式 |
|-------|------|----------|---------|----------|
| `L0 Identity` | 给 agent 一个稳定的用户身份与长期偏好基线 | 80-120 tokens | YAML 中的单用户 profile 文本 | 始终加载 |
| `L1 Essential` | 提供高置信长期记忆 | 400-800 tokens | 社区摘要 + 高置信实体 + 少量 pinned memory 摘要 | 默认加载 |
| `L2 On-Demand` | 提供问题相关上下文 | 200-500 tokens | 现有 retrieval facade / FAISS / hybrid 检索结果 | 默认查询层 |
| `L3 Deep Search` | 提供高成本深度检索 | 受 `top_k` 和 GraphRAG 深度控制 | 现有 GraphRAG local/global/hybrid | 显式请求或 L2 失败回退 |

#### 3. Layer 生成策略

第一阶段设计采用“**读时组装**”，不强依赖新的持久化缓存：

- `L0` 从配置读取
- `L1` 通过当前 graph/community 数据读时生成
- `L2` 继续复用现有 `RetrievalFacade.search()/answer()`
- `L3` 继续复用现有 `GraphRAGRetriever`

只有在以下证据成立时，才进入第二阶段“快照缓存”：

- `L1` 生成明显拖慢 query
- 需要跨 Web / MCP / eval 复用稳定层快照
- 需要审计某次 query 使用的精确 layer 内容

第二阶段再考虑新增：

```text
layer_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  layer_name TEXT NOT NULL,
  token_estimate INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  source_version TEXT,
  updated_at TEXT NOT NULL
)
```

#### 4. 查询 API 增量扩展

对现有 `QueryRequest` 做兼容式扩展：

```text
layer: Optional[str] = "auto"
layer_budget_override: Optional[int] = None
```

对现有 `QueryResponse` 做兼容式扩展：

```text
layer_used: Optional[str]
layer_fallback_chain: List[str]
context_token_estimate: Optional[int]
```

兼容策略：

- 老调用方不传 `layer`，行为与当前一致
- 默认 `layer=auto`，内部解析为 `L2` 优先，必要时回退 `L3`
- Web 搜索页仍然先吃原字段；新字段先用于 operator 展示和后续增强

#### 5. Query Trace 扩展

`src/core/query_trace.py` 建议扩展字段：

- `layer_requested`
- `layer_used`
- `layer_fallback_chain`
- `context_token_estimate`
- `layer_build_duration_ms`

目的：

- 让后续 operator 页面能直接回答“这次检索为什么用了深搜”
- 让 layer 预算异常和回退异常可审计

#### 6. 配置扩展

建议在 `config/settings.example.yaml` 中新增：

```yaml
memory_layers:
  enabled: true
  default_layer: auto
  identity:
    profile_text: ""
  l0:
    max_tokens: 120
  l1:
    max_tokens: 700
    max_entities: 12
    max_communities: 4
    max_pinned_memories: 6
  l2:
    max_tokens: 400
    default_top_k: 5
  l3:
    enabled: true
    default_strategy: hybrid
```

这里故意不单独设计新配置系统，继续沿用现有 YAML。

#### 7. 与 MCP 的关系

`Memory Layers` 不单独发明新的 agent-only 实现。MCP 调用走同一个 layer resolver：

- `answer_question` 增加可选 `layer`
- `search_memories` 增加可选 `layer`
- 新增 `preview_memory_layer` 用于调试和 operator 观察

### 实施切片

#### Slice 1

- 新增 `src/core/memory_layers.py`
- 只实现 contract、budget 计算和 fallback 决策
- 不改 Web，不改 MCP

#### Slice 2

- 在 `RetrievalFacade` 接入 layer resolver
- `QueryRequest` / `QueryResponse` / `query_trace` 扩字段
- 跑现有 query / retrieval / trace 测试

#### Slice 3

- MCP 接入 layer 参数与 `preview_memory_layer`
- 增加 focused tests

#### Slice 4

- 有性能证据后再决定是否补 `layer_snapshots`

### 验收

- 相同 query 在不同 layer 下返回形态稳定
- `auto -> l2 -> l3` 回退路径可测
- token 预算不会失控
- query trace 可看到 `requested/resolved/fallback`
- 不破坏现有 `/api/v1/query` 调用

---

## 增强包二：Expanded MCP Surface

### 目标

把当前常用 MCP 工具面扩展成更完整的 agent 操作面，但继续坚持“**一份业务逻辑，多种协议面复用**”。

### 当前状态

`Expanded MCP Surface` 已完成，`Slice 1-4` 均已落地；当前 MCP 面已经补齐写入、检查、来源状态、layer-aware 检索与只读资源面，且没有引入平行的业务逻辑层。

### 现有锚点

- `src/mcp/server.py`
- `src/mcp/service.py`
- `src/core/memory_service.py`
- `src/core/retrieval_facade.py`
- `src/core/query_trace.py`
- `src/core/temporal_kg.py`

### 非目标

- 不为 MCP 单独再写一套 memory business logic
- 不一次性追满路线图里所有 19 个工具
- 不引入新的远程状态服务或 agent framework

### 完成态回写

#### 1. 已落实的扩展原则

当前实现继续遵守本包原始约束：

- 先扩现有工具，再补少量高价值工具；没有另起一套 MCP-only memory logic。
- 成功返回仍然是结构化直接 payload，失败继续走 MCP structured error surface。
- 所有新工具和资源入口继续收敛在 `src/mcp/service.py` 与 `src/mcp/server.py`，需要复用的能力仍委托给现有 `MemoryService`、`RetrievalFacade`、sync/runtime diagnostics helper。

#### 2. 工具分组

##### 写入组

- `append_journal_entry`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 继续委托 `MemoryService.ingest_memory`
  - 写入结果仍落成普通 memory，不额外创造第二种存储形态

- `bulk_save_memories`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 循环调用共享 memory service
  - 返回逐项结果与失败项，不制造“全有或全无”事务假象

##### 检查组

- `check_duplicate`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 复用 `VectorStore.search` 和 metadata 比对
  - 返回相似项列表、相似度与建议动作

##### 同步/来源组

- `list_sync_sources`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 复用现有 sync-source 配置读取逻辑

- `get_sync_source_status`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 复用现有 source status builder 与 runtime diagnostics 相关 helper

- `get_runtime_diagnostics`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 复用 `src/api/main.py` 中已有 config/provider/sqlite/vector-store/task-chain 检查逻辑

##### Layer-aware 检索组

- `answer_question(question, ..., layer=None, layer_budget_override=None)`
  - 已扩展并委托统一 `RetrievalFacade`
  - 返回 `layer_requested`、`layer_used`、`layer_fallback_chain`、`context_token_estimate`

- `search_memories(query, ..., layer=None, layer_budget_override=None)`
  - 已扩展并委托统一 `RetrievalFacade`
  - 返回同一套 layer diagnostics 字段

- `preview_memory_layer(layer, question=None, layer_budget_override=None)`
  - 已实现于 `src/mcp/service.py` 和 `src/mcp/server.py`
  - 使用与 query/MCP 检索相同的 layer resolver，不引入第二套预览逻辑

#### 3. 输出约定

当前 MCP service 继续沿用结构化字典输出，没有新增 envelope 包装层。

已落实约束：

- 成功输出保持“直接 payload”
- 失败通过明确异常 + MCP structured error surface 暴露
- 不在工具输出里混入人类解释性长文本

#### 4. MCP Resources 扩展

已新增并挂载以下只读 resources：

- `memory-graph://diagnostics/runtime`
- `memory-graph://sync-sources/status`
- `memory-graph://layers/default-preview`

实现落点：

- 资源注册在 `src/mcp/server.py`
- payload 生成在 `src/mcp/service.py`
- 风格继续与现有 `memory-graph://stats`、`memory-graph://recent` 等资源保持一致

#### 5. 服务实现边界

当前实现继续保持以下边界：

```text
src/mcp/service.py
src/mcp/server.py
```

没有新增：

- 新的 `mcp_tool_impl.py`
- 新的 REST-only 业务实现层
- 独立于 `MemoryGraphMCPService` 的另一套工具 service

需要共享的 layer 解析与检索行为仍下沉并复用 `src/core/retrieval_facade.py` 与 `src/core/query_trace.py`，没有在 MCP 面复制同类逻辑。

### 实施切片

#### Slice 1

- 已完成
- `answer_question` / `search_memories` 已增加 `layer` 与 `layer_budget_override`
- `preview_memory_layer` 已落地，并复用统一 layer resolver

#### Slice 2

- 已完成
- `append_journal_entry` 已落地为低摩擦 journal/session summary 写入入口
- `bulk_save_memories` 已落地为批量保存入口，返回逐项结果

#### Slice 3

- 已完成
- `check_duplicate` 已落地
- `list_sync_sources` / `get_sync_source_status` 已落地
- `get_runtime_diagnostics` 工具也已一并落地到同一来源状态与诊断面

#### Slice 4

- 已完成
- `memory-graph://diagnostics/runtime`、`memory-graph://sync-sources/status`、`memory-graph://layers/default-preview` 已落地
- `tests/test_mcp_server.py` 已覆盖工具注册、资源注册、`streamable-http` app 创建与 Bearer auth 行为
- `tests/test_mcp_integration.py` 已持续覆盖核心 layer-aware 读路径
- `tests/test_mcp_service.py` 已覆盖新增工具的共享业务逻辑

### 验收结论

当前实现已满足本包验收目标：

- 每个新增工具和资源都已在 `src/mcp/server.py` 明确注册，输入参数与返回契约可追踪。
- 成功/失败返回保持稳定：成功为结构化 payload，失败为异常路径，不额外混入解释性包装。
- `tests/test_mcp_service.py` 已覆盖 `append_journal_entry`、`bulk_save_memories`、`check_duplicate`、`list_sync_sources`、`get_sync_source_status`、`get_runtime_diagnostics`、`preview_memory_layer` 等新增能力。
- `tests/test_mcp_server.py` 已覆盖工具注册、资源注册、调用透传与 `streamable-http` 运行面。
- `tests/test_mcp_integration.py` 已覆盖核心 `answer_question` / `search_memories` 集成路径。
- 当前 MCP 面没有与现有 `MemoryService` / `RetrievalFacade` 形成平行逻辑，业务逻辑仍保持单源实现。

---

## 增强包三：Observability & Operator UX

### 目标

把现在“能查 trace / 能看 startup 状态”提升成“能运营系统、能解释失败、能定位问题”。

### 现有锚点

- `src/api/main.py`
- `/health`
- `/api/v1/diagnostics/runtime`
- `/api/v1/query/runs`
- `/api/v1/query/runs/{run_id}`
- `frontend/src-react/pages/StartupPage.jsx`
- `frontend/src-react/pages/SettingsPage.jsx`
- `frontend/src-react/pages/DashboardPage.jsx`

### 非目标

- 不做完整监控平台
- 不接入 Prometheus / Grafana 这类外部系统
- 不为了 operator UX 重做现有导航结构

### 详细设计

#### 1. 前端信息架构

新增一个 operator 入口页，建议单页多分区，而不是新增多张散页面：

```text
frontend/src-react/pages/DiagnosticsPage.jsx
frontend/src-react/pages/DiagnosticsPage.css
frontend/src-react/api/diagnostics.js
```

建议路由：

```text
/diagnostics
```

页面分区：

- `Runtime`
  - provider / sqlite / vector store / sidecar / sync source
- `Query Runs`
  - recent list + detail drawer
- `MCP`
  - transport / auth / reachability / tool surface summary
- `Recent Failures`
  - 最近失败、分型和建议动作

保持边界：

- `StartupPage` 继续负责“启动健康”
- `SettingsPage` 继续负责“配置和连通性”
- `DiagnosticsPage` 负责“持续运营和问题定位”

#### 2. Backend 需要补的接口

建议新增：

- `GET /api/v1/diagnostics/operator-summary`
- `GET /api/v1/mcp/status`

建议扩展：

- `GET /api/v1/query/runs`
  - 支持 `status`
  - 支持 `strategy`
  - 支持 `layer_used`
  - 支持 `session_id`
- `GET /api/v1/diagnostics/runtime`
  - 增加 failure 分类结果
  - 增加 sidecar / collector / task-chain 聚合摘要

#### 3. Failure Taxonomy

当前 `recent_failures` 只有：

- `component`
- `detail`
- `source`
- `first_seen_at`
- `last_seen_at`
- `count`

增强阶段建议在 diagnostics 层增加派生字段，而不是重写底层记录结构：

- `category`
  - `provider_auth`
  - `provider_connectivity`
  - `vector_dimension_mismatch`
  - `sqlite_io`
  - `sync_conflict`
  - `sidecar_unreachable`
  - `mcp_unreachable`
- `severity`
  - `info | warning | error`
- `suggested_action`
  - 面向 operator 的下一步建议

这样可以不改写全部调用点，只在 diagnostics 聚合阶段做分类。

#### 4. Query Run 与前端联动

当前 `/api/v1/query` 已经通过响应头返回：

- `X-Query-Run-Id`
- `X-Query-Session-Id`

增强阶段建议前端利用这些 header：

- Search 页保存最近一次 `run_id`
- 在查询结果区域提供“查看本次 trace”入口
- 跳转到 `/diagnostics?tab=query-runs&run_id=...`

这样可以把“结果异常”直接连到“定位页面”，不需要重新搜索日志。

#### 5. MCP 状态页设计

`GET /api/v1/mcp/status` 返回建议：

- `configured`
- `transport`
- `reachable`
- `auth_enabled`
- `tools_count`
- `core_tools`
- `detail`

约束：

- `stdio` 模式只返回配置态，不做 reachability 假探测
- `streamable-http` 模式才做真实连通性与核心工具检查

#### 6. Dashboard 增量增强

不新增复杂交互，只增加 operator 摘要卡：

- 最近 query runs 数
- 最近失败数
- runtime diagnostics 状态
- sync sources attention 数

卡片点击统一进入 `/diagnostics`。

### 实施切片

#### Slice 1

- 扩展 `/api/v1/query/runs`
- 扩展 `/api/v1/diagnostics/runtime`
- 新增 `/api/v1/mcp/status`
- 已完成

#### Slice 2

- 新增 `DiagnosticsPage`
- 加入导航入口
- Dashboard 加 operator summary cards
- 已完成

#### Slice 3

- Search 页接入 `run_id` 跳转
- Recent failures 展示分类和建议动作
- 已完成

### 当前状态

`Observability & Operator UX` 已完成，`Slice 1-3` 均已落地；当前系统已经具备独立 operator 页面、query run 过滤与追踪跳转、runtime/collector/sidecar/task-chain 聚合视图，以及 MCP transport / reachability / tool surface 的状态面。

当前落地点：

- 后端已补齐 `/api/v1/diagnostics/operator-summary`、`/api/v1/mcp/status`，并扩展 `/api/v1/query/runs` 过滤参数与 `/api/v1/diagnostics/runtime` 聚合摘要。
- 失败诊断已在 diagnostics 聚合层补齐 `category`、`severity`、`suggested_action`，没有重写底层 failure record 结构。
- 前端已新增 `DiagnosticsPage`，Dashboard 已增加 operator summary cards，Search 结果已支持按最近一次 `run_id` 跳转到 `/diagnostics?tab=query-runs&run_id=...`。
- 对应主线 contract / helper / API tests 已补齐，API 文档已与当前路由面同步。

### 验收

- operator 不看日志也能识别大部分常见问题
- query run 可以从一次具体搜索结果追到具体 trace
- diagnostics 能区分 provider / sqlite / vector / sync / sidecar / mcp 问题
- 新页面进入现有 contract / focused smoke 覆盖

### 验收结论

当前实现已满足本包验收目标：

- `src/api/main.py` 已提供 operator 汇总、MCP 状态检查、runtime 聚合与 recent failure taxonomy，且没有引入新的并行诊断服务。
- `src/api/routes/query.py` 已支持按 `status`、`strategy`、`layer_used`、`session_id` 过滤 query runs，便于前端 operator 页面和结果追踪联动。
- `frontend/src-react/pages/DiagnosticsPage.jsx` 已成为统一 operator 入口页，Dashboard 与 Search 已接入稳定跳转链路。
- 前端 contract tests、后端 API tests 与自动生成的 `docs/API.md` 已覆盖并固定当前对外契约。

---

## 增强包四：Deployment Standardization

### 目标

把当前“脚本可运行”的交付状态提升成“有标准模板、有统一健康检查、有可复制部署件”的状态。

### 现有锚点

- `scripts/deployment/intranet-single-node-start.sh`
- `scripts/deployment/intranet-single-node-stop.sh`
- `scripts/deployment/intranet-health-check.sh`
- `scripts/deployment/mcp-streamable-http-start.sh`
- `scripts/deployment/mcp-streamable-http-stop.sh`
- `scripts/deployment/mcp-streamable-http-health-check.sh`
- `docs/deployment/*.md`

### 非目标

- 不在增强阶段直接引入 Kubernetes
- 不为了容器化重写运行模型
- 不废弃现有 shell 脚本交付路径

### 详细设计

#### 1. 标准化对象

增强阶段主要补四类标准件：

1. systemd 模板
2. Docker / Compose 模板
3. 反向代理示例
4. 文档与脚本统一健康检查契约

#### 2. 文件布局建议

继续贴近当前仓库布局，不新增过大的顶层结构：

```text
scripts/deployment/systemd/
  memory-graph-api.service.example
  memory-graph-sidecar.service.example
  memory-graph-mcp.service.example

scripts/deployment/compose/
  docker-compose.yml
  .env.compose.example

docs/deployment/
  standardization.md
  reverse-proxy-nginx.sample.conf
  reverse-proxy-caddy.sample
```

#### 3. 服务边界标准化

约定三个服务名：

- `memory-graph-api`
- `memory-graph-sidecar`
- `memory-graph-mcp`

服务职责：

- API：托管 React build + FastAPI routes
- Sidecar：健康探针与未来补充本地守护能力
- MCP：独立协议面

不把 MCP 并回 FastAPI 进程。

#### 4. 环境变量模型

当前 `.env.intranet` 已经是单节点入口，增强阶段不重命名，只做标准化补充。

约定：

- `.env.intranet` 继续作为 Web/API/Sidecar 默认运行入口
- MCP 独立部署时允许使用 `.env.intranet` 共享，或单独补 `.env.mcp.example`
- 文档必须只维护一套环境变量说明，不允许部署文档互相漂移

#### 5. 统一健康检查契约

所有部署模板统一验收以下检查：

- `GET /`
- `GET /health`
- `GET /api/v1/diagnostics/runtime`
- `GET /sidecar/health`
- `GET /sidecar/ready`
- `POST /api/v1/query`
- MCP `initialize + list_tools + read_resource(memory-graph://stats)`

增强重点不是增加检查数量，而是让不同部署模板使用同一套验收标准。

#### 6. 文档对齐要求

部署增强阶段必须把下面几件事一起收口：

- 脚本真实行为与文档一致
- 环境变量说明统一
- 不再出现已下线技术字段残留在部署文档中
- systemd / compose / shell 的启动停止命令命名一致

### 实施切片

#### Slice 1

- 新增 systemd 模板
- 新增 `standardization.md`
- 补统一健康检查说明
- 已完成

#### Slice 2

- 新增 Compose 模板
- 新增反向代理示例
- 已完成

#### Slice 3

- 对齐 `.env` 样例、部署文档、健康检查文档
- 把现有 cloud / intranet / mcp 部署文档收敛成统一入口导航
- 已完成

### 当前状态

`Deployment Standardization` 已完成，`Slice 1-3` 均已落地；当前仓库已经具备 shell、systemd、Compose、reverse proxy 四类标准交付件，并且全部映射到同一套 HTTP/MCP 健康检查契约。

当前落地点：

- `scripts/deployment/systemd/` 已补齐 `memory-graph-api`、`memory-graph-sidecar`、`memory-graph-mcp` 三个 systemd 模板。
- `scripts/deployment/compose/` 已补齐 `docker-compose.yml`、`.env.compose.example` 和三份 Dockerfile 模板。
- `docs/deployment/standardization.md` 已成为统一入口，Nginx/Caddy 样例已落在 `docs/deployment/`。
- canonical `mcp-*` 脚本已经统一到协议级健康检查，旧 `mcp-streamable-http-*` 保留为兼容包装，不再分叉实现。
- `intranet-health-check.sh` / `cloud-smoke-check.sh` 已补齐 `GET /api/v1/diagnostics/runtime`，HTTP/MCP 契约已经与文档对齐。

### 验收

- 新环境 10-15 分钟内可拉起
- 启动 / 停止 / 健康检查命令统一
- systemd / compose / shell 交付件都能映射到同一健康标准
- 文档和脚本不再互相漂移

### 验收结论

当前实现已满足本包验收目标：

- shell、systemd、Compose、反代模板都已具备明确文件落点与统一命名的服务边界。
- MCP 独立部署不再只有端口级探测，已经升级为 `initialize + list_tools + read_resource(memory-graph://stats)` 的协议级检查。
- `.env.intranet`、`.env.mcp`、Compose env 三层职责已明确，部署文档不再各自维护不同说法。
- 部署资产已经可以通过静态测试与脚本校验做 drift 守卫，不再只靠手工维护。

---

## 推荐实施顺序

### Step 1

`Memory Layers` contract + query trace 扩展

原因：

- 这是后续 MCP 和 operator 设计的共同基础
- 风险主要在 schema 与兼容性，适合先收口

### Step 2

`Expanded MCP Surface`（已完成）

原因：

- 能最快把增强价值暴露给 agent 用户
- 仍然不需要前端先动

### Step 3

`Observability & Operator UX` 后端聚合接口（已完成）

原因：

- 先把 operator 数据面整理出来，再做页面，避免 UI 先写死

### Step 4

`Observability & Operator UX` 前端页面与跳转联动（已完成）

原因：

- 数据面稳定后再接页面，返工更少

### Step 5

`Deployment Standardization`（已完成）

原因：

- 不阻塞核心增强
- 放在增强后段更容易把最终接口和健康标准一次收口

---

## 非目标

增强阶段默认不做：

- 多用户协作
- SaaS 化计费
- 平台生态化
- 用外部 agent framework 重写当前系统
- 为“完整 vision”一次性推倒当前 Web / API / MCP 主链路

增强阶段的原则是：**在现有可交付版本之上增强，不推翻当前结构。**

---

## 进入条件

当下面条件同时满足时，建议进入增强阶段：

- 当前交付版本已经冻结
- 当前主链路回归稳定
- 文档与代码对齐
- 交付级构建和验证命令保持通过

---

## 退出条件

增强阶段每完成一个增强包，都至少应满足：

- 代码落地
- 文档更新
- 对应测试补齐
- 构建与合同验证通过

增强阶段不是一次性大改，应该按增强包逐个结束。

---

## 当前建议验证入口

增强阶段相关改动当前建议至少跑以下命令：

```bash
python3 -m pytest tests/test_query_api.py tests/test_query_trace.py tests/test_retrieval_facade.py tests/test_mcp_server.py tests/test_mcp_service.py tests/test_mcp_integration.py
npm --prefix frontend run test:mainline-contract
npm --prefix frontend run test:settings-contract
python3 scripts/generate_api_docs.py --check
npm --prefix frontend run build
npm --prefix frontend/api run build
```
