# Engram Platform 对接清单

**目的**：记录 `Memory_graph` 作为 `engram-platform` 外部 memory service 时，服务端对接边界与完成状态。  
**范围**：只覆盖对接 `engram-platform` 当前统一 `MemoryStore` / `MemoryBackend` 契约所需的服务端收口，不展开前端产品面或泛化 roadmap。

---

## 1. 结论

当前 `Memory_graph` v1 已经是完整可运行服务；截至 `2026-04-18`，面向 `engram-platform` 当前统一 memory 契约的服务端 gap 已完成收口。

平台侧当前已经完成的部分：

- 统一 `MemoryStore` 契约已接住
- 外部服务不可达时主任务可 best-effort 降级
- `search/query filters/cursor/bundle per-scope` 已在 adapter/store 层本地收口
- operator 可见 memory backend 运行状态

当前结论：

- `engram-platform` 不再需要为 metadata 字段缺失做 adapter 级补洞
- `engram-platform` 不再需要为 structured query 主要依赖 list fallback
- `engram-platform` 可直接调用统一 `sync.push/pull/state` 契约
- query source 已返回足够 metadata，平台侧只需要保留轻量展示转换
- 文本查询 + filter 已在服务端组合，并附带分页与诊断字段

---

## 2. 必须补齐

### 2.1 memory metadata schema 补齐

状态：`已完成`

当前 [src/api/schemas/memory.py](../src/api/schemas/memory.py) 的 `MemoryMetadata` 仅覆盖：

- `source`
- `workspace_id`
- `external_id`
- `source_path`
- `record_type`
- `title`
- `tags`
- `timestamp`
- `content_checksum`
- `external_revision`
- `external_updated_at`
- `platform`
- `conversation_id`
- `archived`
- `archived_at`

要完整承接 `engram-platform`，还需要补齐这些字段：

- `scope`
- `scope_id`
- `visibility`
- `owner`
- `session_id`
- `thread_id`
- `task_id`
- `artifact_id`
- `summary`
- `confidence`
- `freshness`
- `pinned`
- `expires_at`

### 2.2 manual ingest 写路径真正保存这些字段

状态：`已完成`

当前 [src/core/memory_service.py](../src/core/memory_service.py) 在 `vector_metadata` 中只保存精简 metadata 子集。  
需要保证 `POST /api/v1/memories` 写入时，上述字段不会在 schema 或 service 层被吞掉。

### 2.3 sync ingest 写路径真正保存这些字段

状态：`已完成`

当前 [src/core/sync/service_builders.py](../src/core/sync/service_builders.py) 的 `build_vector_metadata()` 只构造：

- `source`
- `workspace_id`
- `external_id`
- `source_path`
- `record_type`
- `title`
- `tags`
- `content_checksum`
- `external_updated_at`
- `external_revision`

需要扩成和平台契约一致的 metadata surface，至少保证 sync 路径不会丢失：

- `scope/scope_id`
- `visibility/owner`
- `session_id/thread_id/task_id/artifact_id`
- `summary/confidence/freshness/pinned/expires_at`

### 2.4 query request 补服务端原生过滤字段

状态：`已完成`

当前 [src/api/schemas/query.py](../src/api/schemas/query.py) 的 `QueryRequest` 只有：

- `question`
- `strategy`
- `retrieval_mode`
- `top_k`
- `include_sources`
- `session_id`

对接 `engram-platform` 还需要服务端原生支持这些查询维度：

- `scopes`
- `scope_ids`
- `types`
- `visibility`
- `tags`
- `workspace_id`
- `session_id`
- `task_id`
- `thread_id`
- `user_id`
- `cursor`
- `include_expired`

### 2.5 query response 补来源 metadata 字段

状态：`已完成`

当前 [src/api/routes/query.py](../src/api/routes/query.py) 只向外透出有限 provenance 字段。  
需要确保 source payload 至少可回出：

- `scope`
- `scope_id`
- `visibility`
- `owner`
- `workspace_id`
- `session_id`
- `thread_id`
- `task_id`
- `artifact_id`
- `record_type`
- `summary`
- `confidence`
- `freshness`
- `pinned`
- `expires_at`

否则 `engram-platform` 仍然只能继续在 adapter 侧做大量 fallback / 本地过滤。

### 2.6 sync HTTP 契约补 Engram 兼容入口

状态：`已完成`

当前 [src/api/routes/sync.py](../src/api/routes/sync.py) 暴露的是 source-oriented 路由：

- `POST /api/v1/sync/sources/memories:batch-upsert`
- `GET /api/v1/sync/sources/{source_system}/changes`
- `GET /api/v1/sync/sources/{source_system}/state`
- `POST /api/v1/sync/sources/{source_system}/reconcile`

