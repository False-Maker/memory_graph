"""Focused tests for the minimal Memory Graph MCP server."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

pytest.importorskip(
    "mcp.server.fastmcp",
    reason="Install mcp>=1.27,<2 or set PYTHONPATH=/tmp/mcpdeps before running MCP tests.",
)

import src.mcp.server as mcp_server_module
from src.mcp.server import (
    MCPRuntimeConfig,
    create_mcp_server,
    create_streamable_http_app,
    mcp_session_manager_lifespan,
    run_server,
)


def _sample_memory_payload() -> dict[str, object]:
    return {
        "id": "mem-1",
        "content": "Launch decisions and follow-up notes.",
        "summary": None,
        "metadata": {
            "source": "manual",
            "workspace_id": "workspace-main",
            "external_id": "ext-1",
            "source_path": "notes/launch.md",
            "record_type": "note",
            "title": "Launch note",
            "tags": ["launch", "roadmap"],
            "timestamp": "2026-04-15T08:30:00+00:00",
            "content_checksum": "sha256:abc",
            "external_revision": "3",
            "external_updated_at": "2026-04-15T09:00:00+00:00",
            "platform": "manual",
            "conversation_id": None,
            "archived": False,
            "archived_at": None,
            "scope": None,
            "scope_id": None,
            "visibility": None,
            "owner": None,
            "session_id": None,
            "thread_id": None,
            "task_id": None,
            "artifact_id": None,
            "summary": None,
            "confidence": None,
            "freshness": None,
            "pinned": None,
            "expires_at": None,
        },
        "provenance": {
            "type": "note",
            "time": "2026-04-15T08:30:00+00:00",
            "imported_from": "notes/launch.md",
        },
        "created_at": "2026-04-15T08:30:00+00:00",
    }


def _sample_search_payload(query: str, backend: str, strategy: str) -> dict[str, object]:
    return {
        "query": query,
        "backend": backend,
        "strategy": strategy,
        "layer_requested": "auto",
        "layer_used": "l2" if backend == "standard" else "l3",
        "layer_fallback_chain": ["l2"] if backend == "standard" else ["l3"],
        "context_token_estimate": 42,
        "layer_build_duration_ms": 5,
        "processing_time_ms": 19,
        "total_sources": 1,
        "total_communities": 1,
        "entities": ["launch", "roadmap"],
        "query_entities": ["launch"],
        "sources": [
            {
                "memory_id": "mem-1",
                "content": "Launch decisions and follow-up notes.",
                "relevance": 0.94,
                "entities": ["launch"],
                "metadata": {
                    "source": "manual",
                    "workspace_id": "workspace-main",
                    "external_id": "ext-1",
                    "source_path": "notes/launch.md",
                    "record_type": "note",
                    "title": "Launch note",
                    "tags": ["launch", "roadmap"],
                    "timestamp": "2026-04-15T08:30:00+00:00",
                    "content_checksum": "sha256:abc",
                    "external_revision": "3",
                    "external_updated_at": "2026-04-15T09:00:00+00:00",
                    "platform": "manual",
                    "conversation_id": None,
                    "archived": False,
                    "archived_at": None,
                },
                "provenance": {
                    "type": "note",
                    "time": "2026-04-15T08:30:00+00:00",
                    "imported_from": "notes/launch.md",
                },
                "community_id": "comm-1",
                "community_summary": "Launch planning and timeline decisions.",
            }
        ],
        "communities": [
            {
                "community_id": "comm-1",
                "title": "Launch Cluster",
                "summary": "Launch planning and timeline decisions.",
                "level": 1,
                "entities": ["launch", "roadmap"],
                "relationships": [{"source_id": "launch", "target_id": "roadmap", "type": "relates"}],
                "relevance": 0.89,
            }
        ],
    }


def _sample_answer_payload(question: str, strategy: str) -> dict[str, object]:
    search_payload = _sample_search_payload(question, "graphrag", strategy)
    return {
        "question": question,
        "strategy": strategy,
        "layer_requested": "auto",
        "layer_used": "l3",
        "layer_fallback_chain": ["l3"],
        "context_token_estimate": 42,
        "layer_build_duration_ms": 5,
        "answer": f"Answer for: {question}",
        "processing_time_ms": search_payload["processing_time_ms"],
        "total_sources": search_payload["total_sources"],
        "total_communities": search_payload["total_communities"],
        "entities": search_payload["entities"],
        "query_entities": search_payload["query_entities"],
        "sources": search_payload["sources"],
        "communities": search_payload["communities"],
    }


@pytest.fixture
def stub_service():
    memory_payload = _sample_memory_payload()
    graph_stats_payload = {
        "total_entities": 12,
        "total_relationships": 21,
        "entity_types": {"project": 4, "person": 8},
        "total_memories": 7,
    }
    context_payload = {
        "memory_id": "mem-1",
        "entities": [
            {"id": "entity-launch", "name": "Launch", "type": "project"},
            {"id": "entity-roadmap", "name": "Roadmap", "type": "document"},
        ],
        "communities": [
            {
                "community_id": "comm-1",
                "title": "Launch Cluster",
                "summary": "Launch planning and timeline decisions.",
                "level": 1,
            }
        ],
        "total_entities": 2,
        "total_communities": 1,
    }
    list_payload = {
        "memories": [memory_payload],
        "total": 1,
        "limit": 2,
        "offset": 1,
    }
    stats_resource_payload = {
        "graph": graph_stats_payload,
        "vector_index": {"status": "ready", "count": 7},
    }
    recent_memories_payload = {
        "limit": 10,
        "total": 1,
        "memories": [memory_payload],
    }
    entities_payload = {
        "entities": [
            {
                "id": "entity-launch",
                "name": "Launch",
                "type": "project",
                "properties": {"stage": "beta"},
                "source_text": "Launch",
                "confidence": 0.9,
                "created_at": "2026-04-15T08:30:00+00:00",
            }
        ],
        "total": 1,
        "limit": 20,
        "offset": 0,
        "entity_type": None,
    }
    entity_payload = {
        **entities_payload["entities"][0],
        "community_ids": ["comm-1"],
    }
    entity_neighbors_payload = {
        "entity_id": "entity-launch",
        "depth": 2,
        "total": 1,
        "neighbors": [
            {
                "id": "entity-roadmap",
                "name": "Roadmap",
                "type": "document",
                "distance": 1,
                "relationships": [{"id": "rel-1", "type": "relates", "target_id": "entity-roadmap"}],
            }
        ],
    }
    communities_payload = {
        "communities": [
            {
                "id": "comm-1",
                "level": 1,
                "title": "Launch Cluster",
                "summary": "Launch planning and timeline decisions.",
                "entity_count": 2,
                "rank": 0.89,
                "entity_ids": ["entity-launch", "entity-roadmap"],
            }
        ],
        "total": 1,
        "limit": 20,
        "offset": 0,
        "level": None,
        "require_summary": False,
    }
    community_payload = communities_payload["communities"][0]
    community_entities_payload = {
        "community_id": "comm-1",
        "total": 1,
        "entities": entities_payload["entities"],
    }
    community_relationships_payload = {
        "community_id": "comm-1",
        "total": 1,
        "relationships": [{"id": "rel-1", "source": "Launch", "target": "Roadmap", "type": "relates"}],
    }
    query_runs_payload = {
        "runs": [
            {
                "run_id": "qrun_1",
                "status": "succeeded",
                "question": "launch roadmap",
            }
        ],
        "total": 1,
        "limit": 10,
    }
    query_run_payload = {
        "run_id": "qrun_1",
        "status": "succeeded",
        "question": "launch roadmap",
        "strategy": "hybrid",
    }
    timeline_payload = {
        "entity_id": "entity-launch",
        "total": 1,
        "triples": [
            {
                "id": "triple-1",
                "entity_id": "entity-launch",
                "relation_type": "ships",
                "target_entity_id": "entity-roadmap",
                "valid_from": "2026-04-01T00:00:00+00:00",
                "valid_to": None,
                "confidence": 0.9,
                "source": "manual",
                "created_at": "2026-04-01T00:00:00+00:00",
                "metadata": {},
            }
        ],
    }
    state_as_of_payload = {
        "entity_id": "entity-launch",
        "as_of": "2026-04-15",
        "total": 1,
        "triples": timeline_payload["triples"],
    }
    recent_query_runs_payload = {
        "limit": 10,
        "total": 1,
        "runs": query_runs_payload["runs"],
    }
    journal_entry_payload = {
        "memory_id": "mem-journal",
        "result": "created",
        "server_version": 2,
        "entities_count": 0,
        "relationships_count": 0,
        "memory": memory_payload,
    }
    bulk_save_payload = {
        "results": [
            {"memory_id": "mem-1", "result": "created"},
            {"memory_id": "mem-2", "result": "updated"},
        ],
        "summary": {
            "total": 2,
            "created": 1,
            "updated": 1,
            "noop": 0,
            "failed": 0,
        },
    }
    duplicate_check_payload = {
        "content_preview": "Launch decisions and follow-up notes.",
        "top_k": 3,
        "min_relevance": 0.8,
        "total_matches": 1,
        "matches": [
            {
                "memory_id": "mem-1",
                "relevance": 0.94,
                "memory": memory_payload,
            }
        ],
    }
    sync_sources_payload = {
        "sources": [
            {
                "source_id": "src-1",
                "label": "Workspace Notes",
                "source_system": "notes",
                "workspace_id": "workspace-main",
                "workspace_root": "/tmp/workspace-main",
                "source_paths": ["notes/**/*.md"],
                "updated_at": "2026-04-20T00:00:00+00:00",
            }
        ],
        "total": 1,
    }
    sync_source_status_payload = {
        "source_id": "src-1",
        "status": "healthy",
    }
    runtime_diagnostics_payload = {
        "status": "healthy",
        "service": "Memory Graph API",
        "version": "1.0.0",
        "generated_at": "2026-04-20T00:00:00+00:00",
        "checks": {
            "config": {"ok": True},
            "provider": {"ok": True},
            "sqlite": {"ok": True},
            "vector_store": {"ok": True},
        },
        "task_chain": {"status": "healthy"},
        "recent_failures": [],
    }
    sync_sources_status_payload = {
        "total": 1,
        "sources": [sync_source_status_payload],
    }
    default_layer_preview_payload = {
        "requested_layer": "auto",
        "resolved_layer": "l3",
        "fallback_chain": ["l2", "l3"],
        "token_budget": 2048,
        "token_estimate": 88,
        "layer_build_duration_ms": 9,
        "warnings": ["fallback"],
        "context_items": [{"item_type": "source", "identifier": "mem-1"}],
        "question": None,
        "strategy": "hybrid",
        "top_k": 5,
    }
    preview_layer_payload = {
        "requested_layer": "auto",
        "resolved_layer": "l3",
        "fallback_chain": ["l2", "l3"],
        "token_budget": 2048,
        "token_estimate": 88,
        "layer_build_duration_ms": 9,
        "warnings": ["fallback"],
        "context_items": [{"item_type": "source", "identifier": "mem-1"}],
        "question": "launch roadmap",
        "strategy": "hybrid",
        "top_k": 4,
    }

    service = SimpleNamespace(
        save_memory=AsyncMock(
            return_value={
                "memory_id": "mem-1",
                "result": "created",
                "server_version": 1,
                "entities_count": 1,
                "relationships_count": 0,
                "memory": memory_payload,
            }
        ),
        append_journal_entry=AsyncMock(return_value=journal_entry_payload),
        bulk_save_memories=AsyncMock(return_value=bulk_save_payload),
        delete_memory=AsyncMock(
            return_value={
                "success": True,
                "memory_id": "mem-1",
                "server_version": 2,
                "sync_status": "deleted",
                "deleted": True,
            }
        ),
        archive_memory=AsyncMock(
            return_value={
                "success": True,
                "memory_id": "mem-1",
                "archived": True,
                "archived_at": "2026-04-15T09:00:00+00:00",
                "memory": {**memory_payload, "metadata": {**memory_payload["metadata"], "archived": True}},
            }
        ),
        unarchive_memory=AsyncMock(
            return_value={
                "success": True,
                "memory_id": "mem-1",
                "archived": False,
                "archived_at": None,
                "memory": {**memory_payload, "metadata": {**memory_payload["metadata"], "archived": False}},
            }
        ),
        answer_question=AsyncMock(
            side_effect=lambda **kwargs: _sample_answer_payload(kwargs["question"], kwargs["strategy"])
        ),
        check_duplicate=AsyncMock(return_value=duplicate_check_payload),
        search_memories=AsyncMock(
            side_effect=lambda **kwargs: _sample_search_payload(
                kwargs["query"], kwargs["backend"], kwargs["strategy"]
            )
        ),
        preview_memory_layer=AsyncMock(return_value=preview_layer_payload),
        list_sync_sources=AsyncMock(return_value=sync_sources_payload),
        get_sync_source_status=AsyncMock(return_value=sync_source_status_payload),
        get_runtime_diagnostics=AsyncMock(return_value=runtime_diagnostics_payload),
        get_memory=AsyncMock(return_value=memory_payload),
        get_memory_context=AsyncMock(return_value=context_payload),
        list_memories=AsyncMock(return_value=list_payload),
        get_graph_stats=AsyncMock(return_value=graph_stats_payload),
        list_entities=AsyncMock(return_value=entities_payload),
        get_entity=AsyncMock(return_value=entity_payload),
        get_entity_neighbors=AsyncMock(return_value=entity_neighbors_payload),
        list_communities=AsyncMock(return_value=communities_payload),
        get_community=AsyncMock(return_value=community_payload),
        get_community_entities=AsyncMock(return_value=community_entities_payload),
        get_community_relationships=AsyncMock(return_value=community_relationships_payload),
        list_query_runs=AsyncMock(return_value=query_runs_payload),
        get_query_run=AsyncMock(return_value=query_run_payload),
        get_entity_timeline=AsyncMock(return_value=timeline_payload),
        get_entity_state_as_of=AsyncMock(return_value=state_as_of_payload),
        get_stats_resource_payload=AsyncMock(return_value=stats_resource_payload),
        get_recent_memories_resource_payload=AsyncMock(return_value=recent_memories_payload),
        get_recent_query_runs_resource_payload=AsyncMock(return_value=recent_query_runs_payload),
        get_runtime_diagnostics_resource_payload=AsyncMock(return_value=runtime_diagnostics_payload),
        get_sync_sources_status_resource_payload=AsyncMock(return_value=sync_sources_status_payload),
        get_default_layer_preview_resource_payload=AsyncMock(return_value=default_layer_preview_payload),
        format_resource_payload=MagicMock(
            side_effect=lambda payload: json.dumps(payload, ensure_ascii=False, sort_keys=True)
        ),
        payloads=SimpleNamespace(
            answer=_sample_answer_payload("launch roadmap", "hybrid"),
            memory=memory_payload,
            context=context_payload,
            list_memories=list_payload,
            graph_stats=graph_stats_payload,
            entities=entities_payload,
            entity=entity_payload,
            entity_neighbors=entity_neighbors_payload,
            communities=communities_payload,
            community=community_payload,
            community_entities=community_entities_payload,
            community_relationships=community_relationships_payload,
            query_runs=query_runs_payload,
            query_run=query_run_payload,
            timeline=timeline_payload,
            state_as_of=state_as_of_payload,
            stats_resource=stats_resource_payload,
            recent_memories_resource=recent_memories_payload,
            recent_query_runs_resource=recent_query_runs_payload,
            journal_entry=journal_entry_payload,
            bulk_save=bulk_save_payload,
            duplicate_check=duplicate_check_payload,
            sync_sources=sync_sources_payload,
            sync_source_status=sync_source_status_payload,
            runtime_diagnostics=runtime_diagnostics_payload,
            sync_sources_status=sync_sources_status_payload,
            default_layer_preview=default_layer_preview_payload,
            preview_layer=preview_layer_payload,
        ),
    )
    return service


async def _assert_structured_tool_result(
    server,
    tool_name: str,
    arguments: dict[str, object],
    expected_payload: dict[str, object],
) -> None:
    content_blocks, structured_payload = await server.call_tool(tool_name, arguments)

    assert structured_payload == expected_payload
    assert len(content_blocks) == 1
    assert json.loads(content_blocks[0].text) == expected_payload


class TestMemoryGraphMCPServer:
    @pytest.mark.asyncio
    async def test_create_mcp_server_registers_tools_and_resources(self, stub_service):
        server = create_mcp_server(service=stub_service)

        tools = await server.list_tools()
        assert {tool.name for tool in tools} == {
            "save_memory",
            "append_journal_entry",
            "bulk_save_memories",
            "delete_memory",
            "check_duplicate",
            "archive_memory",
            "unarchive_memory",
            "answer_question",
            "search_memories",
            "preview_memory_layer",
            "list_sync_sources",
            "get_sync_source_status",
            "get_runtime_diagnostics",
            "get_memory",
            "get_memory_context",
            "list_memories",
            "get_graph_stats",
            "list_entities",
            "get_entity",
            "get_entity_neighbors",
            "list_communities",
            "get_community",
            "get_community_entities",
            "get_community_relationships",
            "list_query_runs",
            "get_query_run",
            "get_entity_timeline",
            "get_entity_state_as_of",
        }

        resources = await server.list_resources()
        assert {str(resource.uri) for resource in resources} >= {
            "memory-graph://stats",
            "memory-graph://memories/recent",
            "memory-graph://query-runs/recent",
            "memory-graph://diagnostics/runtime",
            "memory-graph://sync-sources/status",
            "memory-graph://layers/default-preview",
        }

        stats_contents = await server.read_resource("memory-graph://stats")
        assert len(stats_contents) == 1
        assert stats_contents[0].mime_type == "application/json"
        assert json.loads(stats_contents[0].content) == stub_service.payloads.stats_resource

        recent_contents = await server.read_resource("memory-graph://memories/recent")
        assert len(recent_contents) == 1
        assert recent_contents[0].mime_type == "application/json"
        assert json.loads(recent_contents[0].content) == stub_service.payloads.recent_memories_resource

        recent_runs_contents = await server.read_resource("memory-graph://query-runs/recent")
        assert len(recent_runs_contents) == 1
        assert recent_runs_contents[0].mime_type == "application/json"
        assert json.loads(recent_runs_contents[0].content) == stub_service.payloads.recent_query_runs_resource

        runtime_diagnostics_contents = await server.read_resource("memory-graph://diagnostics/runtime")
        assert len(runtime_diagnostics_contents) == 1
        assert runtime_diagnostics_contents[0].mime_type == "application/json"
        assert json.loads(runtime_diagnostics_contents[0].content) == stub_service.payloads.runtime_diagnostics

        sync_sources_contents = await server.read_resource("memory-graph://sync-sources/status")
        assert len(sync_sources_contents) == 1
        assert sync_sources_contents[0].mime_type == "application/json"
        assert json.loads(sync_sources_contents[0].content) == stub_service.payloads.sync_sources_status

        layer_preview_contents = await server.read_resource("memory-graph://layers/default-preview")
        assert len(layer_preview_contents) == 1
        assert layer_preview_contents[0].mime_type == "application/json"
        assert json.loads(layer_preview_contents[0].content) == stub_service.payloads.default_layer_preview

        stub_service.get_stats_resource_payload.assert_awaited_once_with()
        stub_service.get_recent_memories_resource_payload.assert_awaited_once_with(limit=10)
        stub_service.get_recent_query_runs_resource_payload.assert_awaited_once_with(limit=10)
        stub_service.get_runtime_diagnostics_resource_payload.assert_awaited_once_with()
        stub_service.get_sync_sources_status_resource_payload.assert_awaited_once_with()
        stub_service.get_default_layer_preview_resource_payload.assert_awaited_once_with()
        assert stub_service.format_resource_payload.call_count == 6

    @pytest.mark.asyncio
    async def test_mcp_tools_return_structured_output(self, stub_service):
        server = create_mcp_server(service=stub_service)

        await _assert_structured_tool_result(
            server,
            "save_memory",
            {
                "content": "Launch decisions and follow-up notes.",
                "metadata": {"source": "manual", "title": "Launch note"},
                "source_system": "manual",
            },
            {
                "memory_id": "mem-1",
                "result": "created",
                "server_version": 1,
                "entities_count": 1,
                "relationships_count": 0,
                "memory": stub_service.payloads.memory,
            },
        )
        await _assert_structured_tool_result(
            server,
            "append_journal_entry",
            {
                "content": "Today we finalized launch milestones.",
                "title": "Daily note",
                "tags": ["journal"],
            },
            stub_service.payloads.journal_entry,
        )
        await _assert_structured_tool_result(
            server,
            "bulk_save_memories",
            {
                "memories": [
                    {"content": "A"},
                    {"content": "B"},
                ],
                "source_system": "manual",
            },
            stub_service.payloads.bulk_save,
        )
        await _assert_structured_tool_result(
            server,
            "answer_question",
            {
                "question": "launch roadmap",
                "strategy": "hybrid",
                "top_k": 4,
                "include_sources": False,
            },
            _sample_answer_payload("launch roadmap", "hybrid"),
        )
        await _assert_structured_tool_result(
            server,
            "check_duplicate",
            {
                "content": "Launch decisions and follow-up notes.",
                "top_k": 3,
                "min_relevance": 0.8,
            },
            stub_service.payloads.duplicate_check,
        )
        await _assert_structured_tool_result(
            server,
            "preview_memory_layer",
            {
                "layer": "auto",
                "question": "launch roadmap",
                "strategy": "hybrid",
                "top_k": 4,
                "layer_budget_override": 2048,
            },
            stub_service.payloads.preview_layer,
        )
        await _assert_structured_tool_result(
            server,
            "list_sync_sources",
            {},
            stub_service.payloads.sync_sources,
        )
        await _assert_structured_tool_result(
            server,
            "get_sync_source_status",
            {"source_id": "src-1"},
            stub_service.payloads.sync_source_status,
        )
        await _assert_structured_tool_result(
            server,
            "get_runtime_diagnostics",
            {},
            stub_service.payloads.runtime_diagnostics,
        )
        await _assert_structured_tool_result(
            server,
            "archive_memory",
            {"memory_id": "mem-1"},
            {
                "success": True,
                "memory_id": "mem-1",
                "archived": True,
                "archived_at": "2026-04-15T09:00:00+00:00",
                "memory": {**stub_service.payloads.memory, "metadata": {**stub_service.payloads.memory["metadata"], "archived": True}},
            },
        )
        await _assert_structured_tool_result(
            server,
            "unarchive_memory",
            {"memory_id": "mem-1"},
            {
                "success": True,
                "memory_id": "mem-1",
                "archived": False,
                "archived_at": None,
                "memory": {**stub_service.payloads.memory, "metadata": {**stub_service.payloads.memory["metadata"], "archived": False}},
            },
        )
        await _assert_structured_tool_result(
            server,
            "get_memory",
            {"memory_id": "mem-1"},
            stub_service.payloads.memory,
        )
        await _assert_structured_tool_result(
            server,
            "list_memories",
            {"limit": 2, "offset": 1, "status": "archived"},
            stub_service.payloads.list_memories,
        )
        await _assert_structured_tool_result(
            server,
            "get_graph_stats",
            {},
            stub_service.payloads.graph_stats,
        )
        await _assert_structured_tool_result(
            server,
            "list_entities",
            {"limit": 20, "offset": 0},
            stub_service.payloads.entities,
        )
        await _assert_structured_tool_result(
            server,
            "get_entity",
            {"entity_id": "entity-launch"},
            stub_service.payloads.entity,
        )
        await _assert_structured_tool_result(
            server,
            "get_entity_neighbors",
            {"entity_id": "entity-launch", "depth": 2},
            stub_service.payloads.entity_neighbors,
        )
        await _assert_structured_tool_result(
            server,
            "list_communities",
            {"limit": 20, "offset": 0},
            stub_service.payloads.communities,
        )
        await _assert_structured_tool_result(
            server,
            "get_community",
            {"community_id": "comm-1"},
            stub_service.payloads.community,
        )
        await _assert_structured_tool_result(
            server,
            "get_community_entities",
            {"community_id": "comm-1", "limit": 50},
            stub_service.payloads.community_entities,
        )
        await _assert_structured_tool_result(
            server,
            "get_community_relationships",
            {"community_id": "comm-1", "limit": 50},
            stub_service.payloads.community_relationships,
        )
        await _assert_structured_tool_result(
            server,
            "list_query_runs",
            {"limit": 10},
            stub_service.payloads.query_runs,
        )
        await _assert_structured_tool_result(
            server,
            "get_query_run",
            {"run_id": "qrun_1"},
            stub_service.payloads.query_run,
        )
        await _assert_structured_tool_result(
            server,
            "get_entity_timeline",
            {"entity_id": "entity-launch"},
            stub_service.payloads.timeline,
        )
        await _assert_structured_tool_result(
            server,
            "get_entity_state_as_of",
            {"entity_id": "entity-launch", "as_of": "2026-04-15"},
            stub_service.payloads.state_as_of,
        )
        await _assert_structured_tool_result(
            server,
            "get_memory_context",
            {"memory_id": "mem-1"},
            stub_service.payloads.context,
        )
        await _assert_structured_tool_result(
            server,
            "search_memories",
            {
                "query": "launch roadmap",
                "top_k": 3,
                "backend": "graphrag",
                "strategy": "hybrid",
                "include_sources": False,
            },
            _sample_search_payload("launch roadmap", "graphrag", "hybrid"),
        )
        await _assert_structured_tool_result(
            server,
            "delete_memory",
            {"memory_id": "mem-1"},
            {
                "success": True,
                "memory_id": "mem-1",
                "server_version": 2,
                "sync_status": "deleted",
                "deleted": True,
            },
        )

        stub_service.save_memory.assert_awaited_once_with(
            content="Launch decisions and follow-up notes.",
            metadata={"source": "manual", "title": "Launch note"},
            memory_id=None,
            source_system="manual",
        )
        stub_service.append_journal_entry.assert_awaited_once_with(
            content="Today we finalized launch milestones.",
            title="Daily note",
            tags=["journal"],
            metadata=None,
        )
        stub_service.bulk_save_memories.assert_awaited_once_with(
            memories=[{"content": "A"}, {"content": "B"}],
            source_system="manual",
        )
        stub_service.answer_question.assert_awaited_once_with(
            question="launch roadmap",
            strategy="hybrid",
            top_k=4,
            include_sources=False,
            layer="auto",
            layer_budget_override=None,
        )
        stub_service.check_duplicate.assert_awaited_once_with(
            content="Launch decisions and follow-up notes.",
            top_k=3,
            min_relevance=0.8,
            filter_metadata=None,
        )
        stub_service.preview_memory_layer.assert_awaited_once_with(
            layer="auto",
            question="launch roadmap",
            strategy="hybrid",
            top_k=4,
            layer_budget_override=2048,
        )
        stub_service.list_sync_sources.assert_awaited_once_with()
        stub_service.get_sync_source_status.assert_awaited_once_with("src-1")
        stub_service.get_runtime_diagnostics.assert_awaited_once_with()
        stub_service.archive_memory.assert_awaited_once_with("mem-1")
        stub_service.unarchive_memory.assert_awaited_once_with("mem-1")
        stub_service.get_memory.assert_awaited_once_with("mem-1")
        stub_service.list_memories.assert_awaited_once_with(limit=2, offset=1, status="archived")
        stub_service.get_graph_stats.assert_awaited_once_with()
        stub_service.list_entities.assert_awaited_once_with(entity_type=None, limit=20, offset=0)
        stub_service.get_entity.assert_awaited_once_with("entity-launch")
        stub_service.get_entity_neighbors.assert_awaited_once_with("entity-launch", depth=2)
        stub_service.list_communities.assert_awaited_once_with(
            level=None,
            limit=20,
            offset=0,
            require_summary=False,
            include_entity_ids=False,
        )
        stub_service.get_community.assert_awaited_once_with("comm-1", include_entity_ids=True)
        stub_service.get_community_entities.assert_awaited_once_with("comm-1", limit=50)
        stub_service.get_community_relationships.assert_awaited_once_with("comm-1", limit=50)
        stub_service.list_query_runs.assert_awaited_once_with(limit=10)
        stub_service.get_query_run.assert_awaited_once_with("qrun_1")
        stub_service.get_entity_timeline.assert_awaited_once_with("entity-launch")
        stub_service.get_entity_state_as_of.assert_awaited_once_with("entity-launch", as_of="2026-04-15")
        stub_service.get_memory_context.assert_awaited_once_with("mem-1")
        stub_service.search_memories.assert_awaited_once_with(
            query="launch roadmap",
            top_k=3,
            backend="graphrag",
            strategy="hybrid",
            include_sources=False,
            layer="auto",
            layer_budget_override=None,
        )
        stub_service.delete_memory.assert_awaited_once_with("mem-1")

    @pytest.mark.asyncio
    async def test_create_streamable_http_app_returns_server_and_app(self, stub_service):
        config = MCPRuntimeConfig(
            transport="streamable-http",
            streamable_http_path="/memory-graph",
            stateless_http=False,
        )

        server, app = create_streamable_http_app(service=stub_service, config=config)

        assert server is not None
        assert app.__class__.__name__ == "Starlette"
        assert any(getattr(route, "path", None) == "/memory-graph" for route in app.routes)
        assert server.session_manager.stateless is False
        assert server.session_manager.json_response is True

        with patch.object(server.session_manager, "run", wraps=server.session_manager.run) as run_spy:
            async with mcp_session_manager_lifespan(server):
                assert server.session_manager is not None

        run_spy.assert_called_once_with()

    @pytest.mark.parametrize(
        ("config", "transport", "expected_transport", "expected_mount_path"),
        [
            (MCPRuntimeConfig(), None, "stdio", None),
            (
                MCPRuntimeConfig(transport="stdio", mount_path="/memory-graph"),
                "streamable-http",
                "streamable-http",
                "/memory-graph",
            ),
        ],
    )
    def test_run_server_uses_expected_transport(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config: MCPRuntimeConfig,
        transport: str | None,
        expected_transport: str,
        expected_mount_path: str | None,
    ):
        fake_server = MagicMock()
        create_server_mock = MagicMock(return_value=fake_server)
        monkeypatch.setattr(mcp_server_module, "create_mcp_server", create_server_mock)

        returned_server = run_server(config=config, transport=transport)

        assert returned_server is fake_server
        create_server_mock.assert_called_once_with(service=None, config=config)
        fake_server.run.assert_called_once_with(
            transport=expected_transport,
            mount_path=expected_mount_path,
        )

    @pytest.mark.asyncio
    async def test_streamable_http_app_enforces_bearer_auth_when_token_configured(self, stub_service):
        config = MCPRuntimeConfig(
            transport="streamable-http",
            streamable_http_path="/mcp",
            bearer_token="top-secret-token",
        )
        server, app = create_streamable_http_app(service=stub_service, config=config)
        assert server is not None

        async with mcp_session_manager_lifespan(server):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                unauthorized = await client.post("/mcp", json={})
                authorized = await client.post(
                    "/mcp",
                    json={},
                    headers={"Authorization": "Bearer top-secret-token"},
                )

        assert unauthorized.status_code == 401
        assert authorized.status_code != 401
