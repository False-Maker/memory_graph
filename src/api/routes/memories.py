"""
API Routes - Memories
"""
import time
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemoryCreateResponse,
    MemoryListResponse,
    MemoryMetadata,
    MemoryProvenance,
)
from src.core.llm_manager import get_llm_manager
from src.core.memory_contract import (
    metadata_contract_view,
    metadata_matches_filters,
    normalize_string_list,
    resolve_memory_summary,
)
from src.core.graph_store import get_graph_store
from src.core.vector_store import get_vector_store
from src.core.memory_service import get_memory_service


router = APIRouter(prefix="/api/v1/memories", tags=["memories"])
ARCHIVE_STATUS_VALUES = {"active", "archived", "all"}
_QA_FAIL_MEMORIES_LIST_ENV = "MEMORY_GRAPH_QA_FAIL_MEMORIES_LIST"


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _build_memory_provenance(metadata: MemoryMetadata | None, created_at: datetime) -> MemoryProvenance:
    if not metadata:
        return MemoryProvenance(time=created_at.isoformat())

    source_time = metadata.timestamp or metadata.external_updated_at
    return MemoryProvenance(
        type=_first_non_empty(metadata.record_type, metadata.source),
        time=(source_time.isoformat() if source_time else created_at.isoformat()),
        imported_from=_first_non_empty(
            metadata.source_path,
            metadata.external_id,
            metadata.workspace_id,
        ),
    )


def _normalize_memory_context(context: Dict[str, Any] | None) -> Dict[str, Any]:
    entities = context.get("entities", []) if isinstance(context, dict) else []
    communities = context.get("communities", []) if isinstance(context, dict) else []
    return {
        "entities": entities if isinstance(entities, list) else [],
        "communities": communities if isinstance(communities, list) else [],
    }


def _is_memory_archived(metadata: Dict[str, Any] | None) -> bool:
    if not isinstance(metadata, dict):
        return False
    return metadata.get("archived") is True


def _normalize_archive_status(value: str) -> str:
    normalized = (value or "active").strip().lower()
    if normalized not in ARCHIVE_STATUS_VALUES:
        supported = ", ".join(sorted(ARCHIVE_STATUS_VALUES))
        raise HTTPException(status_code=400, detail=f"Invalid status filter: {value}. Supported values: {supported}")
    return normalized


