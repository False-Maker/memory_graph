# Memory Graph API 文档

- 状态: Active
- 对齐基线: `src.api.main:app`
- 生成方式: `python3 scripts/generate_api_docs.py`
- 维护策略: 本文档由当前 OpenAPI 与 settings contract 自动生成；接口变更后必须重新生成并通过 `tests/test_api_docs.py`

## 1. 说明

这份文档不再手工维护整页接口清单，而是直接从当前代码暴露的 OpenAPI 和关键 settings schema 生成。

本文档保留三类信息：

- 当前公开 HTTP / WebSocket 入口地图
- 关键 settings contract（配置读取、保存、连通性测试、secure secret store 行为）
- 文档刷新命令与 drift 守卫入口

更细的请求/响应定义仍以 Swagger `/docs` 与 OpenAPI `/openapi.json` 为准。

## 2. 基础信息

| 项目 | 值 |
| --- | --- |
| 默认基础地址 | `http://127.0.0.1:8000` |
| Swagger | `/docs` |
| OpenAPI JSON | `/openapi.json` |
| 当前公开 HTTP paths | `84` |
| Sidecar 代理 | `/sidecar/health`、`/sidecar/ready` |

## 3. 响应约定

- 当前接口没有全局统一的 `{success,data}` 包装。
- 读取类接口通常直接返回对象或数组；管理类接口会按路由定义返回独立 schema。
- 失败响应默认遵循 FastAPI 风格；`PUT /api/v1/config` 的 secure secret store 不可用场景额外提供稳定的错误响应体。
- 常见状态码：`200`、`400`、`404`、`422`、`500`、`502`、`503`。

## 4. 文档维护

```bash
python3 scripts/generate_api_docs.py
python3 scripts/generate_api_docs.py --check
python3 -m pytest tests/test_api_docs.py
```

- `python3 scripts/generate_api_docs.py` 会刷新 [docs/API.md](/home/elucid/projects/web/Memory_graph/docs/API.md)。
- `--check` 适合本地 pre-commit 或 CI 做 docs drift 守卫。
- `tests/test_api_docs.py` 会把文档生成结果和仓库内文件做逐字比对。

## 5. 关键 Settings Contract

- `GET /api/v1/config` 现在同时暴露 `secret_storage`，让设置页知道当前环境是 `system_keyring` 还是 `environment_only`。
- `PUT /api/v1/config` 在 secure secret store 不可用且请求包含新 API key 时，返回稳定的 `503` 错误响应，而不是只抛原始异常文本。
- 设置 `MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE=1` 会显式进入 `environment_only` 模式，适合无 keyring 部署或隔离 smoke。
- `POST /api/v1/config/test-connection` 仍只测试当前表单值，不会持久化配置。

### GET /api/v1/config 响应
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `llm_provider` | string | yes | - | - |
| `embedding_model` | string | yes | - | - |
| `graph_backend` | string | yes | - | - |
| `vector_store_type` | string | yes | - | - |
| `app_host` | string | yes | - | - |
| `app_port` | integer | yes | - | - |
| `openai_base_url` | string | yes | - | - |
| `openai_model` | string | yes | - | - |
| `openai_api_key_configured` | boolean | no | false | - |
| `anthropic_base_url` | string | yes | - | - |
| `anthropic_model` | string | yes | - | - |
| `anthropic_api_key_configured` | boolean | no | false | - |
| `ollama_url` | string | yes | - | - |
| `ollama_model` | string | yes | - | - |
| `secret_storage` | SecretStorageStatus | yes | - | - |

### secret_storage 对象
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `available` | boolean | yes | - | - |
| `storage_type` | enum[system_keyring, environment_only] | yes | - | - |
| `backend` | string or null | no | - | - |
| `message` | string | yes | - | - |
| `fallback_env_vars` | array<string> | no | - | - |

### PUT /api/v1/config 请求体
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `llm_provider` | enum[openai, anthropic, ollama] or null | no | - | - |
| `openai_api_key` | string or null | no | - | - |
| `openai_base_url` | string or null | no | - | - |
| `openai_model` | string or null | no | - | - |
| `anthropic_api_key` | string or null | no | - | - |
| `anthropic_base_url` | string or null | no | - | - |
| `anthropic_model` | string or null | no | - | - |
| `ollama_url` | string or null | no | - | - |
| `ollama_model` | string or null | no | - | - |

### PUT /api/v1/config 成功响应
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | yes | - | - |
| `message` | string | yes | - | - |

### PUT /api/v1/config 失败响应（503）
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | no | false | - |
| `code` | string | yes | - | - |
| `message` | string | yes | - | - |
| `providers` | array<enum[openai, anthropic]> | no | - | - |
| `fallback_env_vars` | array<string> | no | - | - |
| `secret_storage` | SecretStorageStatus | yes | - | - |

