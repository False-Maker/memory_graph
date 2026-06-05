"""Service layer for the Memory Graph MCP server."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Callable, Literal

from src.api import main as api_main_module
from src.api.routes import sync as sync_routes_module
from src.core.graph_store import get_graph_store
from src.core.graphrag_retriever import GraphRAGRetriever
from src.core.llm_manager import get_llm_manager
from src.core.memory_layers import MemoryLayerContextItem
from src.core.memory_contract import metadata_contract_view, resolve_memory_summary
from src.core.memory_service import get_memory_service
from src.core.query_trace import get_query_trace_store
from src.core.retrieval_facade import RetrievalFacade
from src.core.retriever import Retriever
from src.core.sync.service import get_sync_service
from src.core.temporal_kg import get_temporal_kg
from src.core.vector_store import get_vector_store


JSONDict = dict[str, Any]
SearchBackend = Literal["standard", "graphrag"]
MemoryLayerName = Literal["auto", "l0", "l1", "l2", "l3"]

ARCHIVE_STATUS_VALUES = {"active", "archived", "all"}
STANDARD_SEARCH_STRATEGIES = {"vector", "graph", "hybrid"}
GRAPHRAG_SEARCH_STRATEGIES = {"local", "global", "hybrid"}
MEMORY_METADATA_FIELDS = (
    "source",
    "workspace_id",
    "external_id",
    "source_path",
    "record_type",
    "title",
    "tags",
    "timestamp",
    "content_checksum",
    "external_revision",
    "external_updated_at",
    "platform",
    "conversation_id",
    "archived",
    "archived_at",
)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _serialize_value(asdict(value))
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _normalize_memory_metadata(raw_metadata: Any) -> JSONDict:
    return _serialize_value(metadata_contract_view(raw_metadata))


def _build_provenance_payload(metadata: JSONDict, created_at: datetime) -> JSONDict:
    source_time = metadata.get("timestamp") or metadata.get("external_updated_at") or created_at.isoformat()
    return {
        "type": _first_non_empty(metadata.get("record_type"), metadata.get("source")),
        "time": source_time,
        "imported_from": _first_non_empty(
            metadata.get("source_path"),
            metadata.get("external_id"),
            metadata.get("workspace_id"),
        ),
    }


def _resolve_created_at(raw_created_at: Any) -> datetime:
    if isinstance(raw_created_at, datetime):
        return raw_created_at
    if isinstance(raw_created_at, str) and raw_created_at:
        return datetime.fromisoformat(raw_created_at)
    return datetime.now()


def _normalize_archive_status(value: str) -> str:
    normalized = (value or "active").strip().lower()
    if normalized not in ARCHIVE_STATUS_VALUES:
        supported = ", ".join(sorted(ARCHIVE_STATUS_VALUES))
        raise ValueError(f"Invalid status filter: {value}. Supported values: {supported}")
    return normalized


def _is_memory_archived(metadata: Any) -> bool:
    return isinstance(metadata, dict) and metadata.get("archived") is True


def _normalize_memory_context(context: Any) -> JSONDict:
    if not isinstance(context, dict):
        return {"entities": [], "communities": []}

    entities = context.get("entities")
    communities = context.get("communities")
    return {
        "entities": _serialize_value(entities if isinstance(entities, list) else []),
        "communities": _serialize_value(communities if isinstance(communities, list) else []),
    }


def _memory_sort_key(created_at: datetime, memory_id: str) -> tuple[float, str]:
    return (created_at.timestamp(), memory_id)


def _format_json_resource(payload: JSONDict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


class MemoryGraphMCPService:
    """Read-only service facade used by the MCP server."""

    def __init__(
        self,
        *,
        llm_manager_getter: Callable[[], Any] = get_llm_manager,
        vector_store_getter: Callable[[], Any] = get_vector_store,
        graph_store_getter: Callable[[], Any] = get_graph_store,
        memory_service_getter: Callable[[], Any] = get_memory_service,
        query_trace_store_getter: Callable[[], Any] = get_query_trace_store,
        temporal_kg_getter: Callable[[], Any] = get_temporal_kg,
        retriever_cls: type[Retriever] = Retriever,
        graphrag_retriever_cls: type[GraphRAGRetriever] = GraphRAGRetriever,
        retrieval_facade_cls: type[RetrievalFacade] = RetrievalFacade,
    ) -> None:
        self._get_llm_manager = llm_manager_getter
        self._get_vector_store = vector_store_getter
        self._get_graph_store = graph_store_getter
        self._get_memory_service = memory_service_getter
        self._get_query_trace_store = query_trace_store_getter
        self._get_temporal_kg = temporal_kg_getter
        self._retriever_cls = retriever_cls
        self._graphrag_retriever_cls = graphrag_retriever_cls
        self._retrieval_facade_cls = retrieval_facade_cls

    @staticmethod
    def _serialize_graph_entity(entity: Any) -> JSONDict:
        return {
            "id": getattr(entity, "id", None),
            "name": getattr(entity, "name", ""),
            "type": getattr(entity, "type", ""),
            "properties": _serialize_value(getattr(entity, "properties", {}) or {}),
            "source_text": getattr(entity, "source_text", ""),
            "confidence": getattr(entity, "confidence", 1.0),
            "created_at": _serialize_value(getattr(entity, "created_at", None)),
        }

    @staticmethod
    def _serialize_community_record(community: Any) -> JSONDict:
        if isinstance(community, dict):
            return _serialize_value(dict(community))
        if hasattr(community, "__dict__"):
            return _serialize_value(vars(community))
        return {"value": _serialize_value(community)}

    @staticmethod
    def _serialize_query_run(trace: Any) -> JSONDict:
        if hasattr(trace, "to_dict"):
            return _serialize_value(trace.to_dict())
        if hasattr(trace, "__dict__"):
            return _serialize_value(vars(trace))
        return {"value": _serialize_value(trace)}

    @staticmethod
    def _serialize_temporal_triple(triple: Any) -> JSONDict:
        if hasattr(triple, "__dataclass_fields__"):
            return _serialize_value(asdict(triple))
        if hasattr(triple, "__dict__"):
            return _serialize_value(vars(triple))
        return {"value": _serialize_value(triple)}

    async def _load_source_metadata(
        self,
        *,
        vector_store: Any,
        source: Any,
        metadata_cache: dict[str, JSONDict],
    ) -> JSONDict:
        memory_id = getattr(source, "memory_id", None)
        source_metadata = getattr(source, "metadata", None)
        normalized_source_metadata = _normalize_memory_metadata(source_metadata)

        if not isinstance(memory_id, str) or not memory_id:
            return normalized_source_metadata

        if memory_id not in metadata_cache:
            document = await vector_store.get_memory(memory_id)
            metadata_cache[memory_id] = _normalize_memory_metadata(
                getattr(document, "metadata", None) if document is not None else {}
            )

        hydrated = dict(metadata_cache[memory_id])
        for field_name, value in normalized_source_metadata.items():
            if value not in (None, [], ""):
                hydrated[field_name] = value
        return hydrated

    async def _build_memory_payload(self, memory: Any, *, graph_store: Any) -> JSONDict:
        registry = await graph_store.get_memory_registry(memory.id)
        created_at = _resolve_created_at(registry.get("created_at") if isinstance(registry, dict) else None)
        metadata = _normalize_memory_metadata(getattr(memory, "metadata", None))
        return {
            "id": memory.id,
            "content": getattr(memory, "content", ""),
            "summary": resolve_memory_summary(metadata),
            "metadata": metadata,
            "provenance": _build_provenance_payload(metadata, created_at),
            "created_at": created_at.isoformat(),
        }

    async def _require_memory_payload(self, memory_id: str) -> JSONDict:
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        memory = await vector_store.get_memory(memory_id)
        if memory is None:
            raise LookupError(f"Memory not found: {memory_id}")
        return await self._build_memory_payload(memory, graph_store=graph_store)

    @staticmethod
    def _normalize_metadata_input(metadata: Any) -> JSONDict:
        if isinstance(metadata, dict):
            return dict(metadata)
        return {}

    @staticmethod
    def _build_archive_metadata(memory: Any, archived: bool) -> JSONDict:
        metadata = dict(getattr(memory, "metadata", None) or {})
        if archived:
            metadata["archived"] = True
            metadata["archived_at"] = datetime.now().isoformat()
        else:
            metadata["archived"] = False
            metadata.pop("archived_at", None)
        return metadata

    async def _build_search_source_payload(
        self,
        *,
        vector_store: Any,
        graph_store: Any,
        source: Any,
        metadata_cache: dict[str, JSONDict],
        created_at_cache: dict[str, datetime],
    ) -> JSONDict:
        memory_id = getattr(source, "memory_id", None)
        metadata = await self._load_source_metadata(
            vector_store=vector_store,
            source=source,
            metadata_cache=metadata_cache,
        )
        created_at = datetime.now()
        if isinstance(memory_id, str) and memory_id:
            if memory_id not in created_at_cache:
                registry = await graph_store.get_memory_registry(memory_id)
                created_at_cache[memory_id] = _resolve_created_at(
                    registry.get("created_at") if isinstance(registry, dict) else None
                )
            created_at = created_at_cache[memory_id]
        return {
            "memory_id": memory_id,
            "content": getattr(source, "content", ""),
            "relevance": getattr(source, "relevance", 0.0),
            "entities": list(getattr(source, "entities", []) or []),
            "metadata": metadata,
            "provenance": _build_provenance_payload(metadata, created_at),
            "community_id": getattr(source, "community_id", None),
            "community_summary": getattr(source, "community_summary", None),
        }

    async def list_memories(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str = "active",
    ) -> JSONDict:
        normalized_status = _normalize_archive_status(status)
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        all_memories = await vector_store.get_memories(limit=None, offset=0)

        filtered_memories = [
            memory
            for memory in all_memories
            if normalized_status == "all"
            or _is_memory_archived(getattr(memory, "metadata", None)) is (normalized_status == "archived")
        ]

        decorated: list[tuple[datetime, str, JSONDict]] = []
        for memory in filtered_memories:
            payload = await self._build_memory_payload(memory, graph_store=graph_store)
            created_at = _resolve_created_at(payload["created_at"])
            decorated.append((created_at, memory.id, payload))

        decorated.sort(key=lambda item: _memory_sort_key(item[0], item[1]), reverse=True)
        sliced = [item[2] for item in decorated[offset : offset + limit]]
        return {
            "memories": sliced,
            "total": len(decorated),
            "limit": limit,
            "offset": offset,
        }

    async def get_memory(self, memory_id: str) -> JSONDict:
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        memory = await vector_store.get_memory(memory_id)
        if memory is None:
            raise LookupError(f"Memory not found: {memory_id}")
        return await self._build_memory_payload(memory, graph_store=graph_store)

    async def get_memory_context(self, memory_id: str) -> JSONDict:
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        memory = await vector_store.get_memory(memory_id)
        if memory is None:
            raise LookupError(f"Memory not found: {memory_id}")

        context = _normalize_memory_context(await graph_store.get_memory_context(memory_id))
        return {
            "memory_id": memory_id,
            "entities": context["entities"],
            "communities": context["communities"],
            "total_entities": len(context["entities"]),
            "total_communities": len(context["communities"]),
        }

    async def get_graph_stats(self) -> JSONDict:
        graph_store = self._get_graph_store()
        stats = await graph_store.get_stats()
        return {
            "total_entities": getattr(stats, "total_entities", 0),
            "total_relationships": getattr(stats, "total_relationships", 0),
            "entity_types": _serialize_value(getattr(stats, "entity_types", {})),
            "total_memories": getattr(stats, "total_memories", 0),
        }

    async def save_memory(
        self,
        *,
        content: str,
        metadata: JSONDict | None = None,
        memory_id: str | None = None,
        source_system: str = "manual",
    ) -> JSONDict:
        service = self._get_memory_service()
        normalized_metadata = self._normalize_metadata_input(metadata)
        result = await service.ingest_memory(
            content=content,
            metadata=normalized_metadata,
            memory_id=memory_id,
            source_system=source_system,
        )
        return {
            "memory_id": result.memory_id,
            "result": result.result,
            "server_version": result.server_version,
            "entities_count": result.entities_count,
            "relationships_count": result.relationships_count,
            "memory": await self._require_memory_payload(result.memory_id),
        }

    async def append_journal_entry(
        self,
        *,
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
        metadata: JSONDict | None = None,
    ) -> JSONDict:
        normalized_metadata = self._normalize_metadata_input(metadata)
        normalized_metadata.setdefault("source", "journal")
        normalized_metadata.setdefault("record_type", "journal_entry")
        normalized_metadata.setdefault("title", title or "Journal Entry")
        normalized_metadata.setdefault("tags", list(tags or []))
        normalized_metadata.setdefault("timestamp", datetime.now().isoformat())
        return await self.save_memory(
            content=content,
            metadata=normalized_metadata,
            source_system="journal",
        )

    async def bulk_save_memories(
        self,
        *,
        memories: list[JSONDict],
        source_system: str = "manual",
    ) -> JSONDict:
        results: list[JSONDict] = []
        created = 0
        updated = 0
        noop = 0
        failed = 0

        for entry in list(memories or []):
            content = str(entry.get("content") or "")
            if not content.strip():
                failed += 1
                results.append(
                    {
                        "result": "rejected",
                        "detail": "content is required",
                        "memory_id": None,
                    }
                )
                continue

            metadata = self._normalize_metadata_input(entry.get("metadata"))
            memory_id = entry.get("memory_id") if isinstance(entry.get("memory_id"), str) else None
            try:
                payload = await self.save_memory(
                    content=content,
                    metadata=metadata,
                    memory_id=memory_id,
                    source_system=str(entry.get("source_system") or source_system),
                )
                outcome = str(payload.get("result") or "")
                if outcome == "created":
                    created += 1
                elif outcome == "updated":
                    updated += 1
                elif outcome == "noop":
                    noop += 1
                results.append(payload)
            except Exception as exc:
                failed += 1
                results.append(
                    {
                        "result": "rejected",
                        "detail": str(exc),
                        "memory_id": memory_id,
                    }
                )

        return {
            "results": results,
            "summary": {
                "total": len(list(memories or [])),
                "created": created,
                "updated": updated,
                "noop": noop,
                "failed": failed,
            },
        }

    async def delete_memory(self, memory_id: str) -> JSONDict:
        service = self._get_memory_service()
        result = await service.delete_memory(memory_id)
        if not result.deleted and result.sync_status == "not_found":
            raise LookupError(f"Memory not found: {memory_id}")
        return {
            "success": True,
            "memory_id": result.memory_id,
            "server_version": result.server_version,
            "sync_status": result.sync_status,
            "deleted": result.deleted,
        }

    async def check_duplicate(
        self,
        *,
        content: str,
        top_k: int = 5,
        min_relevance: float = 0.8,
        filter_metadata: JSONDict | None = None,
    ) -> JSONDict:
        llm = self._get_llm_manager()
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()

        embeddings = await llm.embed([content])
        matches = await vector_store.search(
            query_embedding=embeddings[0],
            top_k=top_k,
            filter_metadata=self._normalize_metadata_input(filter_metadata) or None,
        )
        filtered_matches = [
            match
            for match in matches
            if float(getattr(match, "relevance", 0.0) or 0.0) >= float(min_relevance)
        ]
        payloads = []
        for match in filtered_matches:
            memory_payload = await self._build_memory_payload(match, graph_store=graph_store)
            payloads.append(
                {
                    "memory_id": getattr(match, "id", None),
                    "relevance": getattr(match, "relevance", 0.0),
                    "memory": memory_payload,
                }
            )

        return {
            "content_preview": content[:160],
            "top_k": top_k,
            "min_relevance": min_relevance,
            "total_matches": len(payloads),
            "matches": payloads,
        }

    async def archive_memory(self, memory_id: str) -> JSONDict:
        vector_store = self._get_vector_store()
        memory = await vector_store.get_memory(memory_id)
        if memory is None:
            raise LookupError(f"Memory not found: {memory_id}")
        metadata = self._build_archive_metadata(memory, archived=True)
        await vector_store.update_memory(memory_id=memory_id, metadata=metadata)
        return {
            "success": True,
            "memory_id": memory_id,
            "archived": True,
            "archived_at": metadata.get("archived_at"),
            "memory": await self._require_memory_payload(memory_id),
        }

    async def unarchive_memory(self, memory_id: str) -> JSONDict:
        vector_store = self._get_vector_store()
        memory = await vector_store.get_memory(memory_id)
        if memory is None:
            raise LookupError(f"Memory not found: {memory_id}")
        metadata = self._build_archive_metadata(memory, archived=False)
        await vector_store.update_memory(memory_id=memory_id, metadata=metadata)
        return {
            "success": True,
            "memory_id": memory_id,
            "archived": False,
            "archived_at": None,
            "memory": await self._require_memory_payload(memory_id),
        }

    async def list_entities(
        self,
        *,
        entity_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> JSONDict:
        graph_store = self._get_graph_store()
        entity_types = [entity_type] if entity_type else None
        entities = await graph_store.query_entities(entity_types=entity_types, limit=limit, offset=offset)
        total = await graph_store.count_entities(entity_types=entity_types)
        return {
            "entities": [self._serialize_graph_entity(entity) for entity in entities],
            "total": total,
            "limit": limit,
            "offset": offset,
            "entity_type": entity_type,
        }

    async def get_entity(self, entity_id: str) -> JSONDict:
        graph_store = self._get_graph_store()
        entity = await graph_store.get_entity(entity_id)
        if entity is None:
            raise LookupError(f"Entity not found: {entity_id}")
        community_ids = await graph_store.get_entity_communities(entity_id)
        return {
            **self._serialize_graph_entity(entity),
            "community_ids": community_ids,
        }

    async def get_entity_neighbors(self, entity_id: str, *, depth: int = 1) -> JSONDict:
        graph_store = self._get_graph_store()
        entity = await graph_store.get_entity(entity_id)
        if entity is None:
            raise LookupError(f"Entity not found: {entity_id}")
        neighbors = await graph_store.get_neighbors(entity_id, depth=depth)
        return {
            "entity_id": entity_id,
            "depth": depth,
            "total": len(neighbors),
            "neighbors": _serialize_value(neighbors),
        }

    async def list_communities(
        self,
        *,
        level: int | None = None,
        limit: int = 20,
        offset: int = 0,
        require_summary: bool = False,
        include_entity_ids: bool = False,
        order_by: str = "rank_desc",
    ) -> JSONDict:
        graph_store = self._get_graph_store()
        communities = await graph_store.list_communities(
            level=level,
            limit=limit,
            offset=offset,
            require_summary=require_summary,
            include_entity_ids=include_entity_ids,
            order_by=order_by,
        )
        return {
            "communities": [self._serialize_community_record(community) for community in communities],
            "total": len(communities),
            "limit": limit,
            "offset": offset,
            "level": level,
            "require_summary": require_summary,
        }

    async def get_community(self, community_id: str, *, include_entity_ids: bool = True) -> JSONDict:
        graph_store = self._get_graph_store()
        community = await graph_store.get_community(community_id, include_entity_ids=include_entity_ids)
        if community is None:
            raise LookupError(f"Community not found: {community_id}")
        return self._serialize_community_record(community)

    async def get_community_entities(self, community_id: str, *, limit: int = 50) -> JSONDict:
        graph_store = self._get_graph_store()
        community = await graph_store.get_community(community_id, include_entity_ids=False)
        if community is None:
            raise LookupError(f"Community not found: {community_id}")
        entities = await graph_store.get_community_entities(community_id, limit=limit)
        return {
            "community_id": community_id,
            "total": len(entities),
            "entities": [self._serialize_graph_entity(entity) for entity in entities],
        }

    async def get_community_relationships(self, community_id: str, *, limit: int = 50) -> JSONDict:
        graph_store = self._get_graph_store()
        community = await graph_store.get_community(community_id, include_entity_ids=False)
        if community is None:
            raise LookupError(f"Community not found: {community_id}")
        relationships = await graph_store.get_community_relationships(community_id, limit=limit)
        return {
            "community_id": community_id,
            "total": len(relationships),
            "relationships": _serialize_value(relationships),
        }

    async def answer_question(
        self,
        *,
        question: str,
        strategy: str = "graphrag",
        top_k: int = 5,
        include_sources: bool = True,
        layer: MemoryLayerName = "auto",
        layer_budget_override: int | None = None,
    ) -> JSONDict:
        llm = self._get_llm_manager()
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        metadata_cache: dict[str, JSONDict] = {}
        created_at_cache: dict[str, datetime] = {}
        facade = self._retrieval_facade_cls(llm, vector_store, graph_store)
        result = await facade.answer(
            question,
            strategy=strategy,
            top_k=top_k,
            include_sources=include_sources,
            layer=layer,
            layer_budget_override=layer_budget_override,
        )
        sources = [
            await self._build_search_source_payload(
                vector_store=vector_store,
                graph_store=graph_store,
                source=source,
                metadata_cache=metadata_cache,
                created_at_cache=created_at_cache,
            )
            for source in result.sources
        ]
        communities = [
            {
                "community_id": getattr(community, "community_id", None),
                "title": getattr(community, "title", None),
                "summary": getattr(community, "summary", None),
                "level": getattr(community, "level", None),
                "entities": list(getattr(community, "entities", []) or []),
                "relationships": _serialize_value(getattr(community, "relationships", []) or []),
                "relevance": getattr(community, "relevance", 0.0),
            }
            for community in list(getattr(result, "communities", []) or [])
        ]
        return {
            "question": question,
            "strategy": strategy,
            "layer_requested": getattr(result, "layer_requested", layer),
            "layer_used": getattr(result, "layer_used", None),
            "layer_fallback_chain": list(getattr(result, "layer_fallback_chain", []) or []),
            "context_token_estimate": int(getattr(result, "context_token_estimate", 0) or 0),
            "layer_build_duration_ms": int(getattr(result, "layer_build_duration_ms", 0) or 0),
            "answer": getattr(result, "answer", ""),
            "processing_time_ms": getattr(result, "processing_time_ms", 0),
            "total_sources": len(sources),
            "total_communities": len(communities),
            "entities": list(getattr(result, "entities", []) or []),
            "query_entities": list(getattr(result, "query_entities", []) or []),
            "sources": sources,
            "communities": communities,
        }

    async def list_query_runs(self, *, limit: int = 10) -> JSONDict:
        trace_store = self._get_query_trace_store()
        runs = trace_store.list_recent(limit=limit)
        return {
            "runs": [self._serialize_query_run(run) for run in runs],
            "total": len(runs),
            "limit": limit,
        }

    async def get_query_run(self, run_id: str) -> JSONDict:
        trace_store = self._get_query_trace_store()
        run = trace_store.get(run_id)
        if run is None:
            raise LookupError(f"Query run not found: {run_id}")
        return self._serialize_query_run(run)

    async def get_entity_timeline(self, entity_id: str) -> JSONDict:
        temporal_kg = self._get_temporal_kg()
        triples = await temporal_kg.get_entity_timeline(entity_id)
        return {
            "entity_id": entity_id,
            "total": len(triples),
            "triples": [self._serialize_temporal_triple(triple) for triple in triples],
        }

    async def get_entity_state_as_of(self, entity_id: str, *, as_of: str) -> JSONDict:
        temporal_kg = self._get_temporal_kg()
        triples = await temporal_kg.get_entity_state_as_of(entity_id, as_of)
        return {
            "entity_id": entity_id,
            "as_of": as_of,
            "total": len(triples),
            "triples": [self._serialize_temporal_triple(triple) for triple in triples],
        }

    async def search_memories(
        self,
        *,
        query: str,
        top_k: int = 5,
        backend: SearchBackend = "graphrag",
        strategy: str = "hybrid",
        include_sources: bool = True,
        layer: MemoryLayerName = "auto",
        layer_budget_override: int | None = None,
    ) -> JSONDict:
        llm = self._get_llm_manager()
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        metadata_cache: dict[str, JSONDict] = {}
        created_at_cache: dict[str, datetime] = {}
        facade = self._retrieval_facade_cls(llm, vector_store, graph_store)

        if backend == "graphrag":
            normalized_strategy = strategy.strip().lower() or "hybrid"
            if normalized_strategy not in GRAPHRAG_SEARCH_STRATEGIES:
                supported = ", ".join(sorted(GRAPHRAG_SEARCH_STRATEGIES))
                raise ValueError(f"Invalid GraphRAG strategy: {strategy}. Supported values: {supported}")

            result = await facade.search(
                query,
                strategy=normalized_strategy,
                top_k=top_k,
                include_sources=include_sources,
                layer=layer,
                layer_budget_override=layer_budget_override,
            )
            sources = [
                await self._build_search_source_payload(
                    vector_store=vector_store,
                    graph_store=graph_store,
                    source=source,
                    metadata_cache=metadata_cache,
                    created_at_cache=created_at_cache,
                )
                for source in result.sources
            ]
            communities = [
                {
                    "community_id": getattr(community, "community_id", None),
                    "title": getattr(community, "title", None),
                    "summary": getattr(community, "summary", None),
                    "level": getattr(community, "level", None),
                    "entities": list(getattr(community, "entities", []) or []),
                    "relationships": _serialize_value(getattr(community, "relationships", []) or []),
                    "relevance": getattr(community, "relevance", 0.0),
                }
                for community in result.communities
            ]
            return {
                "query": query,
                "backend": backend,
                "strategy": normalized_strategy,
                "layer_requested": getattr(result, "layer_requested", layer),
                "layer_used": getattr(result, "layer_used", None),
                "layer_fallback_chain": list(getattr(result, "layer_fallback_chain", []) or []),
                "context_token_estimate": int(getattr(result, "context_token_estimate", 0) or 0),
                "layer_build_duration_ms": int(getattr(result, "layer_build_duration_ms", 0) or 0),
                "processing_time_ms": getattr(result, "processing_time_ms", 0),
                "total_sources": len(sources),
                "total_communities": len(communities),
                "entities": list(getattr(result, "entities", []) or []),
                "query_entities": list(getattr(result, "query_entities", []) or []),
                "sources": sources,
                "communities": communities,
            }

        normalized_strategy = strategy.strip().lower() or "hybrid"
        if normalized_strategy not in STANDARD_SEARCH_STRATEGIES:
            supported = ", ".join(sorted(STANDARD_SEARCH_STRATEGIES))
            raise ValueError(f"Invalid standard strategy: {strategy}. Supported values: {supported}")

        result = await facade.search(
            query,
            strategy=normalized_strategy,
            top_k=top_k,
            include_sources=include_sources,
            layer=layer,
            layer_budget_override=layer_budget_override,
        )
        sources = [
            await self._build_search_source_payload(
                vector_store=vector_store,
                graph_store=graph_store,
                source=source,
                metadata_cache=metadata_cache,
                created_at_cache=created_at_cache,
            )
            for source in result.sources
        ]
        return {
            "query": query,
            "backend": backend,
            "strategy": normalized_strategy,
            "layer_requested": getattr(result, "layer_requested", layer),
            "layer_used": getattr(result, "layer_used", None),
            "layer_fallback_chain": list(getattr(result, "layer_fallback_chain", []) or []),
            "context_token_estimate": int(getattr(result, "context_token_estimate", 0) or 0),
            "layer_build_duration_ms": int(getattr(result, "layer_build_duration_ms", 0) or 0),
            "processing_time_ms": getattr(result, "processing_time_ms", 0),
            "total_sources": len(sources),
            "total_communities": 0,
            "entities": list(getattr(result, "entities", []) or []),
            "query_entities": [],
            "sources": sources,
            "communities": [],
        }

    async def list_sync_sources(self) -> JSONDict:
        sources = [
            _serialize_value(sync_routes_module._serialize_sync_source_setting(payload).model_dump())
            for payload in sync_routes_module._load_sync_source_settings()
        ]
        return {
            "sources": sources,
            "total": len(sources),
        }

    async def get_sync_source_status(self, source_id: str) -> JSONDict:
        setting = sync_routes_module._get_sync_source_setting_or_404(source_id)
        config, worker = sync_routes_module._build_source_worker(setting)
        matched_files = worker.parser.list_source_files()
        local_state = worker.get_local_state()
        remote_state = await get_sync_service().get_state(
            source_system=config.source_system,
            workspace_id=config.workspace_id,
        )
        response = sync_routes_module._build_source_status_response(
            source_id=source_id,
            setting=setting,
            config=config,
            matched_files=len(matched_files),
            local_state=local_state,
            remote_state=remote_state,
        )
        return _serialize_value(response.model_dump())

    async def get_runtime_diagnostics(self) -> JSONDict:
        checks = {
            "config": api_main_module._run_config_check(source="memory-graph://diagnostics/runtime"),
            "provider": await api_main_module._run_provider_check(source="memory-graph://diagnostics/runtime"),
            "sqlite": await api_main_module._run_sqlite_check(source="memory-graph://diagnostics/runtime"),
            "vector_store": await api_main_module._run_vector_store_check(source="memory-graph://diagnostics/runtime"),
        }
        task_chain = api_main_module._run_task_chain_check(source="memory-graph://diagnostics/runtime")
        is_healthy = all(check["ok"] for check in checks.values())
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "Memory Graph API",
            "version": "1.0.0",
            "generated_at": api_main_module._now_iso(),
            "checks": checks,
            "task_chain": task_chain,
            "recent_failures": api_main_module._recent_failures_snapshot(),
        }

    async def preview_memory_layer(
        self,
        *,
        layer: MemoryLayerName = "auto",
        question: str | None = None,
        strategy: str = "hybrid",
        top_k: int = 5,
        layer_budget_override: int | None = None,
    ) -> JSONDict:
        """Preview the resolved memory-layer behavior without introducing a separate code path."""
        llm = self._get_llm_manager()
        vector_store = self._get_vector_store()
        graph_store = self._get_graph_store()
        facade = self._retrieval_facade_cls(llm, vector_store, graph_store)

        if question:
            result = await facade.search(
                question,
                strategy=strategy,
                top_k=top_k,
                include_sources=True,
                layer=layer,
                layer_budget_override=layer_budget_override,
            )
            context_items = _serialize_value(list(getattr(result, "layer_context_items", []) or []))
        else:
            plan = facade.resolve_strategy(strategy)
            layer_result = facade._resolve_memory_layer(
                layer=layer,
                strategy_plan=plan,
                layer_budget_override=layer_budget_override,
            )
            result = SimpleNamespace(
                layer_used=layer_result.resolved_layer,
                layer_fallback_chain=layer_result.fallback_chain,
                context_token_estimate=layer_result.token_estimate,
                layer_build_duration_ms=0,
                layer_warnings=layer_result.diagnostics.warnings,
                layer_budget_max_tokens=layer_result.token_budget.max_tokens,
                layer_context_items=layer_result.context_items,
            )
            context_items = _serialize_value(list(layer_result.context_items))

        return {
            "requested_layer": layer,
            "resolved_layer": getattr(result, "layer_used", None),
            "fallback_chain": list(getattr(result, "layer_fallback_chain", []) or []),
            "token_budget": int(getattr(result, "layer_budget_max_tokens", 0) or 0),
            "token_estimate": int(getattr(result, "context_token_estimate", 0) or 0),
            "layer_build_duration_ms": int(getattr(result, "layer_build_duration_ms", 0) or 0),
            "warnings": list(getattr(result, "layer_warnings", []) or []),
            "context_items": context_items,
            "question": question,
            "strategy": strategy,
            "top_k": top_k,
        }

    async def get_stats_resource_payload(self) -> JSONDict:
        vector_store = self._get_vector_store()
        return {
            "graph": await self.get_graph_stats(),
            "vector_index": _serialize_value(await vector_store.get_index_state()),
        }

    async def get_recent_memories_resource_payload(self, *, limit: int = 10) -> JSONDict:
        recent = await self.list_memories(limit=limit, offset=0, status="active")
        return {
            "limit": limit,
            "total": recent["total"],
            "memories": recent["memories"],
        }

    async def get_recent_query_runs_resource_payload(self, *, limit: int = 10) -> JSONDict:
        runs = await self.list_query_runs(limit=limit)
        return {
            "limit": limit,
            "total": runs["total"],
            "runs": runs["runs"],
        }

    async def get_runtime_diagnostics_resource_payload(self) -> JSONDict:
        return await self.get_runtime_diagnostics()

    async def get_sync_sources_status_resource_payload(self) -> JSONDict:
        sources_payload = await self.list_sync_sources()
        statuses = []
        for source in list(sources_payload.get("sources") or []):
            source_id = source.get("source_id")
            if not isinstance(source_id, str):
                continue
            try:
                statuses.append(await self.get_sync_source_status(source_id))
            except Exception as exc:
                statuses.append(
                    {
                        "source_id": source_id,
                        "status": "degraded",
                        "detail": str(exc),
                    }
                )
        return {
            "total": len(statuses),
            "sources": statuses,
        }

    async def get_default_layer_preview_resource_payload(self) -> JSONDict:
        return await self.preview_memory_layer(layer="auto", question=None)

    def format_resource_payload(self, payload: JSONDict) -> str:
        return _format_json_resource(payload)


__all__ = [
    "MemoryGraphMCPService",
    "SearchBackend",
]