def _should_force_list_failure() -> bool:
    raw = str(os.environ.get(_QA_FAIL_MEMORIES_LIST_ENV, "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _filter_memories_by_status(memories: list[Any], status: str) -> list[Any]:
    if status == "all":
        return list(memories)
    archived = status == "archived"
    return [memory for memory in memories if _is_memory_archived(getattr(memory, "metadata", None)) is archived]


def _build_archive_metadata(memory: Any, archived: bool) -> Dict[str, Any]:
    metadata = dict(getattr(memory, "metadata", None) or {})
    if archived:
        metadata["archived"] = True
        metadata["archived_at"] = datetime.now().isoformat()
    else:
        metadata["archived"] = False
        metadata.pop("archived_at", None)
    return metadata


def _resolve_memory_created_at(registry: Dict[str, Any] | None) -> datetime:
    if registry and registry.get("created_at"):
        return datetime.fromisoformat(registry["created_at"])
    return datetime.now()


def _memory_sort_key(created_at: datetime, memory_id: str) -> tuple[float, str]:
    return (created_at.timestamp(), memory_id)


def _parse_list_cursor(cursor: Optional[str], *, default: int) -> int:
    if cursor in (None, ""):
        return default
    try:
        return max(0, int(str(cursor).strip()))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid memories cursor: {cursor}")


def _build_list_diagnostics(
    *,
    workspace_id: Optional[str],
    session_id: Optional[str],
    task_id: Optional[str],
    thread_id: Optional[str],
    scope: Optional[str],
    scope_id: Optional[str],
    record_type: Optional[str],
    tags: list[str],
    visibility: Optional[str],
    include_expired: bool,
    used_cursor: Optional[str],
) -> dict[str, Any]:
    applied_filters = {
        key: value
        for key, value in {
            "workspace_id": workspace_id,
            "session_id": session_id,
            "task_id": task_id,
            "thread_id": thread_id,
            "scope": scope,
            "scope_id": scope_id,
            "record_type": record_type,
            "tags": tags,
            "visibility": visibility,
            "include_expired": include_expired if include_expired else None,
            "cursor": used_cursor,
        }.items()
        if value not in (None, [], "")
    }
    return {
        "applied_filters": applied_filters,
        "server_side_filtered": bool(applied_filters),
        "truncated": False,
        "candidate_window": None,
        "warnings": [],
    }


def _build_memory_response(memory: Any, created_at: datetime) -> MemoryResponse:
    metadata_payload = metadata_contract_view(getattr(memory, "metadata", None) or {})
    metadata = MemoryMetadata(**metadata_payload)
    return MemoryResponse(
        id=memory.id,
        content=memory.content,
        summary=resolve_memory_summary(metadata_payload),
        metadata=metadata,
        provenance=_build_memory_provenance(metadata, created_at),
        created_at=created_at,
    )


def _matches_structured_filters(
    memory: Any,
    *,
    workspace_id: Optional[str],
    session_id: Optional[str],
    task_id: Optional[str],
    thread_id: Optional[str],
    scope: Optional[str],
    scope_id: Optional[str],
    record_type: Optional[str],
    tags: list[str],
    visibility: Optional[str],
    include_expired: bool,
) -> bool:
    return metadata_matches_filters(
        getattr(memory, "metadata", None) or {},
        scopes=[scope] if scope else [],
        scope_ids=[scope_id] if scope_id else [],
        types=[record_type] if record_type else [],
        visibility=visibility,
        tags=tags,
        workspace_id=workspace_id,
        session_id=session_id,
        task_id=task_id,
        thread_id=thread_id,
        include_expired=include_expired,
    )


@router.post("", response_model=MemoryCreateResponse)
async def create_memory(request: MemoryCreate):
    """Import a memory"""
    start_time = time.time()

    try:
        service = get_memory_service()
        metadata = request.metadata.model_dump() if request.metadata else {}
        result = await service.ingest_memory(
            content=request.content,
            metadata=metadata,
            source_system=metadata.get("source") or "manual",
        )

        processing_time = int((time.time() - start_time) * 1000)

        return MemoryCreateResponse(
            memory_id=result.memory_id,
            entities_count=result.entities_count,
            relationships_count=result.relationships_count,
            processing_time_ms=processing_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: Optional[str] = Query(default=None),
    status: str = Query(default="active"),
    workspace_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    task_id: Optional[str] = Query(default=None),
    thread_id: Optional[str] = Query(default=None),
    scope: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    record_type: Optional[str] = Query(default=None),
    tags: Optional[list[str]] = Query(default=None),
    visibility: Optional[str] = Query(default=None),
    include_expired: bool = Query(default=False),
):
    """List all memories"""
    try:
        if _should_force_list_failure():
            raise RuntimeError("QA forced failure for memories list")
        vector_store = get_vector_store()
        graph_store = get_graph_store()
        resolved_offset = _parse_list_cursor(cursor, default=offset)
        normalized_status = _normalize_archive_status(status)
        all_memories = await vector_store.get_memories(limit=None, offset=0)
        filtered_memories = _filter_memories_by_status(all_memories, normalized_status)
        normalized_tags = normalize_string_list(tags)
        filtered_memories = [
            memory
            for memory in filtered_memories
            if _matches_structured_filters(
                memory,
                workspace_id=workspace_id,
                session_id=session_id,
                task_id=task_id,
                thread_id=thread_id,
                scope=scope,
                scope_id=scope_id,
                record_type=record_type,
                tags=normalized_tags,
                visibility=visibility,
                include_expired=include_expired,
            )
        ]
        decorated_memories = []
        for mem in filtered_memories:
            registry = await graph_store.get_memory_registry(mem.id)
            created_at = _resolve_memory_created_at(registry)
            decorated_memories.append(
                (
                    created_at,
                    mem.id,
                    _build_memory_response(mem, created_at),
                )
            )

        decorated_memories.sort(
            key=lambda item: _memory_sort_key(item[0], item[1]),
            reverse=True,
        )
        total = len(decorated_memories)
        memory_responses = [
            item[2]
            for item in decorated_memories[resolved_offset : resolved_offset + limit]
        ]
        next_offset = resolved_offset + limit
        next_cursor = str(next_offset) if next_offset < total else None
        diagnostics = _build_list_diagnostics(
            workspace_id=workspace_id,
            session_id=session_id,
            task_id=task_id,
            thread_id=thread_id,
            scope=scope,
            scope_id=scope_id,
            record_type=record_type,
            tags=normalized_tags,
            visibility=visibility,
            include_expired=include_expired,
            used_cursor=cursor,
        )
        diagnostics["truncated"] = next_cursor is not None
        
        return MemoryListResponse(
            memories=memory_responses,
            total=total,
            limit=limit,
            offset=resolved_offset,
            next_cursor=next_cursor,
            diagnostics=diagnostics,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str):
    """Get a memory by ID"""
    try:
        vector_store = get_vector_store()
        graph_store = get_graph_store()
        memory = await vector_store.get_memory(memory_id)
        
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")

        registry = await graph_store.get_memory_registry(memory_id)
        created_at = (
            datetime.fromisoformat(registry["created_at"])
            if registry and registry.get("created_at")
            else datetime.now()
        )
        return _build_memory_response(memory, created_at)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}/context")
async def get_memory_context(memory_id: str):
    """Get related entities and communities for one memory."""
    try:
        vector_store = get_vector_store()
        graph_store = get_graph_store()
        memory = await vector_store.get_memory(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")

        context = _normalize_memory_context(await graph_store.get_memory_context(memory_id))
        return {
            "memory_id": memory_id,
            "entities": context["entities"],
            "communities": context["communities"],
            "total_entities": len(context["entities"]),
            "total_communities": len(context["communities"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory"""
    try:
        service = get_memory_service()
        result = await service.delete_memory(memory_id)
        if not result.deleted and result.sync_status == "not_found":
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {
            "success": True,
            "message": "Memory deleted",
            "memory_id": result.memory_id,
            "server_version": result.server_version,
            "sync_status": result.sync_status,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{memory_id}/archive")
async def archive_memory(memory_id: str):
    """Archive one memory without deleting it."""
    try:
        vector_store = get_vector_store()
        memory = await vector_store.get_memory(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")

        metadata = _build_archive_metadata(memory, archived=True)
        await vector_store.update_memory(memory_id=memory_id, metadata=metadata)
        return {
            "success": True,
            "memory_id": memory_id,
            "archived": True,
            "archived_at": metadata.get("archived_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{memory_id}/unarchive")
async def unarchive_memory(memory_id: str):
    """Restore one archived memory back into the active list."""
    try:
        vector_store = get_vector_store()
        memory = await vector_store.get_memory(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")

        metadata = _build_archive_metadata(memory, archived=False)
        await vector_store.update_memory(memory_id=memory_id, metadata=metadata)
        return {
            "success": True,
            "memory_id": memory_id,
            "archived": False,
            "archived_at": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