### POST /api/v1/config/test-connection 响应
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | yes | - | - |
| `providers` | object<string, boolean> | no | - | - |
| `provider_errors` | object<string, string> | no | - | - |
| `graph_store` | boolean | no | false | - |
| `vector_store` | boolean | no | false | - |
| `current_error` | string or null | no | - | - |
| `error` | string or null | no | - | - |

## 6. 当前公开路由清单

### 系统与运行态
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/` | Root | 200 | - |
| GET | `/api/v1/diagnostics/runtime` | Runtime Diagnostics | 200 | - |
| GET | `/health` | Health Check | 200 | - |
| GET | `/sidecar/health` | Sidecar Health Proxy | 200 | - |
| GET | `/sidecar/ready` | Sidecar Ready Proxy | 200 | - |
| GET | `/{full_path}` | Serve Spa | 200, 422 | - |

### 配置
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/config` | Get Config | 200 | config |
| PUT | `/api/v1/config` | Update Config | 200, 422, 503 | config |
| POST | `/api/v1/config/test-connection` | Test Connections | 200, 422 | config |

### 记忆
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/memories` | List Memories | 200, 422 | memories |
| POST | `/api/v1/memories` | Create Memory | 200, 422 | memories |
| GET | `/api/v1/memories/{memory_id}` | Get Memory | 200, 422 | memories |
| DELETE | `/api/v1/memories/{memory_id}` | Delete Memory | 200, 422 | memories |
| POST | `/api/v1/memories/{memory_id}/archive` | Archive Memory | 200, 422 | memories |
| GET | `/api/v1/memories/{memory_id}/context` | Get Memory Context | 200, 422 | memories |
| POST | `/api/v1/memories/{memory_id}/unarchive` | Unarchive Memory | 200, 422 | memories |

### 检索
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/query` | Query Memories | 200, 422 | query |
| GET | `/api/v1/query/runs` | List Query Runs | 200, 422 | query |
| GET | `/api/v1/query/runs/{run_id}` | Get Query Run | 200, 422 | query |

### 图谱
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/graph/entities` | List Entities | 200, 422 | graph |
| GET | `/api/v1/graph/entities/{entity_id}` | Get Entity | 200, 422 | graph |
| GET | `/api/v1/graph/entities/{entity_id}/neighbors` | Get Entity Neighbors | 200, 422 | graph |
| GET | `/api/v1/graph/relationships` | List Relationships | 200, 422 | graph |
| GET | `/api/v1/graph/stats` | Get Graph Stats | 200 | graph |

### 社区
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/communities` | List Communities | 200, 422 | communities |
| POST | `/api/v1/communities/detect` | Detect Communities | 200, 422 | communities |
| GET | `/api/v1/communities/hierarchy` | Get Full Hierarchy | 200 | communities |
| GET | `/api/v1/communities/status` | Get Community Status | 200 | communities |
| GET | `/api/v1/communities/{community_id}` | Get Community | 200, 422 | communities |
| GET | `/api/v1/communities/{community_id}/ancestors` | Get Community Ancestors | 200, 422 | communities |
| GET | `/api/v1/communities/{community_id}/descendants` | Get Community Descendants | 200, 422 | communities |
| GET | `/api/v1/communities/{community_id}/entities` | Get Community Entities | 200, 422 | communities |
| GET | `/api/v1/communities/{community_id}/hierarchy` | Get Community Hierarchy | 200, 422 | communities |
| GET | `/api/v1/communities/{community_id}/relationships` | Get Community Relationships | 200, 422 | communities |
| POST | `/api/v1/communities/{community_id}/summarize` | Regenerate Summary | 200, 422 | communities |

### 数据与运维
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| DELETE | `/api/v1/data` | Clear All Data | 200 | data |
| GET | `/api/v1/data/export` | Export Data | 200 | data |
| POST | `/api/v1/data/import` | Import Data | 200, 422 | data |
| POST | `/api/v1/data/import-directory` | Import Directory | 200, 422 | data |
| GET | `/api/v1/data/import-runs` | Get Recent Import Runs | 200, 422 | data |
| POST | `/api/v1/data/import-runs/{run_id}/retry` | Retry Import Run | 200, 422 | data |
| POST | `/api/v1/data/import/conversations` | Import Conversations | 200, 422 | data |
| POST | `/api/v1/data/import/conversations/json` | Import Conversations Json | 200, 422 | data |
| GET | `/api/v1/data/import/formats` | Get Supported Formats | 200 | data |
| POST | `/api/v1/data/memories/batch` | Batch Create Memories | 200, 422 | data |
| POST | `/api/v1/data/reindex` | Rebuild Vector Index | 200, 422 | data |
| POST | `/api/v1/data/restore` | Restore Data | 200, 422 | data |
| POST | `/api/v1/data/scan-directory` | Scan Directory | 200, 422 | data |
| GET | `/api/v1/evals/retrieval` | Run Retrieval Eval | 200, 422 | evals |

