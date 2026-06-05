"""API routes for external sync sources."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.schemas.sync import (
    EngramSyncPullChange,
    EngramSyncPullResponse,
    EngramSyncPushRequest,
    EngramSyncPushResponse,
    EngramSyncPushResult,
    EngramSyncStateResponse,
    SyncBatchUpsertRequest,
    SyncBatchUpsertResponse,
    SyncChangeFeedResponse,
    SyncDeleteRequest,
    SyncDeleteResponse,
    SyncReconcileRequest,
    SyncReconcileResponse,
    SyncSourcePreviewRequest,
    SyncSourcePreviewResponse,
    SyncSourcePullRequest,
    SyncSourcePullResponse,
    SyncSourcePullSummary,
    SyncSourcePushRequest,
    SyncSourcePushResponse,
    SyncSourcePushSummary,
    SyncSourceRestoreRequest,
    SyncSourceRestoreResponse,
    SyncSourceSettingDeleteResponse,
    SyncSourceSettingPayload,
    SyncSourceSettingResponse,
    SyncSourceSettingsResponse,
    SyncSourceStatusResponse,
    SyncSourceLocalStateSummary,
    SyncSourceRemoteStateSummary,
    SyncSourceSyncRequest,
    SyncSourceSyncResponse,
    SyncStateResponse,
    SyncUpsertResult,
)
from src.api.routes.data.import_run_store import record_import_run
from src.core.sync.source_models import SyncSourceConfig
from src.core.sync.source_parser import WorkspaceSourceParser
from src.core.sync.sync_worker import SourceSyncWorker
from src.core.sync.service import (
    SyncConflictError,
    SyncNotFoundError,
    get_sync_service,
)


router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


class SyncBatchUpsertSummary(BaseModel):
    """Aggregated batch-upsert status for quick recovery decisions."""

    total_records: int = 0
    created: int = 0
    updated: int = 0
    noop: int = 0
    conflicts: int = 0
    rejected: int = 0
    duplicate_external_ids: list[str] = Field(default_factory=list)
    conflict_external_ids: list[str] = Field(default_factory=list)
    rejected_external_ids: list[str] = Field(default_factory=list)
    retryable_external_ids: list[str] = Field(default_factory=list)
    needs_conflict_resolution: bool = False
    needs_retry: bool = False
    needs_attention: bool = False


class SyncBatchUpsertWithSummaryResponse(BaseModel):
    """Batch-upsert response with per-record results and summary."""

    results: list[SyncUpsertResult] = Field(default_factory=list)
    summary: SyncBatchUpsertSummary


def _normalize_source_system(value: str | None, default: str = "external") -> str:
    normalized = (value or default).strip().lower()
    return normalized or default


def _upsert_result_to_dict(item: object) -> dict:
    """Normalize one upsert result to a plain dict."""
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return {
        "external_id": getattr(item, "external_id", None),
        "memory_id": getattr(item, "memory_id", None),
        "result": getattr(item, "result", None),
        "server_version": getattr(item, "server_version", None),
        "sync_status": getattr(item, "sync_status", None),
        "detail": getattr(item, "detail", None),
    }


def _build_batch_upsert_summary(result_items: list[dict]) -> SyncBatchUpsertSummary:
    """Build a recovery-oriented summary from per-record upsert results."""
    counters = {
        "created": 0,
        "updated": 0,
        "noop": 0,
        "conflict": 0,
        "rejected": 0,
    }
    duplicate_external_ids: list[str] = []
    conflict_external_ids: list[str] = []
    rejected_external_ids: list[str] = []

    for item in result_items:
        outcome = str(item.get("result") or "").strip().lower()
        external_id = str(item.get("external_id") or "").strip()
        detail = str(item.get("detail") or "")

        if outcome in counters:
            counters[outcome] += 1

        if outcome == "conflict" and external_id:
            conflict_external_ids.append(external_id)
        if outcome == "rejected" and external_id:
            rejected_external_ids.append(external_id)
        if (
            outcome == "noop"
            and external_id
            and "duplicate" in detail.lower()
        ):
            duplicate_external_ids.append(external_id)

    retryable_external_ids = list(dict.fromkeys(rejected_external_ids))
    conflicts = list(dict.fromkeys(conflict_external_ids))
    duplicates = list(dict.fromkeys(duplicate_external_ids))
    needs_conflict_resolution = len(conflicts) > 0
    needs_retry = len(retryable_external_ids) > 0
    needs_attention = needs_conflict_resolution or needs_retry

    return SyncBatchUpsertSummary(
        total_records=len(result_items),
        created=counters["created"],
        updated=counters["updated"],
        noop=counters["noop"],
        conflicts=counters["conflict"],
        rejected=counters["rejected"],
        duplicate_external_ids=duplicates,
        conflict_external_ids=conflicts,
        rejected_external_ids=retryable_external_ids,
        retryable_external_ids=retryable_external_ids,
        needs_conflict_resolution=needs_conflict_resolution,
        needs_retry=needs_retry,
        needs_attention=needs_attention,
    )


def _to_engram_push_result(item: dict[str, object]) -> EngramSyncPushResult:
    return EngramSyncPushResult(
        external_id=str(item.get("external_id") or ""),
        status=str(item.get("result") or ""),
        memory_id=item.get("memory_id") if isinstance(item.get("memory_id"), str) else None,
        server_version=item.get("server_version") if isinstance(item.get("server_version"), int) else None,
        detail=item.get("detail") if isinstance(item.get("detail"), str) else None,
    )


def _build_sync_feed_diagnostics(*, cursor: int, limit: int, returned_count: int, next_cursor: int) -> dict[str, object]:
    truncated = returned_count >= limit and next_cursor > cursor
    return {
        "applied_filters": {
            "cursor": cursor,
            "limit": limit,
        },
        "server_side_filtered": True,
        "truncated": truncated,
        "candidate_window": None,
        "warnings": [],
    }


def _resolve_workspace_root(request: SyncSourcePreviewRequest) -> Path:
    """Resolve a stable workspace root for a multi-path sync source."""
    if request.workspace_root:
        return Path(request.workspace_root).expanduser().resolve()

    absolute_bases = []
    for raw_path in request.source_paths:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            continue
        absolute_bases.append((candidate.parent if candidate.suffix else candidate).resolve())

    if absolute_bases:
        return Path(os.path.commonpath([str(base) for base in absolute_bases])).resolve()

    return Path(".").resolve()


def build_sync_source_config(request: SyncSourcePreviewRequest) -> SyncSourceConfig:
    """Build one parser/client config from frontend-supplied source inputs."""
    return SyncSourceConfig(
        workspace_root=_resolve_workspace_root(request),
        source_system=_normalize_source_system(request.source_system),
        workspace_id=request.workspace_id or "default",
        source_paths=request.source_paths,
    )


def _serialize_matched_file(path: Path, workspace_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = workspace_root.resolve()
    if resolved_path.is_relative_to(resolved_root):
        return str(resolved_path.relative_to(resolved_root))
    return str(resolved_path)


def _get_sync_source_settings_path() -> Path:
    """Return the persisted sync-source settings file path."""
    return Path("data") / "sync-sources.json"


def _load_sync_source_settings() -> list[dict]:
    """Load saved sync source settings from disk."""
    path = _get_sync_source_settings_path()
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        return []
    return [item for item in sources if isinstance(item, dict)]


def _save_sync_source_settings(sources: list[dict]) -> None:
    """Persist sync source settings to disk."""
    path = _get_sync_source_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "sources": sources}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _serialize_sync_source_setting(payload: dict) -> SyncSourceSettingResponse:
    """Convert one persisted source setting dict into the response model."""
    return SyncSourceSettingResponse(
        source_id=str(payload["source_id"]),
        label=payload.get("label"),
        source_system=str(payload.get("source_system") or "external"),
        workspace_id=str(payload.get("workspace_id") or "default"),
        workspace_root=payload.get("workspace_root"),
        source_paths=list(payload.get("source_paths") or []),
        updated_at=payload["updated_at"],
    )


def _get_sync_source_setting_or_404(source_id: str) -> dict:
    """Load one saved source setting or raise a route-shaped 404."""
    for item in _load_sync_source_settings():
        if item.get("source_id") == source_id:
            return item
    raise HTTPException(status_code=404, detail=f"Sync source not found: {source_id}")


def _build_sync_source_preview_request_from_setting(payload: dict) -> SyncSourcePreviewRequest:
    """Convert one saved source setting into the preview/config request model."""
    return SyncSourcePreviewRequest(
        source_system=str(payload.get("source_system") or "external"),
        workspace_id=str(payload.get("workspace_id") or "default"),
        workspace_root=payload.get("workspace_root"),
        source_paths=list(payload.get("source_paths") or []),
    )


def _build_saved_sync_source_config(payload: dict) -> SyncSourceConfig:
    """Build one parser/client config from a persisted source setting."""
    return build_sync_source_config(_build_sync_source_preview_request_from_setting(payload))


class _InProcessSourceSyncClient:
    """Minimal sync client facade that talks to SyncService without loopback HTTP."""

    def __init__(self, config: SyncSourceConfig):
        self.config = config

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def batch_upsert(self, records: list[dict]) -> dict:
        request = SyncBatchUpsertRequest(
            source_system=self.config.source_system,
            workspace_id=self.config.workspace_id,
            client_id=f"{self.config.source_system}-sync",
            records=records,
        )
        payload = await get_sync_service().batch_upsert_source_memories(
            self.config.source_system,
            request,
        )
        if isinstance(payload, dict):
            return payload
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        return {"results": getattr(payload, "results", [])}

    async def reconcile(
        self,
        seen_external_ids: list[str],
        scan_id: str,
        delete_missing: bool = True,
    ) -> dict:
        request = SyncReconcileRequest(
            workspace_id=self.config.workspace_id,
            scan_id=scan_id,
            seen_external_ids=seen_external_ids,
            delete_missing=delete_missing,
        )
        return await get_sync_service().reconcile_source(
            self.config.source_system,
            request,
        )

    async def get_changes(self, cursor: int, limit: int = 100) -> dict:
        return await get_sync_service().get_changes(
            source_system=self.config.source_system,
            workspace_id=self.config.workspace_id,
            cursor=cursor,
            limit=limit,
        )


def _build_source_setting_dict(source_id: str, payload: SyncSourceSettingPayload) -> dict:
    """Build one persisted source setting dict."""
    return {
        "source_id": source_id,
        "label": payload.label or f"{payload.source_system}:{payload.workspace_id}",
        "source_system": _normalize_source_system(payload.source_system),
        "workspace_id": payload.workspace_id or "default",
        "workspace_root": payload.workspace_root,
        "source_paths": list(payload.source_paths),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _record_import_run_safe(payload: dict[str, object]) -> None:
    """Persist source operation history without breaking the API path."""
    try:
        record_import_run(payload)
    except Exception:
        return


def _build_source_operation_summary(operation_kind: str, payload: object) -> dict[str, object]:
    """Normalize one source operation summary for persisted history/UI reuse."""
    if operation_kind in {"push", "restore"}:
        return {
            "matched_files": int(getattr(payload, "matched_files", 0) or 0),
            "scanned_records": int(getattr(payload, "scanned_records", 0) or 0),
            "pushed_records": int(getattr(payload, "pushed_records", 0) or 0),
            "restore_candidates": int(getattr(payload, "restore_candidates", 0) or 0),
            "created": int(getattr(payload, "created", 0) or 0),
            "updated": int(getattr(payload, "updated", 0) or 0),
            "noop": int(getattr(payload, "noop", 0) or 0),
            "conflicts": int(getattr(payload, "conflicts", 0) or 0),
            "rejected": int(getattr(payload, "rejected", 0) or 0),
            "marker_updates": int(getattr(payload, "marker_updates", 0) or 0),
            "deleted_remote_records": list(getattr(payload, "deleted_remote_records", []) or []),
        }

    if operation_kind == "pull":
        return {
            "processed_changes": int(getattr(payload, "processed_changes", 0) or 0),
            "applied_creates": int(getattr(payload, "applied_creates", 0) or 0),
            "applied_updates": int(getattr(payload, "applied_updates", 0) or 0),
            "applied_deletes": int(getattr(payload, "applied_deletes", 0) or 0),
            "written_conflicts": int(getattr(payload, "written_conflicts", 0) or 0),
            "skipped_echoes": int(getattr(payload, "skipped_echoes", 0) or 0),
        }

    if operation_kind == "sync" and isinstance(payload, dict):
        push = payload.get("push")
        pull = payload.get("pull")
        return {
            "push": _build_source_operation_summary("push", push),
            "pull": _build_source_operation_summary("pull", pull),
        }

    return {}


def _record_source_operation_run(
    *,
    operation_kind: str,
    source_id: str,
    setting: dict,
    status: str,
    message: str,
    summary: dict[str, object] | None = None,
    error: str | None = None,
) -> None:
    """Persist one source push/pull/sync/restore run in the shared history store."""
    _record_import_run_safe(
        {
            "status": status,
            "run_type": f"source_{operation_kind}",
            "source": f"sync/sources/settings/{source_id}/{operation_kind}",
            "source_id": source_id,
            "workspace_id": setting.get("workspace_id"),
            "label": setting.get("label"),
            "source_path": setting.get("workspace_root"),
            "filename": setting.get("workspace_root"),
            "message": message,
            "detail": f"source_system={setting.get('source_system')} | workspace_id={setting.get('workspace_id')}",
            "summary": summary or {},
            "error": error,
        }
    )


def _build_source_worker(setting: dict) -> tuple[SyncSourceConfig, SourceSyncWorker]:
    """Build one in-process worker for a saved source setting."""
    config = _build_saved_sync_source_config(setting)
    worker = SourceSyncWorker(
        config=config,
        client=_InProcessSourceSyncClient(config),
    )
    return config, worker


def _build_push_attention_flags(summary: object) -> dict[str, bool]:
    conflicts = int(getattr(summary, 'conflicts', 0) or 0)
    rejected = int(getattr(summary, 'rejected', 0) or 0)
    return {
        'needs_conflict_resolution': conflicts > 0,
        'needs_retry': rejected > 0,
        'needs_attention': conflicts > 0 or rejected > 0,
    }


def _build_pull_attention_flags(summary: object) -> dict[str, bool]:
    conflicts = int(getattr(summary, 'written_conflicts', 0) or 0)
    return {
        'needs_conflict_resolution': conflicts > 0,
        'needs_attention': conflicts > 0,
    }


def _build_status_attention_payload(local_state: object, remote_state: dict) -> tuple[str, bool, bool, str | None]:
    records = getattr(local_state, 'records', {}) or {}
    local_conflicts = sum(1 for item in records.values() if getattr(item, 'sync_status', None) == 'conflict')
    remote_conflicts = int(remote_state.get('conflicts', 0) or 0)
    if local_conflicts > 0 or remote_conflicts > 0:
        return 'degraded', True, True, '存在冲突记录，需先处理 conflict 再继续同步。'
    return 'healthy', False, False, None


def _build_source_push_response(
    *,
    source_id: str,
    setting: dict,
    config: SyncSourceConfig,
    matched_files: int,
    summary: object,
) -> SyncSourcePushResponse:
    return SyncSourcePushResponse(
        source_id=source_id,
        label=setting.get("label"),
        source_system=config.source_system,
        workspace_id=config.workspace_id,
        workspace_root=str(config.workspace_root),
        source_paths=list(config.source_paths),
        state_path=str(config.resolved_state_path()),
        conflicts_dir=str(config.resolved_conflicts_dir()),
        summary=SyncSourcePushSummary(
            matched_files=matched_files,
            scanned_records=getattr(summary, "scanned_records", 0),
            pushed_records=getattr(summary, "pushed_records", 0),
            restore_candidates=getattr(summary, "restore_candidates", 0),
            created=getattr(summary, "created", 0),
            updated=getattr(summary, "updated", 0),
            noop=getattr(summary, "noop", 0),
            conflicts=getattr(summary, "conflicts", 0),
            rejected=getattr(summary, "rejected", 0),
            marker_updates=getattr(summary, "marker_updates", 0),
            deleted_remote_records=list(getattr(summary, "deleted_remote_records", [])),
            **_build_push_attention_flags(summary),
        ),
    )


def _build_source_pull_response(
    *,
    source_id: str,
    setting: dict,
    config: SyncSourceConfig,
    summary: object,
) -> SyncSourcePullResponse:
    return SyncSourcePullResponse(
        source_id=source_id,
        label=setting.get("label"),
        source_system=config.source_system,
        workspace_id=config.workspace_id,
        workspace_root=str(config.workspace_root),
        source_paths=list(config.source_paths),
        state_path=str(config.resolved_state_path()),
        conflicts_dir=str(config.resolved_conflicts_dir()),
        inbox_dir=str(config.resolved_inbox_dir()),
        summary=SyncSourcePullSummary(
            processed_changes=getattr(summary, "processed_changes", 0),
            applied_creates=getattr(summary, "applied_creates", 0),
            applied_updates=getattr(summary, "applied_updates", 0),
            applied_deletes=getattr(summary, "applied_deletes", 0),
            written_conflicts=getattr(summary, "written_conflicts", 0),
            skipped_echoes=getattr(summary, "skipped_echoes", 0),
            **_build_pull_attention_flags(summary),
        ),
    )


def _build_source_restore_response(
    *,
    source_id: str,
    setting: dict,
    config: SyncSourceConfig,
    matched_files: int,
    summary: object,
) -> SyncSourceRestoreResponse:
    return SyncSourceRestoreResponse(
        source_id=source_id,
        label=setting.get("label"),
        source_system=config.source_system,
        workspace_id=config.workspace_id,
        workspace_root=str(config.workspace_root),
        source_paths=list(config.source_paths),
        state_path=str(config.resolved_state_path()),
        conflicts_dir=str(config.resolved_conflicts_dir()),
        summary=_build_source_push_response(
            source_id=source_id,
            setting=setting,
            config=config,
            matched_files=matched_files,
            summary=summary,
        ).summary,
    )


def _build_source_status_response(
    *,
    source_id: str,
    setting: dict,
    config: SyncSourceConfig,
    matched_files: int,
    local_state: object,
    remote_state: dict,
) -> SyncSourceStatusResponse:
    records = getattr(local_state, "records", {}) or {}
    recent_mutation_ids = getattr(local_state, "recent_mutation_ids", []) or []
    status, needs_conflict_resolution, needs_attention, attention_reason = _build_status_attention_payload(local_state, remote_state)
    return SyncSourceStatusResponse(
        source_id=source_id,
        label=setting.get("label"),
        source_system=config.source_system,
        workspace_id=config.workspace_id,
        workspace_root=str(config.workspace_root),
        source_paths=list(config.source_paths),
        state_path=str(config.resolved_state_path()),
        conflicts_dir=str(config.resolved_conflicts_dir()),
        inbox_dir=str(config.resolved_inbox_dir()),
        matched_files=matched_files,
        status=status,
        needs_conflict_resolution=needs_conflict_resolution,
        needs_attention=needs_attention,
        attention_reason=attention_reason,
        local_state=SyncSourceLocalStateSummary(
            tracked_records=len(records),
            deleted_records=sum(1 for item in records.values() if getattr(item, "sync_status", None) == "deleted"),
            conflict_records=sum(1 for item in records.values() if getattr(item, "sync_status", None) == "conflict"),
            synced_records=sum(1 for item in records.values() if getattr(item, "sync_status", None) == "synced"),
            last_pulled_seq=int(getattr(local_state, "last_pulled_seq", 0) or 0),
            recent_mutation_ids=len(recent_mutation_ids),
        ),
        remote_state=SyncSourceRemoteStateSummary(
            active_records=int(remote_state.get("active_records", 0) or 0),
            tombstones=int(remote_state.get("tombstones", 0) or 0),
            conflicts=int(remote_state.get("conflicts", 0) or 0),
            last_change_seq=int(remote_state.get("last_change_seq", 0) or 0),
            last_server_change_at=remote_state.get("last_server_change_at"),
        ),
    )


@router.get("/sources/settings", response_model=SyncSourceSettingsResponse)
async def list_sync_source_settings():
    """List saved sync source settings."""
    try:
        sources = [
            _serialize_sync_source_setting(payload)
            for payload in _load_sync_source_settings()
        ]
        return SyncSourceSettingsResponse(sources=sources)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/settings", response_model=SyncSourceSettingResponse)
async def create_sync_source_setting(payload: SyncSourceSettingPayload):
    """Create a new saved sync source setting."""
    try:
        sources = _load_sync_source_settings()
        source_id = uuid.uuid4().hex[:12]
        setting = _build_source_setting_dict(source_id, payload)
        sources.append(setting)
        _save_sync_source_settings(sources)
        return _serialize_sync_source_setting(setting)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/sources/settings/{source_id}", response_model=SyncSourceSettingResponse)
async def update_sync_source_setting(source_id: str, payload: SyncSourceSettingPayload):
    """Update an existing saved sync source setting."""
    try:
        sources = _load_sync_source_settings()
        for index, item in enumerate(sources):
            if item.get("source_id") != source_id:
                continue
            updated = _build_source_setting_dict(source_id, payload)
            sources[index] = updated
            _save_sync_source_settings(sources)
            return _serialize_sync_source_setting(updated)
        raise HTTPException(status_code=404, detail=f"Sync source not found: {source_id}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/sources/settings/{source_id}", response_model=SyncSourceSettingDeleteResponse)
async def delete_sync_source_setting(source_id: str):
    """Delete one saved sync source setting."""
    try:
        sources = _load_sync_source_settings()
        remaining = [item for item in sources if item.get("source_id") != source_id]
        if len(remaining) == len(sources):
            raise HTTPException(status_code=404, detail=f"Sync source not found: {source_id}")
        _save_sync_source_settings(remaining)
        return SyncSourceSettingDeleteResponse(source_id=source_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/settings/{source_id}/push", response_model=SyncSourcePushResponse)
async def push_sync_source_setting(
    source_id: str,
    payload: SyncSourcePushRequest | None = Body(default=None),
):
    """Run one saved source through the local push + reconcile workflow."""
    try:
        request_payload = payload or SyncSourcePushRequest()
        setting = _get_sync_source_setting_or_404(source_id)
        config, worker = _build_source_worker(setting)
        matched_files = worker.parser.list_source_files()
        summary = await worker.push(
            batch_size=request_payload.batch_size,
            reconcile=True,
            delete_missing=request_payload.delete_missing,
        )
        response = _build_source_push_response(
            source_id=source_id,
            setting=setting,
            config=config,
            matched_files=len(matched_files),
            summary=summary,
        )
        _record_source_operation_run(
            operation_kind="push",
            source_id=source_id,
            setting=setting,
            status="succeeded",
            message=f"source push completed: {setting.get('label') or source_id}",
            summary=response.summary.model_dump(),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        setting = locals().get("setting")
        if isinstance(setting, dict):
            _record_source_operation_run(
                operation_kind="push",
                source_id=source_id,
                setting=setting,
                status="failed",
                message="source push failed",
                error=str(exc),
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/settings/{source_id}/pull", response_model=SyncSourcePullResponse)
async def pull_sync_source_setting(
    source_id: str,
    payload: SyncSourcePullRequest | None = Body(default=None),
):
    """Run one saved source pull and write remote changes into the local workspace."""
    try:
        request_payload = payload or SyncSourcePullRequest()
        setting = _get_sync_source_setting_or_404(source_id)
        config, worker = _build_source_worker(setting)
        summary = await worker.pull(limit=request_payload.change_limit)
        response = _build_source_pull_response(
            source_id=source_id,
            setting=setting,
            config=config,
            summary=summary,
        )
        _record_source_operation_run(
            operation_kind="pull",
            source_id=source_id,
            setting=setting,
            status="succeeded",
            message=f"source pull completed: {setting.get('label') or source_id}",
            summary=response.summary.model_dump(),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        setting = locals().get("setting")
        if isinstance(setting, dict):
            _record_source_operation_run(
                operation_kind="pull",
                source_id=source_id,
                setting=setting,
                status="failed",
                message="source pull failed",
                error=str(exc),
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/settings/{source_id}/sync", response_model=SyncSourceSyncResponse)
async def sync_sync_source_setting(
    source_id: str,
    payload: SyncSourceSyncRequest | None = Body(default=None),
):
    """Run one saved source full sync: push local changes, then pull remote changes."""
    try:
        request_payload = payload or SyncSourceSyncRequest()
        setting = _get_sync_source_setting_or_404(source_id)
        config, worker = _build_source_worker(setting)
        result = await worker.sync(
            batch_size=request_payload.batch_size,
            change_limit=request_payload.change_limit,
            delete_missing=request_payload.delete_missing,
        )
        push_summary = getattr(result, "get", None)
        push_payload = result.get("push") if callable(push_summary) else None
        pull_payload = result.get("pull") if callable(push_summary) else None

        response = SyncSourceSyncResponse(
            source_id=source_id,
            label=setting.get("label"),
            source_system=config.source_system,
            workspace_id=config.workspace_id,
            workspace_root=str(config.workspace_root),
            source_paths=list(config.source_paths),
            state_path=str(config.resolved_state_path()),
            conflicts_dir=str(config.resolved_conflicts_dir()),
            inbox_dir=str(config.resolved_inbox_dir()),
            push=_build_source_push_response(
                source_id=source_id,
                setting=setting,
                config=config,
                matched_files=len(worker.parser.list_source_files()),
                summary=push_payload,
            ).summary,
            pull=_build_source_pull_response(
                source_id=source_id,
                setting=setting,
                config=config,
                summary=pull_payload,
            ).summary,
        )
        _record_source_operation_run(
            operation_kind="sync",
            source_id=source_id,
            setting=setting,
            status="succeeded",
            message=f"source sync completed: {setting.get('label') or source_id}",
            summary=response.model_dump(include={"push", "pull"}),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        setting = locals().get("setting")
        if isinstance(setting, dict):
            _record_source_operation_run(
                operation_kind="sync",
                source_id=source_id,
                setting=setting,
                status="failed",
                message="source sync failed",
                error=str(exc),
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/settings/{source_id}/restore", response_model=SyncSourceRestoreResponse)
async def restore_sync_source_setting(
    source_id: str,
    payload: SyncSourceRestoreRequest | None = Body(default=None),
):
    """Restore local-state records that are still marked deleted for one saved source."""
    try:
        request_payload = payload or SyncSourceRestoreRequest()
        setting = _get_sync_source_setting_or_404(source_id)
        config, worker = _build_source_worker(setting)
        matched_files = worker.parser.list_source_files()
        summary = await worker.restore(batch_size=request_payload.batch_size)
        response = _build_source_restore_response(
            source_id=source_id,
            setting=setting,
            config=config,
            matched_files=len(matched_files),
            summary=summary,
        )
        _record_source_operation_run(
            operation_kind="restore",
            source_id=source_id,
            setting=setting,
            status="succeeded",
            message=f"source restore completed: {setting.get('label') or source_id}",
            summary=response.summary.model_dump(),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        setting = locals().get("setting")
        if isinstance(setting, dict):
            _record_source_operation_run(
                operation_kind="restore",
                source_id=source_id,
                setting=setting,
                status="failed",
                message="source restore failed",
                error=str(exc),
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sources/settings/{source_id}/status", response_model=SyncSourceStatusResponse)
async def get_sync_source_setting_status(source_id: str):
    """Inspect local and remote state for one saved source setting."""
    try:
        setting = _get_sync_source_setting_or_404(source_id)
        config, worker = _build_source_worker(setting)
        matched_files = worker.parser.list_source_files()
        local_state = worker.get_local_state()
        remote_state = await get_sync_service().get_state(
            source_system=config.source_system,
            workspace_id=config.workspace_id,
        )
        return _build_source_status_response(
            source_id=source_id,
            setting=setting,
            config=config,
            matched_files=len(matched_files),
            local_state=local_state,
            remote_state=remote_state,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/preview", response_model=SyncSourcePreviewResponse)
async def preview_sync_source(request: SyncSourcePreviewRequest):
    """Preview a user-defined sync source without mutating any state."""
    try:
        config = build_sync_source_config(request)
        parser = WorkspaceSourceParser(config)
        matched_files = parser.list_source_files()
        snapshot = parser.scan_workspace()
        return SyncSourcePreviewResponse(
            source_system=config.source_system,
            workspace_id=config.workspace_id,
            workspace_root=str(config.workspace_root),
            source_paths=list(config.source_paths),
            matched_files=[
                _serialize_matched_file(path, config.workspace_root)
                for path in matched_files
            ],
            record_count=len(snapshot.records),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/sources/memories:batch-upsert",
    response_model=SyncBatchUpsertWithSummaryResponse,
)
async def batch_upsert_source_memories(request: SyncBatchUpsertRequest):
    """Batch upsert records for one named external source."""
    try:
        payload = await get_sync_service().batch_upsert_source_memories(
            _normalize_source_system(request.source_system, default="external"),
            request,
        )
        if isinstance(payload, SyncBatchUpsertResponse):
            result_items = [_upsert_result_to_dict(item) for item in payload.results]
        else:
            result_items = [
                _upsert_result_to_dict(item)
                for item in (payload.get("results") if isinstance(payload, dict) else [])
            ]

        return SyncBatchUpsertWithSummaryResponse(
            results=[SyncUpsertResult(**item) for item in result_items],
            summary=_build_batch_upsert_summary(result_items),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/sources/{source_system}/memories/{workspace_id}/{external_id}",
    response_model=SyncDeleteResponse,
)
async def delete_source_memory(
    source_system: str,
    workspace_id: str,
    external_id: str,
    request: SyncDeleteRequest,
):
    """Delete one synced record for a named external source."""
    try:
        return await get_sync_service().delete_source_memory(
            _normalize_source_system(source_system, default="external"),
            workspace_id,
            external_id,
            request,
        )
    except SyncNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SyncConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": exc.detail,
                "current_server_version": exc.current_version,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sources/{source_system}/changes", response_model=SyncChangeFeedResponse)
async def list_source_changes(
    source_system: str,
    workspace_id: str,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List change-feed items for one named external source."""
    try:
        payload = await get_sync_service().get_changes(
            source_system=_normalize_source_system(source_system, default="external"),
            workspace_id=workspace_id,
            cursor=cursor,
            limit=limit,
        )
        return SyncChangeFeedResponse(
            **payload,
            diagnostics=_build_sync_feed_diagnostics(
                cursor=cursor,
                limit=limit,
                returned_count=len(list(payload.get("changes") or [])),
                next_cursor=int(payload.get("next_cursor", cursor) or cursor),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sources/{source_system}/reconcile", response_model=SyncReconcileResponse)
async def reconcile_source_workspace(source_system: str, request: SyncReconcileRequest):
    """Reconcile a full scan against the server registry for one named external source."""
    try:
        payload = await get_sync_service().reconcile_source(
            _normalize_source_system(source_system, default="external"),
            request,
        )
        return SyncReconcileResponse(**payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sources/{source_system}/state", response_model=SyncStateResponse)
async def get_sync_source_state(source_system: str, workspace_id: str):
    """Get aggregate sync state for one named external source workspace."""
    try:
        payload = await get_sync_service().get_state(
            _normalize_source_system(source_system, default="external"),
            workspace_id,
        )
        return SyncStateResponse(**payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/push", response_model=EngramSyncPushResponse)
async def compat_sync_push(request: EngramSyncPushRequest):
    """Engram-compatible push entrypoint backed by the existing batch-upsert service."""
    try:
        normalized_request = SyncBatchUpsertRequest(
            source_system=_normalize_source_system(request.source_system, default="external"),
            workspace_id=request.workspace_id,
            client_id=request.client_id,
            records=[record.model_dump() for record in request.records],
        )
        payload = await get_sync_service().batch_upsert_source_memories(
            normalized_request.source_system,
            normalized_request,
        )
        if isinstance(payload, SyncBatchUpsertResponse):
            result_items = [_upsert_result_to_dict(item) for item in payload.results]
        else:
            result_items = [
                _upsert_result_to_dict(item)
                for item in (payload.get("results") if isinstance(payload, dict) else [])
            ]
        return EngramSyncPushResponse(
            results=[_to_engram_push_result(item) for item in result_items],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pull", response_model=EngramSyncPullResponse)
async def compat_sync_pull(
    workspace_id: str = Query(alias="workspaceId"),
    source_system: str = Query(default="external", alias="sourceSystem"),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Engram-compatible pull entrypoint backed by the existing change feed."""
    try:
        payload = await get_sync_service().get_changes(
            source_system=_normalize_source_system(source_system, default="external"),
            workspace_id=workspace_id,
            cursor=cursor,
            limit=limit,
        )
        return EngramSyncPullResponse(
            next_cursor=int(payload.get("next_cursor", cursor) or cursor),
            changes=[
                EngramSyncPullChange(
                    cursor=int(item.get("seq", 0) or 0),
                    change_type=str(item.get("change_type") or ""),
                    memory_id=str(item.get("memory_id") or ""),
                    external_id=item.get("external_id") if isinstance(item.get("external_id"), str) else None,
                    server_version=int(item.get("server_version", 0) or 0),
                    record=item.get("record") if isinstance(item.get("record"), dict) else None,
                )
                for item in list(payload.get("changes") or [])
            ],
            diagnostics=_build_sync_feed_diagnostics(
                cursor=cursor,
                limit=limit,
                returned_count=len(list(payload.get("changes") or [])),
                next_cursor=int(payload.get("next_cursor", cursor) or cursor),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/state", response_model=EngramSyncStateResponse)
async def compat_sync_state(
    workspace_id: str = Query(alias="workspaceId"),
    source_system: str = Query(default="external", alias="sourceSystem"),
):
    """Engram-compatible sync state entrypoint backed by the existing workspace summary."""
    try:
        payload = await get_sync_service().get_state(
            _normalize_source_system(source_system, default="external"),
            workspace_id,
        )
        metadata = {
            "sourceSystem": _normalize_source_system(source_system, default="external"),
            "lastServerChangeAt": payload.get("last_server_change_at"),
        }
        return EngramSyncStateResponse(
            workspace_id=payload["workspace_id"],
            active_records=int(payload.get("active_records", 0) or 0),
            tombstones=int(payload.get("tombstones", 0) or 0),
            conflicts=int(payload.get("conflicts", 0) or 0),
            last_change_cursor=int(payload.get("last_change_seq", 0) or 0),
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
