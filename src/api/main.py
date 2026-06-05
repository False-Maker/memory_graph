"""
Memory Graph - API Entry Point
"""

from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from src.core.config import AppConfig, get_config_path, get_settings
from src.core.graph_store import get_graph_store
from src.core.llm_manager import get_llm_manager
from src.core.query_trace import get_query_trace_store
from src.core.sync.source_models import SyncSourceConfig
from src.core.vector_store import get_vector_store
from src.api.routes import memories, query, graph, config, data, collectors, communities, sync, evals, temporal
from src.api.security import enforce_api_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan"""
    # Startup
    print("Memory Graph API starting up...")
    yield
    # Shutdown
    print("Memory Graph API shutting down...")


# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Memory Graph API",
    description="Personal AI Memory System based on GraphRAG",
    version="1.0.0",
    docs_url="/docs" if settings.app.docs_enabled else None,
    redoc_url="/redoc" if settings.app.docs_enabled else None,
    openapi_url="/openapi.json" if settings.app.docs_enabled else None,
    lifespan=lifespan,
)

# Add CORS middleware
cors_allow_origins = settings.app.cors.get("allow_origins", [])
if not cors_allow_origins or cors_allow_origins == ["*"]:
    cors_allow_origins = AppConfig().cors["allow_origins"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=settings.app.cors.get("allow_credentials", True),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(enforce_api_auth)


# Register routers
app.include_router(memories.router)
app.include_router(query.router)
app.include_router(graph.router)
app.include_router(communities.router)
app.include_router(config.router)
app.include_router(data.router)
app.include_router(collectors.router)
app.include_router(sync.router)
app.include_router(evals.router)
app.include_router(temporal.router)


# Get the project root directory
project_root = Path(__file__).parent.parent.parent
frontend_dist = project_root / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"
sidecar_base_url = os.getenv("SIDECAR_BASE_URL", "http://127.0.0.1:3001").rstrip("/")
RECENT_FAILURE_LIMIT = 20
_recent_failures: deque[dict[str, Any]] = deque(maxlen=RECENT_FAILURE_LIMIT)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_recent_failure(component: str, detail: str, *, source: str) -> None:
    """Record recent runtime failures for diagnostics visibility."""
    normalized_detail = detail.strip() if isinstance(detail, str) else str(detail)
    if not normalized_detail:
        normalized_detail = "unknown failure"

    now = _now_iso()
    for item in _recent_failures:
        if (
            item.get("component") == component
            and item.get("detail") == normalized_detail
            and item.get("source") == source
        ):
            item["last_seen_at"] = now
            item["count"] = int(item.get("count", 1)) + 1
            return

    _recent_failures.appendleft(
        {
            "component": component,
            "detail": normalized_detail,
            "source": source,
            "first_seen_at": now,
            "last_seen_at": now,
            "count": 1,
        }
    )


def _recent_failures_snapshot(limit: int = 10) -> list[dict[str, Any]]:
    return list(_recent_failures)[: max(limit, 0)]


def _classify_recent_failure(item: dict[str, Any]) -> dict[str, Any]:
    component = str(item.get("component") or "").strip().lower()
    detail = str(item.get("detail") or "").strip()
    lower_detail = detail.lower()

    category = "unknown"
    severity = "warning"
    suggested_action = "检查最近失败详情并按当前页面给出的诊断建议继续排查。"

    if component == "provider":
        if any(token in lower_detail for token in ("auth", "api key", "401", "403", "unauthorized", "forbidden")):
            category = "provider_auth"
            severity = "error"
            suggested_action = "到 Settings 检查当前 provider 的 API key、base URL 和模型名，再重新执行连接测试。"
        else:
            category = "provider_connectivity"
            severity = "error"
            suggested_action = "检查 provider 网络连通性、base URL 与超时，再重试连接测试。"
    elif component == "vector_store":
        if any(token in lower_detail for token in ("dimension", "mismatch")):
            category = "vector_dimension_mismatch"
            severity = "error"
            suggested_action = "先到 Settings 执行 reindex，确认 embedding 维度与当前索引一致。"
        else:
            category = "vector_store_io"
            severity = "warning"
            suggested_action = "检查向量索引目录权限与磁盘状态，再重试相关读写操作。"
    elif component == "graph_store":
        category = "sqlite_io"
        severity = "error"
        suggested_action = "检查 graph SQLite 文件路径、权限和磁盘状态，必要时先做备份后重启服务。"
    elif component == "task_chain":
        category = "sync_conflict"
        severity = "warning"
        suggested_action = "到 Diagnostics 或 Inbox 的外部记忆源区域检查 conflict、deleted records 和最近一次 pull/push 结果。"
    elif component == "sidecar":
        category = "sidecar_unreachable"
        severity = "warning"
        suggested_action = "确认 Sidecar 进程已启动，且 /health 与 /ready 可从当前 API 所在机器访问。"
    elif component == "mcp":
        category = "mcp_unreachable"
        severity = "warning"
        suggested_action = "确认 MCP transport、host、port、path 和 Bearer token 配置正确，再重试 MCP 状态检查。"

    return {
        **item,
        "category": category,
        "severity": severity,
        "suggested_action": suggested_action,
    }


def _recent_failures_with_taxonomy(limit: int = 10) -> list[dict[str, Any]]:
    return [_classify_recent_failure(item) for item in _recent_failures_snapshot(limit=limit)]


def _split_provider_results(raw_results: dict[str, Any]) -> tuple[dict[str, bool], dict[str, str]]:
    providers: dict[str, bool] = {}
    provider_errors: dict[str, str] = {}

    for key, value in raw_results.items():
        if key.endswith("_error") and isinstance(value, str):
            provider_errors[key.removesuffix("_error")] = value
        elif isinstance(value, bool):
            providers[key] = value

    return providers, provider_errors


def _get_diagnostics_sync_source_settings_path() -> Path:
    """Return the persisted sync-source settings path used by task-chain diagnostics."""
    return Path("data") / "sync-sources.json"


def _load_task_chain_source_settings() -> list[dict[str, Any]]:
    """Load configured sync sources for diagnostics."""
    path = _get_diagnostics_sync_source_settings_path()
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        raise ValueError("sync-sources.json is missing a valid 'sources' list")
    return [item for item in sources if isinstance(item, dict)]


def _resolve_task_chain_state_path(source_payload: dict[str, Any]) -> Path:
    """Resolve the local sync state file path for one configured source."""
    workspace_root = Path(source_payload.get("workspace_root") or ".").expanduser()
    config = SyncSourceConfig(
        workspace_root=workspace_root,
        source_system=str(source_payload.get("source_system") or "external"),
        workspace_id=str(source_payload.get("workspace_id") or "default"),
        source_paths=list(source_payload.get("source_paths") or []),
    )
    return config.resolved_state_path()


def _build_task_chain_source_status(source_payload: dict[str, Any]) -> dict[str, Any]:
    """Build one task-chain source health record from the local sync state file."""
    workspace_root = source_payload.get("workspace_root")
    base_status = {
        "source_id": str(source_payload.get("source_id") or ""),
        "label": source_payload.get("label"),
        "source_system": str(source_payload.get("source_system") or "external"),
        "workspace_id": str(source_payload.get("workspace_id") or "default"),
        "workspace_root": workspace_root,
        "state_status": "degraded",
        "record_count": 0,
        "conflicts": 0,
        "deleted_records": 0,
        "last_pulled_seq": 0,
        "detail": None,
    }

    if not workspace_root:
        base_status["detail"] = "workspace_root is not configured"
        return base_status

    state_path = _resolve_task_chain_state_path(source_payload)
    if not state_path.exists():
        base_status["detail"] = f"State file not found: {state_path}"
        return base_status

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        base_status["detail"] = f"Failed to read state file: {exc}"
        return base_status

    records = payload.get("records", {})
    if not isinstance(records, dict):
        base_status["detail"] = "State file is missing a valid 'records' object"
        return base_status

    conflicts = 0
    deleted_records = 0
    for record_payload in records.values():
        if not isinstance(record_payload, dict):
            continue
        sync_status = str(record_payload.get("sync_status") or "").strip().lower()
        if sync_status == "conflict":
            conflicts += 1
        elif sync_status == "deleted":
            deleted_records += 1

    state_status = "healthy" if conflicts == 0 else "degraded"
    detail = None if state_status == "healthy" else f"{conflicts} conflicted records require attention"
    return {
        **base_status,
        "state_status": state_status,
        "record_count": len(records),
        "conflicts": conflicts,
        "deleted_records": deleted_records,
        "last_pulled_seq": int(payload.get("last_pulled_seq", 0) or 0),
        "detail": detail,
    }


def _run_task_chain_check(*, source: str) -> dict[str, Any]:
    """Inspect configured sync sources and summarize task-chain health."""
    try:
        sources = _load_task_chain_source_settings()
    except Exception as exc:
        _record_recent_failure("task_chain", str(exc), source=source)
        return {
            "status": "degraded",
            "configured_sources": 0,
            "sources": [],
            "detail": str(exc),
        }

    if not sources:
        return {
            "status": "not_configured",
            "configured_sources": 0,
            "sources": [],
            "detail": "No sync sources configured",
        }

    source_statuses = [_build_task_chain_source_status(item) for item in sources]
    degraded_sources = [item for item in source_statuses if item.get("state_status") != "healthy"]
    for item in degraded_sources:
        if item.get("detail"):
            _record_recent_failure("task_chain", str(item["detail"]), source=source)

    return {
        "status": "healthy" if not degraded_sources else "degraded",
        "configured_sources": len(source_statuses),
        "sources": source_statuses,
        "detail": None if not degraded_sources else f"{len(degraded_sources)} sync source(s) need attention",
    }


def _run_config_check(*, source: str) -> dict[str, Any]:
    try:
        runtime_settings = get_settings()
        config_path = get_config_path(require_exists=True)
        return {
            "ok": True,
            "provider": runtime_settings.llm.provider,
            "path": str(config_path),
            "exists": True,
        }
    except Exception as exc:
        _record_recent_failure("config", str(exc), source=source)
        return {
            "ok": False,
            "error": str(exc),
        }


async def _run_sqlite_check(*, source: str) -> dict[str, Any]:
    try:
        graph_store = get_graph_store()
        sqlite_ok = await graph_store.test_connection()
        if not sqlite_ok:
            _record_recent_failure(
                "graph_store",
                "Graph store connection test returned false",
                source=source,
            )
        return {
            "ok": sqlite_ok,
            "path": str(getattr(graph_store, "_db_path", "unknown")),
        }
    except Exception as exc:
        _record_recent_failure("graph_store", str(exc), source=source)
        return {
            "ok": False,
            "error": str(exc),
        }


async def _run_vector_store_check(*, source: str) -> dict[str, Any]:
    try:
        vector_store = get_vector_store()
        vector_ok = await vector_store.test_connection()
        if not vector_ok:
            _record_recent_failure(
                "vector_store",
                "Vector store connection test returned false",
                source=source,
            )
        vector_state = await vector_store.get_index_state() if vector_ok else None
        return {
            "ok": vector_ok,
            "state": vector_state,
        }
    except Exception as exc:
        _record_recent_failure("vector_store", str(exc), source=source)
        return {
            "ok": False,
            "error": str(exc),
        }


async def _run_provider_check(*, source: str) -> dict[str, Any]:
    try:
        runtime_settings = get_settings()
        current_provider = runtime_settings.llm.provider
        llm = get_llm_manager()
        raw_results = await llm.test_connection()
        raw_results = raw_results if isinstance(raw_results, dict) else {}
        providers, provider_errors = _split_provider_results(raw_results)
        current_provider_ok = providers.get("current")
        if current_provider_ok is None:
            current_provider_ok = providers.get(current_provider)
        if current_provider_ok is None:
            current_provider_ok = any(providers.values()) if providers else False
        current_error = provider_errors.get("current") or provider_errors.get(current_provider)
        if current_error:
            _record_recent_failure("provider", current_error, source=source)
        elif not current_provider_ok:
            _record_recent_failure(
                "provider",
                f"{current_provider} connection check returned false",
                source=source,
            )
        return {
            "ok": bool(current_provider_ok),
            "current_provider": current_provider,
            "providers": providers,
            "provider_errors": provider_errors,
            "current_error": current_error,
        }
    except Exception as exc:
        _record_recent_failure("provider", str(exc), source=source)
        return {
            "ok": False,
            "current_provider": None,
            "providers": {},
            "provider_errors": {},
            "current_error": str(exc),
        }


async def _run_sidecar_check(*, source: str) -> dict[str, Any]:
    async def _probe(endpoint: str) -> tuple[bool, Any]:
        target_url = f"{sidecar_base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(target_url)
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.status_code == 200, response.json()
            return response.status_code == 200, {"status_code": response.status_code}
        except Exception as exc:
            return False, str(exc)

    health_ok, health_payload = await _probe("health")
    ready_ok, ready_payload = await _probe("ready")
    detail = None
    if not health_ok:
        detail = str(health_payload)
    elif not ready_ok:
        detail = str(ready_payload)

    if detail:
        _record_recent_failure("sidecar", detail, source=source)

    return {
        "ok": health_ok and ready_ok,
        "health_ok": health_ok,
        "ready_ok": ready_ok,
        "detail": detail,
        "health": health_payload,
        "ready": ready_payload,
        "base_url": sidecar_base_url,
    }


def _build_collectors_summary() -> dict[str, Any]:
    try:
        from src.api.routes.collectors.deps import get_unified_collector

        payload = get_unified_collector().get_status()
    except Exception as exc:
        return {
            "ok": False,
            "running": False,
            "total_collectors": 0,
            "official_collectors": 0,
            "running_collectors": 0,
            "running_official_collectors": 0,
            "detail": str(exc),
        }

    collectors = list(payload.get("collectors") or [])
    official_collectors = [
        item for item in collectors if str(item.get("support_tier") or "official") == "official"
    ]
    running_collectors = [item for item in collectors if item.get("running") is True]
    running_official_collectors = [item for item in official_collectors if item.get("running") is True]
    return {
        "ok": True,
        "running": bool(payload.get("running")),
        "total_collectors": len(collectors),
        "official_collectors": len(official_collectors),
        "running_collectors": len(running_collectors),
        "running_official_collectors": len(running_official_collectors),
        "queue_size": int(payload.get("queue_size", 0) or 0),
        "handlers_count": int(payload.get("handlers_count", 0) or 0),
    }


async def _run_mcp_status_check() -> dict[str, Any]:
    from src.mcp.server import MCPRuntimeConfig, create_mcp_server
    from src.mcp.service import MemoryGraphMCPService

    config = MCPRuntimeConfig.from_env()
    service = MemoryGraphMCPService()
    server = create_mcp_server(service=service, config=config)
    tool_names = sorted(tool.name for tool in await server.list_tools())
    core_tools = [
        "answer_question",
        "search_memories",
        "preview_memory_layer",
        "append_journal_entry",
        "bulk_save_memories",
        "check_duplicate",
        "list_sync_sources",
        "get_sync_source_status",
        "get_runtime_diagnostics",
    ]
    reachable: bool | None = None
    detail: str | None = None
    base_url = None

    if config.transport == "streamable-http":
        base_url = f"http://{config.host}:{config.port}{config.streamable_http_path}"
        reachable = False
        try:
            from pydantic import AnyUrl
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            headers = {"Authorization": f"Bearer {config.bearer_token}"} if config.bearer_token else None
            async with streamablehttp_client(base_url, headers=headers) as (read_stream, write_stream, _get_session_id):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    tool_names = sorted(tool.name for tool in tools_result.tools)
                    await session.read_resource(AnyUrl("memory-graph://stats"))
                    reachable = True
        except Exception as exc:
            detail = str(exc)
            _record_recent_failure("mcp", detail, source="/api/v1/mcp/status")
    else:
        detail = "stdio mode is process-local; remote reachability probe is not applicable"

    missing_core_tools = [tool for tool in core_tools if tool not in tool_names]
    return {
        "configured": True,
        "transport": config.transport,
        "reachable": reachable,
        "auth_enabled": bool(config.bearer_token),
        "tools_count": len(tool_names),
        "core_tools": core_tools,
        "missing_core_tools": missing_core_tools,
        "detail": detail,
        "base_url": base_url,
    }


def _build_operator_summary(
    *,
    runtime_payload: dict[str, Any],
    mcp_status: dict[str, Any],
) -> dict[str, Any]:
    query_runs = get_query_trace_store().list_recent(limit=50)
    succeeded = sum(1 for run in query_runs if getattr(run, "status", None) == "succeeded")
    failed = sum(1 for run in query_runs if getattr(run, "status", None) == "failed")
    running = sum(1 for run in query_runs if getattr(run, "status", None) == "running")
    recent_failures = list(runtime_payload.get("recent_failures") or [])
    task_chain = runtime_payload.get("task_chain") or {}
    collectors = runtime_payload.get("collectors") or {}

    return {
        "status": "healthy" if runtime_payload.get("status") == "healthy" else "warning",
        "generated_at": runtime_payload.get("generated_at") or _now_iso(),
        "runtime": {
            "status": runtime_payload.get("status"),
            "recent_failures_count": len(recent_failures),
            "task_chain_status": task_chain.get("status"),
        },
        "query_runs": {
            "total_recent": len(query_runs),
            "succeeded": succeeded,
            "failed": failed,
            "running": running,
        },
        "sync_sources": {
            "configured": int(task_chain.get("configured_sources", 0) or 0),
            "attention": len([item for item in list(task_chain.get("sources") or []) if item.get("state_status") != "healthy"]),
            "status": task_chain.get("status"),
        },
        "mcp": {
            "transport": mcp_status.get("transport"),
            "reachable": mcp_status.get("reachable"),
            "tools_count": mcp_status.get("tools_count"),
            "auth_enabled": mcp_status.get("auth_enabled"),
        },
        "collectors": {
            "running": collectors.get("running"),
            "official_collectors": collectors.get("official_collectors"),
            "running_official_collectors": collectors.get("running_official_collectors"),
        },
    }


def serve_frontend_index():
    """Return the built React Web entry when available."""
    if frontend_index.exists():
        return FileResponse(str(frontend_index))

    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Memory Graph API</title>
  </head>
  <body>
    <main>
      <h1>Memory Graph API</h1>
      <p>React Web build not found. Run <code>npm --prefix frontend run build</code> first.</p>
      <p><a href="/docs">Open API docs</a></p>
    </main>
  </body>
</html>
        """.strip()
    )