### 同步
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/sync/pull` | Compat Sync Pull | 200, 422 | sync |
| POST | `/api/v1/sync/push` | Compat Sync Push | 200, 422 | sync |
| POST | `/api/v1/sync/sources/memories:batch-upsert` | Batch Upsert Source Memories | 200, 422 | sync |
| POST | `/api/v1/sync/sources/preview` | Preview Sync Source | 200, 422 | sync |
| GET | `/api/v1/sync/sources/settings` | List Sync Source Settings | 200 | sync |
| POST | `/api/v1/sync/sources/settings` | Create Sync Source Setting | 200, 422 | sync |
| PUT | `/api/v1/sync/sources/settings/{source_id}` | Update Sync Source Setting | 200, 422 | sync |
| DELETE | `/api/v1/sync/sources/settings/{source_id}` | Delete Sync Source Setting | 200, 422 | sync |
| POST | `/api/v1/sync/sources/settings/{source_id}/pull` | Pull Sync Source Setting | 200, 422 | sync |
| POST | `/api/v1/sync/sources/settings/{source_id}/push` | Push Sync Source Setting | 200, 422 | sync |
| POST | `/api/v1/sync/sources/settings/{source_id}/restore` | Restore Sync Source Setting | 200, 422 | sync |
| GET | `/api/v1/sync/sources/settings/{source_id}/status` | Get Sync Source Setting Status | 200, 422 | sync |
| POST | `/api/v1/sync/sources/settings/{source_id}/sync` | Sync Sync Source Setting | 200, 422 | sync |
| GET | `/api/v1/sync/sources/{source_system}/changes` | List Source Changes | 200, 422 | sync |
| DELETE | `/api/v1/sync/sources/{source_system}/memories/{workspace_id}/{external_id}` | Delete Source Memory | 200, 422 | sync |
| POST | `/api/v1/sync/sources/{source_system}/reconcile` | Reconcile Source Workspace | 200, 422 | sync |
| GET | `/api/v1/sync/sources/{source_system}/state` | Get Sync Source State | 200, 422 | sync |
| GET | `/api/v1/sync/state` | Compat Sync State | 200, 422 | sync |

### 采集器
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| POST | `/api/collectors/browser/capture` | Capture Browser Message | 200, 422 | collectors |
| GET | `/api/collectors/collectors/{collector_type}` | Get Collector Status | 200, 422 | collectors |
| POST | `/api/collectors/collectors/{collector_type}/start` | Start Collector | 200, 422 | collectors |
| POST | `/api/collectors/collectors/{collector_type}/stop` | Stop Collector | 200, 422 | collectors |
| GET | `/api/collectors/cursor/conversations` | Get Cursor Conversations | 200 | collectors |
| POST | `/api/collectors/cursor/import/{conversation_id}` | Import Cursor Conversation | 200, 422 | collectors |
| POST | `/api/collectors/file-watcher/import` | Import File | 200, 422 | collectors |
| GET | `/api/collectors/file-watcher/paths` | Get Watched Paths | 200 | collectors |
| POST | `/api/collectors/file-watcher/paths` | Add Watch Path | 200, 422 | collectors |
| DELETE | `/api/collectors/file-watcher/paths` | Remove Watch Path | 200, 422 | collectors |
| POST | `/api/collectors/import` | Import Message | 200, 422 | collectors |
| POST | `/api/collectors/import-directory` | Import Directory | 200, 422 | collectors |
| POST | `/api/collectors/scan-directory` | Scan Directory | 200, 422 | collectors |
| POST | `/api/collectors/start` | Start Collectors | 200, 422 | collectors |
| GET | `/api/collectors/status` | Get Collectors Status | 200 | collectors |
| POST | `/api/collectors/stop` | Stop Collectors | 200, 422 | collectors |
| GET | `/api/collectors/websocket/stats` | Get Websocket Stats | 200 | collectors |

### 其他
| 方法 | 路径 | 说明 | 状态码 | 标签 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/diagnostics/operator-summary` | Operator Summary | 200 | - |
| GET | `/api/v1/mcp/status` | Mcp Status | 200 | - |
| GET | `/api/v1/temporal/entities/{entity_id}` | Get Entity State As Of | 200, 422 | temporal |
| GET | `/api/v1/temporal/entities/{entity_id}/timeline` | Get Entity Timeline | 200, 422 | temporal |
| GET | `/api/v1/temporal/stats` | Get Temporal Stats | 200 | temporal |
| POST | `/api/v1/temporal/triples` | Create Temporal Triple | 200, 422 | temporal |
| DELETE | `/api/v1/temporal/triples/{triple_id}` | Delete Temporal Triple | 200, 422 | temporal |

### 非 OpenAPI 入口
| 方法 | 路径 | 说明 | 状态码 | 备注 |
| --- | --- | --- | --- | --- |
| GET | `/api/collectors/ws/collectors` | Collector websocket endpoint | 101 | WebSocket endpoint, intentionally not emitted by OpenAPI. |
