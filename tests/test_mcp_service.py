"""Focused tests for the Memory Graph MCP service layer."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.graph_store_models import GraphStats
from src.core.temporal_kg import TemporalTriple
from src.core.vector_store_models import MemoryDocument
from src.mcp.service import MemoryGraphMCPService


def _expected_metadata(**overrides):
    payload = {
        "source": None,
        "workspace_id": None,
        "external_id": None,
        "source_path": None,
        "record_type": None,
        "title": None,
        "tags": [],
        "timestamp": None,
        "content_checksum": None,
        "external_revision": None,
        "external_updated_at": None,
        "platform": None,
        "conversation_id": None,
        "archived": None,
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
    }
    payload.update(overrides)
    return payload


def _build_service(*, llm=None, vector_store=None, graph_store=None, retriever_cls=None, graphrag_cls=None):
    return MemoryGraphMCPService(
        llm_manager_getter=lambda: llm if llm is not None else MagicMock(),
        vector_store_getter=lambda: vector_store if vector_store is not None else MagicMock(),
        graph_store_getter=lambda: graph_store if graph_store is not None else MagicMock(),
        retriever_cls=retriever_cls if retriever_cls is not None else MagicMock(),
        graphrag_retriever_cls=graphrag_cls if graphrag_cls is not None else MagicMock(),
    )


@pytest.mark.asyncio
async def test_list_memories_filters_archived_and_sorts_newest_first():
    vector_store = MagicMock()
    vector_store.get_memories = AsyncMock(
        return_value=[
            MemoryDocument(
                id="mem-old",
                content="Old active memory",
                metadata={"source": "manual", "archived": False, "title": "Old"},
            ),
            MemoryDocument(
                id="mem-archived",
                content="Archived memory",
                metadata={"source": "manual", "archived": True, "title": "Archived"},
            ),
            MemoryDocument(
                id="mem-new",
                content="New active memory",
                metadata={"source": "sync", "archived": False, "title": "New"},
            ),
        ]
    )
    graph_store = MagicMock()
    graph_store.get_memory_registry = AsyncMock(
        side_effect=lambda memory_id: {
            "mem-old": {"created_at": "2026-04-01T00:00:00+00:00"},
            "mem-archived": {"created_at": "2026-04-02T00:00:00+00:00"},
            "mem-new": {"created_at": "2026-04-03T00:00:00+00:00"},
        }[memory_id]
    )

    service = _build_service(vector_store=vector_store, graph_store=graph_store)

    active = await service.list_memories(limit=10, offset=0, status="active")
    archived = await service.list_memories(limit=10, offset=0, status="archived")

    assert [item["id"] for item in active["memories"]] == ["mem-new", "mem-old"]
    assert [item["id"] for item in archived["memories"]] == ["mem-archived"]
    assert active["total"] == 2
    assert archived["total"] == 1
    assert active["memories"][0]["provenance"]["type"] == "sync"


@pytest.mark.asyncio
async def test_save_memory_routes_through_memory_service_and_returns_full_payload():
    memory_service = MagicMock()
    memory_service.ingest_memory = AsyncMock(
        return_value=SimpleNamespace(
            memory_id="mem-1",
            result="created",
            server_version=4,
            entities_count=2,
            relationships_count=1,
        )
    )
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(
        return_value=MemoryDocument(
            id="mem-1",
            content="Saved memory",
            metadata={"source": "manual", "title": "Saved note"},
        )
    )
    graph_store = MagicMock()
    graph_store.get_memory_registry = AsyncMock(return_value={"created_at": "2026-04-10T00:00:00+00:00"})

    service = MemoryGraphMCPService(
        memory_service_getter=lambda: memory_service,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
    )
    payload = await service.save_memory(
        content="Saved memory",
        metadata={"source": "manual", "title": "Saved note"},
        memory_id=None,
        source_system="manual",
    )

    assert payload["memory_id"] == "mem-1"
    assert payload["result"] == "created"
    assert payload["server_version"] == 4
    assert payload["memory"]["metadata"]["title"] == "Saved note"
    memory_service.ingest_memory.assert_awaited_once_with(
        content="Saved memory",
        metadata={"source": "manual", "title": "Saved note"},
        memory_id=None,
        source_system="manual",
    )


@pytest.mark.asyncio
async def test_append_journal_entry_sets_journal_defaults():
    memory_service = MagicMock()
    memory_service.ingest_memory = AsyncMock(
        return_value=SimpleNamespace(
            memory_id="mem-journal",
            result="created",
            server_version=2,
            entities_count=0,
            relationships_count=0,
        )
    )
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(
        return_value=MemoryDocument(
            id="mem-journal",
            content="Journal body",
            metadata={"source": "journal", "record_type": "journal_entry", "title": "Daily note"},
        )
    )
    graph_store = MagicMock()
    graph_store.get_memory_registry = AsyncMock(return_value={"created_at": "2026-04-20T00:00:00+00:00"})

    service = MemoryGraphMCPService(
        memory_service_getter=lambda: memory_service,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
    )
    payload = await service.append_journal_entry(
        content="Journal body",
        title="Daily note",
        tags=["journal"],
    )

    assert payload["memory_id"] == "mem-journal"
    metadata = memory_service.ingest_memory.await_args.kwargs["metadata"]
    assert metadata["source"] == "journal"
    assert metadata["record_type"] == "journal_entry"
    assert metadata["title"] == "Daily note"
    assert metadata["tags"] == ["journal"]


@pytest.mark.asyncio
async def test_bulk_save_memories_aggregates_results_without_all_or_nothing():
    service = _build_service()
    service.save_memory = AsyncMock(
        side_effect=[
            {"memory_id": "mem-1", "result": "created"},
            {"memory_id": "mem-2", "result": "updated"},
            {"memory_id": "mem-3", "result": "noop"},
        ]
    )

    payload = await service.bulk_save_memories(
        memories=[
            {"content": "A"},
            {"content": "B"},
            {"content": "C"},
        ],
        source_system="manual",
    )

    assert payload == {
        "results": [
            {"memory_id": "mem-1", "result": "created"},
            {"memory_id": "mem-2", "result": "updated"},
            {"memory_id": "mem-3", "result": "noop"},
        ],
        "summary": {
            "total": 3,
            "created": 1,
            "updated": 1,
            "noop": 1,
            "failed": 0,
        },
    }


@pytest.mark.asyncio
async def test_check_duplicate_returns_matching_memory_payloads():
    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    vector_store = MagicMock()
    vector_store.search = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="mem-1",
                content="Potential duplicate",
                metadata={"source": "manual", "title": "Dup"},
                relevance=0.92,
            )
        ]
    )
    graph_store = MagicMock()
    graph_store.get_memory_registry = AsyncMock(return_value={"created_at": "2026-04-20T00:00:00+00:00"})

    service = MemoryGraphMCPService(
        llm_manager_getter=lambda: llm,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
    )
    payload = await service.check_duplicate(content="Candidate memory", top_k=3, min_relevance=0.8)

    assert payload["total_matches"] == 1
    assert payload["matches"][0]["memory_id"] == "mem-1"
    assert payload["matches"][0]["memory"]["metadata"]["title"] == "Dup"
    vector_store.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_sync_sources_and_get_status_reuse_saved_source_contracts():
    service = _build_service()

    with patch(
        "src.mcp.service.sync_routes_module._load_sync_source_settings",
        return_value=[
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
    ), patch(
        "src.mcp.service.sync_routes_module._serialize_sync_source_setting",
        return_value=SimpleNamespace(model_dump=lambda: {
            "source_id": "src-1",
            "label": "Workspace Notes",
            "source_system": "notes",
            "workspace_id": "workspace-main",
            "workspace_root": "/tmp/workspace-main",
            "source_paths": ["notes/**/*.md"],
            "updated_at": "2026-04-20T00:00:00+00:00",
        }),
    ):
        sources_payload = await service.list_sync_sources()

    assert sources_payload["total"] == 1
    assert sources_payload["sources"][0]["source_id"] == "src-1"

    with patch("src.mcp.service.sync_routes_module._get_sync_source_setting_or_404", return_value={"source_id": "src-1"}), \
         patch("src.mcp.service.sync_routes_module._build_source_worker", return_value=(
            SimpleNamespace(source_system="notes", workspace_id="workspace-main", workspace_root="/tmp/workspace-main", source_paths=["notes/**/*.md"]),
            SimpleNamespace(
                parser=SimpleNamespace(list_source_files=lambda: ["a.md"]),
                get_local_state=lambda: SimpleNamespace(records={}, last_pulled_seq=1, recent_mutation_ids=[]),
            ),
         )), \
         patch("src.mcp.service.get_sync_service", return_value=MagicMock(get_state=AsyncMock(return_value={
            "workspace_id": "workspace-main",
            "active_records": 2,
            "tombstones": 0,
            "conflicts": 0,
            "last_change_seq": 5,
            "last_server_change_at": "2026-04-20T00:00:00+00:00",
         }))), \
         patch("src.mcp.service.sync_routes_module._build_source_status_response", return_value=SimpleNamespace(model_dump=lambda: {"source_id": "src-1", "status": "healthy"})):
        status_payload = await service.get_sync_source_status("src-1")

    assert status_payload == {"source_id": "src-1", "status": "healthy"}


@pytest.mark.asyncio
async def test_get_runtime_diagnostics_reuses_backend_diagnostics_helpers():
    service = _build_service()

    with patch("src.mcp.service.api_main_module._run_config_check", return_value={"ok": True}), \
         patch("src.mcp.service.api_main_module._run_provider_check", new=AsyncMock(return_value={"ok": True})), \
         patch("src.mcp.service.api_main_module._run_sqlite_check", new=AsyncMock(return_value={"ok": True})), \
         patch("src.mcp.service.api_main_module._run_vector_store_check", new=AsyncMock(return_value={"ok": True})), \
         patch("src.mcp.service.api_main_module._run_task_chain_check", return_value={"status": "healthy"}), \
         patch("src.mcp.service.api_main_module._recent_failures_snapshot", return_value=[]), \
         patch("src.mcp.service.api_main_module._now_iso", return_value="2026-04-20T00:00:00+00:00"):
        payload = await service.get_runtime_diagnostics()

    assert payload == {
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


@pytest.mark.asyncio
async def test_delete_archive_and_unarchive_memory_paths():
    memory_service = MagicMock()
    memory_service.delete_memory = AsyncMock(
        return_value=SimpleNamespace(
            memory_id="mem-1",
            deleted=True,
            server_version=5,
            sync_status="deleted",
        )
    )
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(
        side_effect=[
            MemoryDocument(id="mem-1", content="Body", metadata={"source": "manual", "title": "A"}),
            MemoryDocument(id="mem-1", content="Body", metadata={"source": "manual", "title": "A", "archived": True}),
            MemoryDocument(id="mem-1", content="Body", metadata={"source": "manual", "title": "A", "archived": False}),
            MemoryDocument(id="mem-1", content="Body", metadata={"source": "manual", "title": "A", "archived": False}),
        ]
    )
    vector_store.update_memory = AsyncMock(return_value=True)
    graph_store = MagicMock()
    graph_store.get_memory_registry = AsyncMock(return_value={"created_at": "2026-04-10T00:00:00+00:00"})

    service = MemoryGraphMCPService(
        memory_service_getter=lambda: memory_service,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
    )

    deleted = await service.delete_memory("mem-1")
    archived = await service.archive_memory("mem-1")
    unarchived = await service.unarchive_memory("mem-1")

    assert deleted["deleted"] is True
    assert archived["archived"] is True
    assert archived["memory"]["metadata"]["archived"] is True
    assert unarchived["archived"] is False
    assert unarchived["memory"]["metadata"]["archived"] is False
    memory_service.delete_memory.assert_awaited_once_with("mem-1")
    assert vector_store.update_memory.await_count == 2


@pytest.mark.asyncio
async def test_get_memory_context_normalizes_missing_context_lists():
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(
        return_value=MemoryDocument(id="mem-1", content="Memory", metadata={"source": "manual"})
    )
    graph_store = MagicMock()
    graph_store.get_memory_context = AsyncMock(return_value={"entities": ["alice"], "communities": None})

    service = _build_service(vector_store=vector_store, graph_store=graph_store)
    payload = await service.get_memory_context("mem-1")

    assert payload == {
        "memory_id": "mem-1",
        "entities": ["alice"],
        "communities": [],
        "total_entities": 1,
        "total_communities": 0,
    }


@pytest.mark.asyncio
async def test_search_memories_standard_backend_maps_sources_and_provenance():
    llm = MagicMock()
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(
        return_value=MemoryDocument(
            id="mem-1",
            content="Stored memory",
            metadata={
                "source": "manual",
                "record_type": "note",
                "source_path": "notes/mem-1.md",
                "timestamp": "2026-04-02T09:00:00+00:00",
            },
        )
    )
    graph_store = MagicMock()
    graph_store.get_memory_registry = AsyncMock(return_value={"created_at": "2026-04-02T08:00:00+00:00"})

    facade_instance = MagicMock()
    facade_instance.search = AsyncMock(
        return_value=SimpleNamespace(
            sources=[
                SimpleNamespace(
                    memory_id="mem-1",
                    content="Search match",
                    relevance=0.91,
                    entities=["alice"],
                )
            ],
            entities=["alice"],
            processing_time_ms=12,
            layer_requested="auto",
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=21,
            layer_build_duration_ms=4,
            layer_budget_max_tokens=400,
            layer_context_items=[],
        )
    )
    retrieval_facade_cls = MagicMock(return_value=facade_instance)

    service = MemoryGraphMCPService(
        llm_manager_getter=lambda: llm,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
        retrieval_facade_cls=retrieval_facade_cls,
    )
    payload = await service.search_memories(query="alice", backend="standard", strategy="hybrid", top_k=4)

    assert payload == {
        "query": "alice",
        "backend": "standard",
        "strategy": "hybrid",
        "layer_requested": "auto",
        "layer_used": "l2",
        "layer_fallback_chain": ["l2"],
        "context_token_estimate": 21,
        "layer_build_duration_ms": 4,
        "processing_time_ms": 12,
        "total_sources": 1,
        "total_communities": 0,
        "entities": ["alice"],
        "query_entities": [],
        "sources": [
            {
                "memory_id": "mem-1",
                "content": "Search match",
                "relevance": 0.91,
                "entities": ["alice"],
                "metadata": {
                    **_expected_metadata(
                        source="manual",
                        source_path="notes/mem-1.md",
                        record_type="note",
                        timestamp="2026-04-02T09:00:00+00:00",
                    ),
                },
                "provenance": {
                    "type": "note",
                    "time": "2026-04-02T09:00:00+00:00",
                    "imported_from": "notes/mem-1.md",
                },
                "community_id": None,
                "community_summary": None,
            }
        ],
        "communities": [],
    }
    facade_instance.search.assert_awaited_once_with(
        "alice",
        strategy="hybrid",
        top_k=4,
        include_sources=True,
        layer="auto",
        layer_budget_override=None,
    )


@pytest.mark.asyncio
async def test_search_memories_graphrag_backend_maps_query_entities_and_communities():
    llm = MagicMock()
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(return_value=None)
    graph_store = MagicMock()

    facade_instance = MagicMock()
    facade_instance.search = AsyncMock(
        return_value=SimpleNamespace(
            sources=[
                SimpleNamespace(
                    memory_id=None,
                    content="Community source",
                    relevance=0.83,
                    entities=["launch"],
                    community_id="comm-1",
                    community_summary="Launch cluster",
                    metadata={"source": "community"},
                )
            ],
            entities=["launch"],
            query_entities=["launch"],
            communities=[
                SimpleNamespace(
                    community_id="comm-1",
                    title="Launch Cluster",
                    summary="Launch cluster",
                    level=1,
                    entities=["entity-1"],
                    relationships=[{"source": "entity-1", "target": "entity-2"}],
                    relevance=0.92,
                )
            ],
            processing_time_ms=21,
            layer_requested="auto",
            layer_used="l3",
            layer_fallback_chain=["l3"],
            context_token_estimate=27,
            layer_build_duration_ms=5,
            layer_budget_max_tokens=1200,
            layer_context_items=[],
        )
    )
    retrieval_facade_cls = MagicMock(return_value=facade_instance)

    service = MemoryGraphMCPService(
        llm_manager_getter=lambda: llm,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
        retrieval_facade_cls=retrieval_facade_cls,
    )
    payload = await service.search_memories(query="launch", backend="graphrag", strategy="global", top_k=3)

    assert payload["backend"] == "graphrag"
    assert payload["strategy"] == "global"
    assert payload["layer_requested"] == "auto"
    assert payload["layer_used"] == "l3"
    assert payload["layer_fallback_chain"] == ["l3"]
    assert payload["context_token_estimate"] == 27
    assert payload["query_entities"] == ["launch"]
    assert payload["total_communities"] == 1
    assert payload["sources"][0]["community_id"] == "comm-1"
    assert payload["communities"][0]["title"] == "Launch Cluster"
    facade_instance.search.assert_awaited_once_with(
        "launch",
        strategy="global",
        top_k=3,
        include_sources=True,
        layer="auto",
        layer_budget_override=None,
    )


@pytest.mark.asyncio
async def test_answer_question_uses_unified_retrieval_facade():
    llm = MagicMock()
    vector_store = MagicMock()
    graph_store = MagicMock()

    facade_instance = MagicMock()
    facade_instance.answer = AsyncMock(
        return_value=SimpleNamespace(
            answer="Launch is owned by Alice.",
            sources=[
                SimpleNamespace(
                    memory_id=None,
                    content="Community evidence",
                    relevance=0.88,
                    entities=["alice"],
                    community_id="comm-1",
                    community_summary="Launch cluster",
                    metadata={"source": "community"},
                )
            ],
            entities=["alice"],
            query_entities=["alice"],
            communities=[
                SimpleNamespace(
                    community_id="comm-1",
                    title="Launch Cluster",
                    summary="Launch cluster",
                    level=1,
                    entities=["alice"],
                    relationships=[],
                    relevance=0.91,
                )
            ],
            processing_time_ms=16,
            layer_requested="auto",
            layer_used="l3",
            layer_fallback_chain=["l3"],
            context_token_estimate=33,
            layer_build_duration_ms=7,
            layer_budget_max_tokens=1200,
            layer_context_items=[],
        )
    )
    retrieval_facade_cls = MagicMock(return_value=facade_instance)

    service = MemoryGraphMCPService(
        llm_manager_getter=lambda: llm,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
        retrieval_facade_cls=retrieval_facade_cls,
    )
    payload = await service.answer_question(question="Who owns launch?", strategy="global", top_k=4)

    assert payload["answer"] == "Launch is owned by Alice."
    assert payload["strategy"] == "global"
    assert payload["layer_requested"] == "auto"
    assert payload["layer_used"] == "l3"
    assert payload["layer_fallback_chain"] == ["l3"]
    assert payload["context_token_estimate"] == 33
    assert payload["query_entities"] == ["alice"]
    assert payload["total_communities"] == 1
    retrieval_facade_cls.assert_called_once_with(llm, vector_store, graph_store)
    facade_instance.answer.assert_awaited_once_with(
        "Who owns launch?",
        strategy="global",
        top_k=4,
        include_sources=True,
        layer="auto",
        layer_budget_override=None,
    )


@pytest.mark.asyncio
async def test_entity_and_community_helpers_serialize_graph_records():
    graph_store = MagicMock()
    graph_store.count_entities = AsyncMock(return_value=1)
    graph_store.query_entities = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="entity-1",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text="Alice owns launch.",
                confidence=0.93,
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            )
        ]
    )
    graph_store.get_entity = AsyncMock(
        return_value=SimpleNamespace(
            id="entity-1",
            name="Alice",
            type="person",
            properties={"role": "owner"},
            source_text="Alice owns launch.",
            confidence=0.93,
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    graph_store.get_entity_communities = AsyncMock(return_value=["comm-1"])
    graph_store.get_neighbors = AsyncMock(return_value=[{"id": "entity-2", "name": "Launch", "distance": 1}])
    graph_store.list_communities = AsyncMock(
        return_value=[
            {
                "id": "comm-1",
                "level": 1,
                "title": "Launch Cluster",
                "summary": "Launch summary",
                "entity_count": 1,
                "rank": 0.8,
            }
        ]
    )
    graph_store.get_community = AsyncMock(
        return_value={
            "id": "comm-1",
            "level": 1,
            "title": "Launch Cluster",
            "summary": "Launch summary",
            "entity_count": 1,
            "rank": 0.8,
            "entity_ids": ["entity-1"],
        }
    )
    graph_store.get_community_entities = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="entity-1",
                name="Alice",
                type="person",
                properties={},
                source_text="",
                confidence=1.0,
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            )
        ]
    )
    graph_store.get_community_relationships = AsyncMock(
        return_value=[{"id": "rel-1", "source": "Alice", "target": "Launch", "type": "owns"}]
    )

    service = _build_service(graph_store=graph_store)

    entities = await service.list_entities(limit=5, offset=0)
    entity = await service.get_entity("entity-1")
    neighbors = await service.get_entity_neighbors("entity-1", depth=2)
    communities = await service.list_communities(limit=5, offset=0, include_entity_ids=True)
    community = await service.get_community("comm-1")
    community_entities = await service.get_community_entities("comm-1", limit=10)
    community_relationships = await service.get_community_relationships("comm-1", limit=10)

    assert entities["total"] == 1
    assert entities["entities"][0]["name"] == "Alice"
    assert entity["community_ids"] == ["comm-1"]
    assert neighbors["total"] == 1
    assert communities["communities"][0]["title"] == "Launch Cluster"
    assert community["entity_ids"] == ["entity-1"]
    assert community_entities["total"] == 1
    assert community_relationships["relationships"][0]["type"] == "owns"


@pytest.mark.asyncio
async def test_query_trace_and_temporal_helpers_return_serialized_payloads():
    trace_store = MagicMock()
    trace_store.list_recent = MagicMock(
        return_value=[SimpleNamespace(to_dict=lambda: {"run_id": "run-1", "status": "succeeded"})]
    )
    trace_store.get = MagicMock(return_value=SimpleNamespace(to_dict=lambda: {"run_id": "run-1", "status": "succeeded"}))

    temporal_kg = MagicMock()
    temporal_kg.get_entity_timeline = AsyncMock(
        return_value=[
            TemporalTriple(
                id="triple-1",
                entity_id="entity-1",
                relation_type="owns",
                target_entity_id="entity-2",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_to=None,
                confidence=0.9,
                source="manual",
                created_at="2026-04-01T00:00:00+00:00",
                metadata={},
            )
        ]
    )
    temporal_kg.get_entity_state_as_of = AsyncMock(
        return_value=[
            TemporalTriple(
                id="triple-1",
                entity_id="entity-1",
                relation_type="owns",
                target_entity_id="entity-2",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_to=None,
                confidence=0.9,
                source="manual",
                created_at="2026-04-01T00:00:00+00:00",
                metadata={},
            )
        ]
    )

    service = MemoryGraphMCPService(
        query_trace_store_getter=lambda: trace_store,
        temporal_kg_getter=lambda: temporal_kg,
    )

    runs = await service.list_query_runs(limit=5)
    run = await service.get_query_run("run-1")
    timeline = await service.get_entity_timeline("entity-1")
    state = await service.get_entity_state_as_of("entity-1", as_of="2026-04-15")

    assert runs == {"runs": [{"run_id": "run-1", "status": "succeeded"}], "total": 1, "limit": 5}
    assert run == {"run_id": "run-1", "status": "succeeded"}
    assert timeline["entity_id"] == "entity-1"
    assert timeline["total"] == 1
    assert state["as_of"] == "2026-04-15"
    trace_store.list_recent.assert_called_once_with(limit=5)
    trace_store.get.assert_called_once_with("run-1")


@pytest.mark.asyncio
async def test_stats_resource_payload_combines_graph_and_vector_state():
    vector_store = MagicMock()
    vector_store.get_index_state = AsyncMock(return_value={"dimension": 1024, "documents": 3})
    graph_store = MagicMock()
    graph_store.get_stats = AsyncMock(
        return_value=GraphStats(
            total_entities=2,
            total_relationships=1,
            entity_types={"person": 2},
            total_memories=3,
        )
    )

    service = _build_service(vector_store=vector_store, graph_store=graph_store)
    payload = await service.get_stats_resource_payload()

    assert payload == {
        "graph": {
            "total_entities": 2,
            "total_relationships": 1,
            "entity_types": {"person": 2},
            "total_memories": 3,
        },
        "vector_index": {"dimension": 1024, "documents": 3},
    }


@pytest.mark.asyncio
async def test_invalid_search_inputs_raise_value_error():
    service = _build_service()

    with pytest.raises(ValueError, match="Invalid status filter"):
        await service.list_memories(status="broken")

    with pytest.raises(ValueError, match="Invalid standard strategy"):
        await service.search_memories(query="x", backend="standard", strategy="broken")

    with pytest.raises(ValueError, match="Invalid GraphRAG strategy"):
        await service.search_memories(query="x", backend="graphrag", strategy="broken")


@pytest.mark.asyncio
async def test_preview_memory_layer_uses_facade_and_returns_contract_payload():
    llm = MagicMock()
    vector_store = MagicMock()
    graph_store = MagicMock()

    facade_instance = MagicMock()
    facade_instance.search = AsyncMock(
        return_value=SimpleNamespace(
            layer_used="l3",
            layer_fallback_chain=["l2", "l3"],
            context_token_estimate=88,
            layer_build_duration_ms=9,
            layer_warnings=["fallback"],
            layer_budget_max_tokens=2048,
            layer_context_items=[{"item_type": "source", "identifier": "mem-1"}],
        )
    )
    retrieval_facade_cls = MagicMock(return_value=facade_instance)

    service = MemoryGraphMCPService(
        llm_manager_getter=lambda: llm,
        vector_store_getter=lambda: vector_store,
        graph_store_getter=lambda: graph_store,
        retrieval_facade_cls=retrieval_facade_cls,
    )
    payload = await service.preview_memory_layer(
        layer="auto",
        question="preview this",
        strategy="hybrid",
        top_k=4,
        layer_budget_override=2048,
    )

    assert payload == {
        "requested_layer": "auto",
        "resolved_layer": "l3",
        "fallback_chain": ["l2", "l3"],
        "token_budget": 2048,
        "token_estimate": 88,
        "layer_build_duration_ms": 9,
        "warnings": ["fallback"],
        "context_items": [{"item_type": "source", "identifier": "mem-1"}],
        "question": "preview this",
        "strategy": "hybrid",
        "top_k": 4,
    }
    facade_instance.search.assert_awaited_once_with(
        "preview this",
        strategy="hybrid",
        top_k=4,
        include_sources=True,
        layer="auto",
        layer_budget_override=2048,
    )


@pytest.mark.asyncio
async def test_get_memory_raises_lookup_error_for_missing_id():
    vector_store = MagicMock()
    vector_store.get_memory = AsyncMock(return_value=None)

    service = _build_service(vector_store=vector_store)

    with pytest.raises(LookupError, match="Memory not found: missing"):
        await service.get_memory("missing")