要完整承接 `engram-platform` 当前对接方式，需要补一层通用兼容 surface，至少覆盖：

- `POST /api/v1/sync/push`
- `GET /api/v1/sync/pull`
- `GET /api/v1/sync/state`

这层可以内部复用现有 source-oriented service，不一定要重写 sync 内核，但 HTTP contract 需要对齐。

### 2.7 sync response 字段名和语义对齐

状态：`已完成`

平台当前需要的统一结果语义包括：

- push：`externalId/status/memoryId/serverVersion/detail`
- pull：`nextCursor/changes[]`
- change：`cursor/changeType/memoryId/externalId/serverVersion/record`
- state：`workspaceId/activeRecords/tombstones/conflicts/lastChangeCursor/metadata`

现有 sync 接口虽然有相近能力，但字段名、包裹层和语义仍偏 `Memory_graph` 自身实现，需要对齐。

### 2.8 memory list 增加结构化 filter

状态：`已完成`

当前 [src/api/routes/memories.py](../src/api/routes/memories.py) 的 `GET /api/v1/memories` 只支持：

- `limit`
- `offset`
- `status=active|archived|all`

如果不补 service 端结构化 filter，平台的 structured query 永远只能走 list fallback 或本地过滤。  
至少需要支持：

- `workspace_id`
- `session_id`
- `task_id`
- `thread_id`
- `scope`
- `scope_id`
- `record_type`
- `tags`
- `visibility`
- `include_expired`

### 2.9 summary 真正读写一致

状态：`已完成`

当前 [src/api/schemas/memory.py](../src/api/schemas/memory.py) 的 `MemoryResponse` 有 `summary`，但 [src/api/routes/memories.py](../src/api/routes/memories.py) 的读路由没有真正赋值。  
需要保证：

- write 路径能保存 `summary`
- get/list/query 三条读路径能稳定回出 `summary`

---

## 3. 强烈建议补

### 3.1 文本检索 + filter 的服务端原生组合

状态：`已完成`

即使平台 adapter 已能本地过滤，真正要“完善对接”，还是应在服务端原生支持：

- text query + metadata filter
- text query + scope filter
- text query + workspace/session/task/thread 过滤

当前实现说明：

- `POST /api/v1/query` 已在服务端执行 text query + metadata filter 组合
- 结构化过滤在服务端完成，不再要求平台 adapter 本地兜底
- 返回结果附带 `candidate_window` 与 `warnings`

### 3.2 稳定分页语义

状态：`已完成`

当前 memories list 是 `limit/offset`，query 主接口没有分页 contract。  
建议至少统一出一套稳定语义：

- memories list：保留 `limit/offset` 或新增 cursor，但要明确 next page 规则
- query/filter：若支持分页，给出 `next_cursor`
- sync change feed：把 cursor 语义稳定到 API 文档和 OpenAPI

### 3.3 查询是否降级 / 是否截断的诊断字段

状态：`已完成`

建议 query/list/sync 结果补充诊断信息，例如：

- `applied_filters`
- `server_side_filtered`
- `truncated`
- `candidate_window`
- `warnings`

这样 `engram-platform` 可以少做猜测和自定义 warning。

### 3.4 OpenAPI / 文档自动同步

状态：`已完成`

当前 [docs/API.md](./API.md) 是自动生成的。  
只要改了上述 contract，就要同步：

- OpenAPI
- `docs/API.md`
- 对接说明文档

避免对接方继续按旧 contract 写 adapter。

---

## 4. 可后置

这些不是当前 `engram-platform` 对接 blocker，可以后置：

- 更强的 operator/admin 聚合面
- MCP surface 的额外增强
- 更深的 GraphRAG 召回优化
- 更广的 collector 扩张

---

## 5. 实施结果

按下面顺序已完成收口：

1. 补齐 `MemoryMetadata` schema
2. 补 manual/sync 两条写路径的 metadata 保存
3. 补 get/list/query 三条读路径的 metadata / summary 回传
4. 补 query request 的原生 filter 字段
5. 补统一 sync 兼容入口 `push/pull/state`
6. 补结构化 memories list filter
7. 补文本检索 + filter 的服务端原生组合、分页与诊断字段

---

## 6. 完成标准

当前已满足以下条件，可认为 `Memory_graph` 已对 `engram-platform` 完成服务端对接收口：

- `engram-platform` 不再需要为 metadata 字段缺失做 adapter 级补洞
- `engram-platform` 不再需要为 structured query 主要依赖 list fallback
- `engram-platform` 可直接调用统一 `sync.push/pull/state` 契约
- query source 返回足够 metadata，平台侧只保留少量展示层转换
- 文本查询 + filter 的主要链路不再长期依赖 candidate-window warning