async def proxy_sidecar_probe(endpoint: str):
    """Proxy sidecar health probes so the built Web app can stay same-origin."""
    target_url = f"{sidecar_base_url}/{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.get(target_url)
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "DOWN",
                "message": "Failed to reach sidecar",
                "upstream": target_url,
                "detail": str(exc),
            },
        )

    content_type = upstream.headers.get("content-type", "")
    if "application/json" in content_type:
        return JSONResponse(status_code=upstream.status_code, content=upstream.json())

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=content_type or None,
    )


# Root endpoint - serve frontend
@app.get("/")
async def root():
    """Serve the frontend"""
    return serve_frontend_index()


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint with runtime dependency checks."""
    checks = {
        "config": _run_config_check(source="/health"),
        "sqlite": await _run_sqlite_check(source="/health"),
        "vector_store": await _run_vector_store_check(source="/health"),
    }

    is_healthy = all(check["ok"] for check in checks.values())
    payload = {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "Memory Graph API",
        "version": "1.0.0",
        "generated_at": _now_iso(),
        "checks": checks,
        "recent_failures": _recent_failures_snapshot(),
    }

    status_code = 200 if is_healthy else 503
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/api/v1/diagnostics/runtime")
async def runtime_diagnostics():
    """Runtime diagnostics for provider, stores, and recent failures."""
    checks = {
        "config": _run_config_check(source="/api/v1/diagnostics/runtime"),
        "provider": await _run_provider_check(source="/api/v1/diagnostics/runtime"),
        "sqlite": await _run_sqlite_check(source="/api/v1/diagnostics/runtime"),
        "vector_store": await _run_vector_store_check(source="/api/v1/diagnostics/runtime"),
    }
    task_chain = _run_task_chain_check(source="/api/v1/diagnostics/runtime")
    sidecar = await _run_sidecar_check(source="/api/v1/diagnostics/runtime")
    collectors = _build_collectors_summary()
    is_healthy = all(check["ok"] for check in checks.values())
    payload = {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "Memory Graph API",
        "version": "1.0.0",
        "generated_at": _now_iso(),
        "checks": checks,
        "task_chain": task_chain,
        "sidecar": sidecar,
        "collectors": collectors,
        "recent_failures": _recent_failures_with_taxonomy(),
    }
    # Keep diagnostics endpoint queryable even during unhealthy states.
    return JSONResponse(status_code=200, content=payload)


@app.get("/api/v1/diagnostics/operator-summary")
async def operator_summary():
    """Compact operator-focused summary for dashboard and diagnostics landing page."""
    runtime_payload = await runtime_diagnostics()
    runtime_json = json.loads(runtime_payload.body.decode("utf-8"))
    mcp_status = await _run_mcp_status_check()
    return JSONResponse(
        status_code=200,
        content=_build_operator_summary(runtime_payload=runtime_json, mcp_status=mcp_status),
    )


@app.get("/api/v1/mcp/status")
async def mcp_status():
    """Return configured MCP transport status and core tool availability."""
    return JSONResponse(status_code=200, content=await _run_mcp_status_check())


@app.get("/sidecar/health")
async def sidecar_health_proxy():
    """Proxy sidecar /health for the Web frontend."""
    return await proxy_sidecar_probe("health")


@app.get("/sidecar/ready")
async def sidecar_ready_proxy():
    """Proxy sidecar /ready for the Web frontend."""
    return await proxy_sidecar_probe("ready")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve built frontend assets and SPA routes without swallowing API 404s."""
    reserved_prefixes = ("api/", "docs", "redoc", "openapi.json", "health", "sidecar/")
    if full_path in reserved_prefixes or any(full_path.startswith(prefix) for prefix in reserved_prefixes):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    if frontend_dist.exists() and full_path:
        candidate = (frontend_dist / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(frontend_dist.resolve()):
            return FileResponse(str(candidate))

    return serve_frontend_index()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
    )
