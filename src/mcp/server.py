"""FastMCP server factory for Memory Graph."""

from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import AnyHttpUrl

from .service import MemoryGraphMCPService, SearchBackend


TransportName = Literal["stdio", "streamable-http"]
DEFAULT_SERVER_INSTRUCTIONS = (
    "Read-only Memory Graph MCP server for memory lookup, retrieval, and graph statistics."
)


class MCPDependencyError(RuntimeError):
    """Raised when the official MCP SDK is not importable."""


class StaticBearerTokenVerifier:
    """Minimal TokenVerifier implementation backed by one shared bearer token."""

    def __init__(self, token: str):
        self._token = token

    async def verify_token(self, token: str):
        if token != self._token:
            return None

        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token,
            client_id="memory-graph-client",
            scopes=["memory-graph"],
            resource=None,
        )


def _load_fastmcp() -> type[Any]:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise MCPDependencyError(
            "The official Python MCP SDK is required. Install mcp>=1.27,<2 or set "
            "PYTHONPATH to the local SDK path before running the server."
        ) from exc
    return FastMCP


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_transport(value: str | None, *, default: TransportName = "stdio") -> TransportName:
    normalized = (value or default).strip().lower()
    if normalized not in {"stdio", "streamable-http"}:
        supported = "stdio, streamable-http"
        raise ValueError(f"Unsupported MCP transport: {value}. Supported values: {supported}")
    return normalized  # type: ignore[return-value]


@dataclass(frozen=True)
class MCPRuntimeConfig:
    """Runtime config for the MCP server."""

    transport: TransportName = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    mount_path: str = "/"
    streamable_http_path: str = "/mcp"
    json_response: bool = True
    stateless_http: bool = True
    bearer_token: str | None = None

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "MCPRuntimeConfig":
        env = environ or os.environ
        return cls(
            transport=_normalize_transport(env.get("MEMORY_GRAPH_MCP_TRANSPORT")),
            host=env.get("MEMORY_GRAPH_MCP_HOST", "127.0.0.1"),
            port=int(env.get("MEMORY_GRAPH_MCP_PORT", "8000")),
            mount_path=env.get("MEMORY_GRAPH_MCP_MOUNT_PATH", "/"),
            streamable_http_path=env.get("MEMORY_GRAPH_MCP_STREAMABLE_HTTP_PATH", "/mcp"),
            json_response=_parse_bool(env.get("MEMORY_GRAPH_MCP_JSON_RESPONSE"), default=True),
            stateless_http=_parse_bool(env.get("MEMORY_GRAPH_MCP_STATELESS_HTTP"), default=True),
            bearer_token=(env.get("MEMORY_GRAPH_MCP_BEARER_TOKEN") or "").strip() or None,
        )


