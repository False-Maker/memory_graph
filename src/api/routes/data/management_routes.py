"""Management routes for data import/export and reindexing."""

import json
from typing import Any, List

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.api.routes.data.deps import (
    batch_create_memories as batch_create_memories_via_package,
    get_graph_store,
    get_llm_manager,
    get_memory_service,
    get_vector_store,
)
from src.api.routes.data.import_run_store import record_import_run
from src.api.security import read_upload_file_limited
from src.api.routes.data_helpers import build_export_payload
from src.api.schemas.memory import MemoryCreate

router = APIRouter(prefix="/api/v1/data", tags=["data"])


def _record_import_run_safe(payload: dict[str, Any]) -> None:
    try:
        record_import_run(payload)
    except Exception:
        # History tracking must never fail import API behavior.
        return


def _read_optional_payload_list(payload: dict[str, Any], key: str) -> list[Any]:
    """Read an optional list field from restore payload."""
    value = payload.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid restore payload: expected '{key}' list",
        )
    return value


def _read_restore_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize restore manifest metadata."""
    manifest = payload.get("manifest")
    if manifest is None:
        return {
            "present": False,
            "version": None,
            "exported_at": None,
            "counts": {},
        }

    if not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="Invalid restore payload: expected 'manifest' object")

    version = manifest.get("version")
    if version is not None and not isinstance(version, int):
        raise HTTPException(status_code=400, detail="Invalid restore payload: manifest.version must be an integer")

    exported_at = manifest.get("exported_at")
    if exported_at is not None and not isinstance(exported_at, str):
        raise HTTPException(status_code=400, detail="Invalid restore payload: manifest.exported_at must be a string")

    raw_counts = manifest.get("counts", {})
    if not isinstance(raw_counts, dict):
        raise HTTPException(status_code=400, detail="Invalid restore payload: manifest.counts must be an object")

    normalized_counts: dict[str, int] = {}
    for key in ("memories", "entities", "relationships"):
        value = raw_counts.get(key)
        if value is None:
            continue
        if not isinstance(value, int) or value < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid restore payload: manifest.counts.{key} must be a non-negative integer",
            )
        normalized_counts[key] = value

    return {
        "present": True,
        "version": version,
        "exported_at": exported_at,
        "counts": normalized_counts,
    }


@router.post("/import")
async def import_data(file: UploadFile = File(...)):
    """Import memories from JSON file."""
    filename = file.filename
    try:
        content = await read_upload_file_limited(file)
        data = json.loads(content)

        if not isinstance(data, list):
            data = [data]

        memory_requests = [
            item if isinstance(item, MemoryCreate) else MemoryCreate.model_validate(item)
            for item in data
        ]
        memories = await batch_create_memories_via_package(memory_requests)
        _record_import_run_safe(
            {
                "status": "succeeded",
                "run_type": "file_import",
                "source": "data/import",
                "filename": filename,
                "imported": memories["count"],
                "failed": 0,
            }
        )
        return {
            "success": True,
            "imported": memories["count"],
        }
    except HTTPException as exc:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "file_import",
                "source": "data/import",
                "filename": filename,
                "imported": 0,
                "failed": 1,
                "error": str(exc.detail),
            }
        )
        raise
    except Exception as exc:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "file_import",
                "source": "data/import",
                "filename": filename,
                "imported": 0,
                "failed": 1,
                "error": str(exc),
            }
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/export")
async def export_data():
    """Export all memories."""
    try:
        vector_store = get_vector_store()
        graph_store = get_graph_store()
        memories = await vector_store.get_memories(limit=10000)
        entities = await graph_store.get_entities(limit=10000)
        relationships = await graph_store.get_relationships(limit=10000)
        return build_export_payload(memories, entities, relationships)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("")
async def clear_all_data():
    """Clear all memories and graph data."""
    try:
        vector_store = get_vector_store()
        graph_store = get_graph_store()
        await vector_store.clear_all()
        await graph_store.clear_all()
        return {
            "success": True,
            "message": "All data cleared",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reindex")
async def rebuild_vector_index(
    reembed: bool = Query(default=False, description="Regenerate embeddings before rebuilding the index"),
    batch_size: int = Query(default=32, ge=1, le=256),
):
    """Rebuild the vector index and optionally regenerate embeddings."""
    try:
        vector_store = get_vector_store()

        if reembed:
            llm = get_llm_manager()
            result = await vector_store.reembed_all(
                embed_texts=llm.embed,
                batch_size=batch_size,
            )
        else:
            rebuilt = await vector_store.rebuild_index()
            result = {
                "documents": await vector_store.get_count(),
                "reembedded": 0,
                "indexed": rebuilt,
            }

        state = await vector_store.get_index_state()
        return {
            "success": True,
            "result": result,
            "state": state,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/restore")
async def restore_data(
    file: UploadFile = File(...),
    dry_run: bool = Query(
        default=False,
        description="Validate payload and manifest without mutating stores",
    ),
    clear_existing: bool = Query(
        default=True,
        description="Clear vector/graph stores before restoring snapshot memories",
    ),
    reindex: bool = Query(
        default=True,
        description="Rebuild vector index after restoring memories",
    ),
    reembed: bool = Query(
        default=False,
        description="Regenerate embeddings during post-restore reindex",
    ),
    batch_size: int = Query(default=32, ge=1, le=256),
):
    """Restore memories from an /export payload and optionally reindex."""
    try:
        content = await read_upload_file_limited(file)
        payload = json.loads(content)
    except HTTPException:
        raise
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON restore payload: {exc.msg}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid restore payload: expected object")

    memory_items = payload.get("memories")
    if not isinstance(memory_items, list):
        raise HTTPException(
            status_code=400,
            detail="Invalid restore payload: expected 'memories' list",
        )
    entity_items = _read_optional_payload_list(payload, "entities")
    relationship_items = _read_optional_payload_list(payload, "relationships")
    manifest = _read_restore_manifest(payload)
    payload_counts = {
        "memories": len(memory_items),
        "entities": len(entity_items),
        "relationships": len(relationship_items),
    }

    mismatch_labels = []
    for key, expected_count in manifest["counts"].items():
        actual_count = payload_counts[key]
        if expected_count != actual_count:
            mismatch_labels.append(f"{key}: expected {expected_count}, got {actual_count}")
    if mismatch_labels:
        raise HTTPException(
            status_code=400,
            detail=f"Restore manifest count mismatch: {', '.join(mismatch_labels)}",
        )

    try:
        memory_requests = [
            item if isinstance(item, MemoryCreate) else MemoryCreate.model_validate(item)
            for item in memory_items
        ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid memory item in restore payload: {exc}") from exc

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "validated": True,
            "preview": payload_counts,
            "manifest": {
                "present": manifest["present"],
                "version": manifest["version"],
                "exported_at": manifest["exported_at"],
                "counts": manifest["counts"],
                "matches_payload": True,
            },
            "would_clear_existing": clear_existing,
            "would_reindex": reindex,
            "would_reembed": bool(reindex and reembed),
        }

    try:
        vector_store = get_vector_store()
        graph_store = get_graph_store()

        if clear_existing:
            await vector_store.clear_all()
            await graph_store.clear_all()

        restored = await batch_create_memories_via_package(memory_requests)
        reindex_result = None
        state = None

        if reindex:
            if reembed:
                llm = get_llm_manager()
                reindex_result = await vector_store.reembed_all(
                    embed_texts=llm.embed,
                    batch_size=batch_size,
                )
            else:
                rebuilt = await vector_store.rebuild_index()
                reindex_result = {
                    "documents": await vector_store.get_count(),
                    "reembedded": 0,
                    "indexed": rebuilt,
                }
            state = await vector_store.get_index_state()

        return {
            "success": True,
            "restored": restored["count"],
            "cleared_existing": clear_existing,
            "reindex": reindex_result,
            "state": state,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/memories/batch")
async def batch_create_memories(memory_list: List[MemoryCreate]):
    """Batch create memories."""
    results = []
    service = get_memory_service()

    for memory in memory_list:
        metadata = memory.metadata.model_dump() if memory.metadata else {}
        result = await service.ingest_memory(
            content=memory.content,
            metadata=metadata,
            source_system=metadata.get("source") or "import",
        )
        results.append(result.memory_id)

    return {
        "success": True,
        "memory_ids": results,
        "count": len(results),
    }