def create_mcp_server(
    *,
    service: MemoryGraphMCPService | None = None,
    config: MCPRuntimeConfig | None = None,
    name: str = "Memory Graph",
    instructions: str = DEFAULT_SERVER_INSTRUCTIONS,
) -> Any:
    """Create the FastMCP server and register the read-only tools/resources."""
    resolved_service = service or MemoryGraphMCPService()
    resolved_config = config or MCPRuntimeConfig.from_env()
    FastMCP = _load_fastmcp()
    auth = None
    token_verifier = None
    if resolved_config.bearer_token:
        from mcp.server.fastmcp.server import AuthSettings

        base_url = AnyHttpUrl(f"http://{resolved_config.host}:{resolved_config.port}")
        auth = AuthSettings(
            issuer_url=base_url,
            resource_server_url=base_url,
            required_scopes=["memory-graph"],
        )
        token_verifier = StaticBearerTokenVerifier(resolved_config.bearer_token)

    mcp = FastMCP(
        name=name,
        instructions=instructions,
        host=resolved_config.host,
        port=resolved_config.port,
        mount_path=resolved_config.mount_path,
        streamable_http_path=resolved_config.streamable_http_path,
        json_response=resolved_config.json_response,
        stateless_http=resolved_config.stateless_http,
        auth=auth,
        token_verifier=token_verifier,
    )

    @mcp.tool(
        name="save_memory",
        description="Create or update a memory record through the shared memory service.",
        structured_output=True,
    )
    async def save_memory(
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        source_system: str = "manual",
    ) -> dict[str, Any]:
        return await resolved_service.save_memory(
            content=content,
            metadata=metadata,
            memory_id=memory_id,
            source_system=source_system,
        )

    @mcp.tool(
        name="append_journal_entry",
        description="Append a journal entry through the shared memory service with journal defaults.",
        structured_output=True,
    )
    async def append_journal_entry(
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await resolved_service.append_journal_entry(
            content=content,
            title=title,
            tags=tags,
            metadata=metadata,
        )

    @mcp.tool(
        name="bulk_save_memories",
        description="Bulk create or update multiple memory records in one request.",
        structured_output=True,
    )
    async def bulk_save_memories(
        memories: list[dict[str, Any]],
        source_system: str = "manual",
    ) -> dict[str, Any]:
        return await resolved_service.bulk_save_memories(
            memories=memories,
            source_system=source_system,
        )

    @mcp.tool(
        name="delete_memory",
        description="Delete a memory record by ID.",
        structured_output=True,
    )
    async def delete_memory(memory_id: str) -> dict[str, Any]:
        return await resolved_service.delete_memory(memory_id)

    @mcp.tool(
        name="check_duplicate",
        description="Check whether a candidate memory is likely a duplicate of existing memories.",
        structured_output=True,
    )
    async def check_duplicate(
        content: str,
        top_k: int = 5,
        min_relevance: float = 0.8,
        filter_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await resolved_service.check_duplicate(
            content=content,
            top_k=top_k,
            min_relevance=min_relevance,
            filter_metadata=filter_metadata,
        )

    @mcp.tool(
        name="archive_memory",
        description="Archive a memory without deleting it.",
        structured_output=True,
    )
    async def archive_memory(memory_id: str) -> dict[str, Any]:
        return await resolved_service.archive_memory(memory_id)

    @mcp.tool(
        name="unarchive_memory",
        description="Restore an archived memory back into the active list.",
        structured_output=True,
    )
    async def unarchive_memory(memory_id: str) -> dict[str, Any]:
        return await resolved_service.unarchive_memory(memory_id)

    @mcp.tool(
        name="answer_question",
        description="Answer a question using the unified retrieval facade and return cited sources.",
        structured_output=True,
    )
    async def answer_question(
        question: str,
        strategy: str = "graphrag",
        top_k: int = 5,
        include_sources: bool = True,
        layer: str = "auto",
        layer_budget_override: int | None = None,
    ) -> dict[str, Any]:
        return await resolved_service.answer_question(
            question=question,
            strategy=strategy,
            top_k=top_k,
            include_sources=include_sources,
            layer=layer,
            layer_budget_override=layer_budget_override,
        )

    @mcp.tool(
        name="search_memories",
        description="Search memories with either the standard retriever or GraphRAG retriever.",
        structured_output=True,
    )
    async def search_memories(
        query: str,
        top_k: int = 5,
        backend: SearchBackend = "graphrag",
        strategy: str = "hybrid",
        include_sources: bool = True,
        layer: str = "auto",
        layer_budget_override: int | None = None,
    ) -> dict[str, Any]:
        return await resolved_service.search_memories(
            query=query,
            top_k=top_k,
            backend=backend,
            strategy=strategy,
            include_sources=include_sources,
            layer=layer,
            layer_budget_override=layer_budget_override,
        )

    @mcp.tool(
        name="preview_memory_layer",
        description="Preview how the memory layer resolver would build context for a query.",
        structured_output=True,
    )
    async def preview_memory_layer(
        layer: str = "auto",
        question: str | None = None,
        strategy: str = "hybrid",
        top_k: int = 5,
        layer_budget_override: int | None = None,
    ) -> dict[str, Any]:
        return await resolved_service.preview_memory_layer(
            layer=layer,
            question=question,
            strategy=strategy,
            top_k=top_k,
            layer_budget_override=layer_budget_override,
        )

    @mcp.tool(
        name="get_memory",
        description="Fetch a single memory record by ID.",
        structured_output=True,
    )
    async def get_memory(memory_id: str) -> dict[str, Any]:
        return await resolved_service.get_memory(memory_id)

    @mcp.tool(
        name="get_memory_context",
        description="Fetch the entity/community context for one memory ID.",
        structured_output=True,
    )
    async def get_memory_context(memory_id: str) -> dict[str, Any]:
        return await resolved_service.get_memory_context(memory_id)

    @mcp.tool(
        name="list_memories",
        description="List memories with pagination and archive filtering.",
        structured_output=True,
    )
    async def list_memories(
        limit: int = 20,
        offset: int = 0,
        status: str = "active",
    ) -> dict[str, Any]:
        return await resolved_service.list_memories(limit=limit, offset=offset, status=status)

    @mcp.tool(
        name="list_sync_sources",
        description="List saved sync source settings known to Memory Graph.",
        structured_output=True,
    )
    async def list_sync_sources() -> dict[str, Any]:
        return await resolved_service.list_sync_sources()

    @mcp.tool(
        name="get_sync_source_status",
        description="Inspect current status for one saved sync source.",
        structured_output=True,
    )
    async def get_sync_source_status(source_id: str) -> dict[str, Any]:
        return await resolved_service.get_sync_source_status(source_id)

    @mcp.tool(
        name="get_runtime_diagnostics",
        description="Return backend runtime diagnostics for providers, stores, task chain, and recent failures.",
        structured_output=True,
    )
    async def get_runtime_diagnostics() -> dict[str, Any]:
        return await resolved_service.get_runtime_diagnostics()

    @mcp.tool(
        name="get_graph_stats",
        description="Return high-level graph statistics.",
        structured_output=True,
    )
    async def get_graph_stats() -> dict[str, Any]:
        return await resolved_service.get_graph_stats()

    @mcp.tool(
        name="list_entities",
        description="List graph entities with optional type filtering and pagination.",
        structured_output=True,
    )
    async def list_entities(
        entity_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await resolved_service.list_entities(
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )

    @mcp.tool(
        name="get_entity",
        description="Fetch a single graph entity by ID and include linked community IDs.",
        structured_output=True,
    )
    async def get_entity(entity_id: str) -> dict[str, Any]:
        return await resolved_service.get_entity(entity_id)

    @mcp.tool(
        name="get_entity_neighbors",
        description="Fetch graph neighbors for a single entity ID.",
        structured_output=True,
    )
    async def get_entity_neighbors(entity_id: str, depth: int = 1) -> dict[str, Any]:
        return await resolved_service.get_entity_neighbors(entity_id, depth=depth)

    @mcp.tool(
        name="list_communities",
        description="List communities with optional level filtering and pagination.",
        structured_output=True,
    )
    async def list_communities(
        level: int | None = None,
        limit: int = 20,
        offset: int = 0,
        require_summary: bool = False,
        include_entity_ids: bool = False,
    ) -> dict[str, Any]:
        return await resolved_service.list_communities(
            level=level,
            limit=limit,
            offset=offset,
            require_summary=require_summary,
            include_entity_ids=include_entity_ids,
        )

    @mcp.tool(
        name="get_community",
        description="Fetch one community record by ID.",
        structured_output=True,
    )
    async def get_community(community_id: str, include_entity_ids: bool = True) -> dict[str, Any]:
        return await resolved_service.get_community(
            community_id,
            include_entity_ids=include_entity_ids,
        )

    @mcp.tool(
        name="get_community_entities",
        description="List leaf entities contained by a community.",
        structured_output=True,
    )
    async def get_community_entities(community_id: str, limit: int = 50) -> dict[str, Any]:
        return await resolved_service.get_community_entities(community_id, limit=limit)

    @mcp.tool(
        name="get_community_relationships",
        description="List relationships whose endpoints both belong to a community.",
        structured_output=True,
    )
    async def get_community_relationships(community_id: str, limit: int = 50) -> dict[str, Any]:
        return await resolved_service.get_community_relationships(community_id, limit=limit)

    @mcp.tool(
        name="list_query_runs",
        description="List recent query runs recorded by the backend trace store.",
        structured_output=True,
    )
    async def list_query_runs(limit: int = 10) -> dict[str, Any]:
        return await resolved_service.list_query_runs(limit=limit)

    @mcp.tool(
        name="get_query_run",
        description="Fetch one backend query run trace by run ID.",
        structured_output=True,
    )
    async def get_query_run(run_id: str) -> dict[str, Any]:
        return await resolved_service.get_query_run(run_id)

    @mcp.tool(
        name="get_entity_timeline",
        description="Return the temporal timeline for one entity.",
        structured_output=True,
    )
    async def get_entity_timeline(entity_id: str) -> dict[str, Any]:
        return await resolved_service.get_entity_timeline(entity_id)

    @mcp.tool(
        name="get_entity_state_as_of",
        description="Return the temporal state for one entity at a specific timestamp.",
        structured_output=True,
    )
    async def get_entity_state_as_of(entity_id: str, as_of: str) -> dict[str, Any]:
        return await resolved_service.get_entity_state_as_of(entity_id, as_of=as_of)

    @mcp.resource(
        "memory-graph://stats",
        name="memory_graph_stats",
        description="Graph and vector index stats snapshot.",
        mime_type="application/json",
    )
    async def memory_graph_stats() -> str:
        return resolved_service.format_resource_payload(await resolved_service.get_stats_resource_payload())

    @mcp.resource(
        "memory-graph://memories/recent",
        name="recent_memories",
        description="Recent active memories snapshot.",
        mime_type="application/json",
    )
    async def recent_memories() -> str:
        return resolved_service.format_resource_payload(
            await resolved_service.get_recent_memories_resource_payload(limit=10)
        )

    @mcp.resource(
        "memory-graph://query-runs/recent",
        name="recent_query_runs",
        description="Recent backend query run trace snapshot.",
        mime_type="application/json",
    )
    async def recent_query_runs() -> str:
        return resolved_service.format_resource_payload(
            await resolved_service.get_recent_query_runs_resource_payload(limit=10)
        )

    @mcp.resource(
        "memory-graph://diagnostics/runtime",
        name="runtime_diagnostics",
        description="Runtime diagnostics snapshot for providers, stores, sync task chain, and recent failures.",
        mime_type="application/json",
    )
    async def runtime_diagnostics_resource() -> str:
        return resolved_service.format_resource_payload(
            await resolved_service.get_runtime_diagnostics_resource_payload()
        )

    @mcp.resource(
        "memory-graph://sync-sources/status",
        name="sync_sources_status",
        description="Saved sync source status snapshot.",
        mime_type="application/json",
    )
    async def sync_sources_status_resource() -> str:
        return resolved_service.format_resource_payload(
            await resolved_service.get_sync_sources_status_resource_payload()
        )

    @mcp.resource(
        "memory-graph://layers/default-preview",
        name="default_layer_preview",
        description="Preview of the default memory layer resolver.",
        mime_type="application/json",
    )
    async def default_layer_preview_resource() -> str:
        return resolved_service.format_resource_payload(
            await resolved_service.get_default_layer_preview_resource_payload()
        )

    setattr(mcp, "_memory_graph_service", resolved_service)
    setattr(mcp, "_memory_graph_config", resolved_config)
    return mcp


def create_streamable_http_app(
    *,
    service: MemoryGraphMCPService | None = None,
    config: MCPRuntimeConfig | None = None,
) -> tuple[Any, Any]:
    """Create a FastMCP server plus its streamable-http ASGI app."""
    server = create_mcp_server(service=service, config=config)
    return server, server.streamable_http_app()


@asynccontextmanager
async def mcp_session_manager_lifespan(server: Any):
    """Run the lazy streamable-http session manager around an ASGI app lifespan."""
    async with server.session_manager.run():
        yield


def run_server(
    *,
    service: MemoryGraphMCPService | None = None,
    config: MCPRuntimeConfig | None = None,
    transport: TransportName | None = None,
) -> Any:
    """Create and run the MCP server with the requested transport."""
    resolved_config = config or MCPRuntimeConfig.from_env()
    resolved_transport = transport or resolved_config.transport
    server = create_mcp_server(service=service, config=resolved_config)
    mount_path = resolved_config.mount_path if resolved_transport == "streamable-http" else None
    server.run(transport=resolved_transport, mount_path=mount_path)
    return server


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Memory Graph MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        help="MCP transport to run. Defaults to MEMORY_GRAPH_MCP_TRANSPORT or stdio.",
    )
    parser.add_argument("--host", help="Host for streamable-http mode.")
    parser.add_argument("--port", type=int, help="Port for streamable-http mode.")
    parser.add_argument("--mount-path", help="Mount path for streamable-http mode.")
    parser.add_argument("--streamable-http-path", help="Path that serves the streamable-http endpoint.")
    parser.add_argument(
        "--stateless-http",
        choices=["true", "false"],
        help="Whether streamable-http sessions should be stateless.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for stdio or streamable-http serving."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    config = MCPRuntimeConfig.from_env()
    config = replace(
        config,
        transport=_normalize_transport(args.transport, default=config.transport),
        host=args.host or config.host,
        port=args.port or config.port,
        mount_path=args.mount_path or config.mount_path,
        streamable_http_path=args.streamable_http_path or config.streamable_http_path,
        stateless_http=_parse_bool(args.stateless_http, default=config.stateless_http),
    )
    run_server(config=config)
    return 0


__all__ = [
    "DEFAULT_SERVER_INSTRUCTIONS",
    "MCPDependencyError",
    "MCPRuntimeConfig",
    "create_mcp_server",
    "create_streamable_http_app",
    "main",
    "mcp_session_manager_lifespan",
    "run_server",
]
