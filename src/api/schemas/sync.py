"""API schemas for sync endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.diagnostics import CollectionDiagnostics


class SyncRecordInput(BaseModel):
    """Single synced record to upsert."""

    external_id: str
    source_path: str
    record_type: str
    title: Optional[str] = None
    content: str
    tags: List[str] = Field(default_factory=list)
    content_checksum: str
    external_updated_at: Optional[datetime] = None
    external_revision: Optional[str] = None
    base_server_version: Optional[int] = None
    client_mutation_id: str
    scope: Optional[str] = None
    scope_id: Optional[str] = None
    visibility: Optional[str] = None
    owner: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    artifact_id: Optional[str] = None
    summary: Optional[str] = None
    confidence: Optional[float] = None
    freshness: Optional[float] = None
    pinned: Optional[bool] = None
    expires_at: Optional[datetime] = None


class SyncBatchUpsertRequest(BaseModel):
    """Batch upsert request."""

    source_system: str = "external"
    workspace_id: str
    client_id: str
    records: List[SyncRecordInput] = Field(default_factory=list)

    @field_validator("source_system", "workspace_id", "client_id", mode="before")
    @classmethod
    def normalize_required_strings(cls, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or value


class SyncUpsertResult(BaseModel):
    """Per-record upsert result."""

    external_id: str
    memory_id: Optional[str] = None
    result: Literal["created", "updated", "noop", "conflict", "rejected"]
    server_version: Optional[int] = None
    sync_status: Optional[str] = None
    detail: Optional[str] = None


class SyncBatchUpsertResponse(BaseModel):
    """Batch upsert response."""

    results: List[SyncUpsertResult] = Field(default_factory=list)


class SyncDeleteRequest(BaseModel):
    """Delete request for one synced memory."""

    base_server_version: int
    external_revision: Optional[str] = None
    client_mutation_id: str


class SyncDeleteResponse(BaseModel):
    """Delete response."""

    external_id: str
    memory_id: str
    result: Literal["deleted", "noop"]
    server_version: int
    sync_status: str


class SyncChangeRecord(BaseModel):
    """Single change-feed item."""

    seq: int
    change_type: str
    origin: str
    client_mutation_id: Optional[str] = None
    external_id: Optional[str] = None
    memory_id: str
    server_version: int
    occurred_at: datetime
    record: Optional[Dict[str, Any]] = None


class SyncChangeFeedResponse(BaseModel):
    """Change-feed response."""

    next_cursor: int
    changes: List[SyncChangeRecord] = Field(default_factory=list)
    diagnostics: CollectionDiagnostics = Field(default_factory=CollectionDiagnostics)


class SyncReconcileRequest(BaseModel):
    """Full rescan reconcile request."""

    workspace_id: str
    scan_id: str
    seen_external_ids: List[str] = Field(default_factory=list)
    delete_missing: bool = False


class SyncSourcePreviewRequest(BaseModel):
    """Preview one user-supplied sync source definition."""

    source_system: str = "external"
    workspace_id: str = "default"
    workspace_root: Optional[str] = None
    source_paths: List[str] = Field(default_factory=list)

    @field_validator("source_system", "workspace_id", "workspace_root", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("source_paths", mode="before")
    @classmethod
    def normalize_source_paths(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]

        normalized_paths = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized and normalized not in normalized_paths:
                normalized_paths.append(normalized)
        return normalized_paths


class SyncSourcePreviewResponse(BaseModel):
    """Preview response for one user-defined sync source."""

    source_system: str
    workspace_id: str
    workspace_root: str
    source_paths: List[str] = Field(default_factory=list)
    matched_files: List[str] = Field(default_factory=list)
    record_count: int


class SyncSourceSettingPayload(BaseModel):
    """One saved sync source definition."""

    label: Optional[str] = None
    source_system: str = "external"
    workspace_id: str = "default"
    workspace_root: Optional[str] = None
    source_paths: List[str] = Field(default_factory=list)

    @field_validator("label", "source_system", "workspace_id", "workspace_root", mode="before")
    @classmethod
    def normalize_setting_strings(cls, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("source_paths", mode="before")
    @classmethod
    def normalize_setting_paths(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]

        normalized_paths = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized and normalized not in normalized_paths:
                normalized_paths.append(normalized)
        return normalized_paths


class SyncSourceSettingResponse(SyncSourceSettingPayload):
    """Saved sync source response."""

    source_id: str
    updated_at: datetime


class SyncSourceSettingsResponse(BaseModel):
    """List response for saved sync source settings."""

    sources: List[SyncSourceSettingResponse] = Field(default_factory=list)


class SyncSourceSettingDeleteResponse(BaseModel):
    """Delete response for one saved sync source."""

    success: bool = True
    source_id: str


class SyncSourcePushRequest(BaseModel):
    """Request payload for running one saved source push."""

    batch_size: int = Field(default=50, ge=1, le=200)
    delete_missing: bool = True


class SyncSourcePushSummary(BaseModel):
    """Summary of one saved source push run."""

    matched_files: int = 0
    scanned_records: int = 0
    pushed_records: int = 0
    restore_candidates: int = 0
    created: int = 0
    updated: int = 0
    noop: int = 0
    conflicts: int = 0
    rejected: int = 0
    marker_updates: int = 0
    deleted_remote_records: List[str] = Field(default_factory=list)
    needs_conflict_resolution: bool = False
    needs_retry: bool = False
    needs_attention: bool = False


class SyncSourcePushResponse(BaseModel):
    """Response for running one saved source push."""

    source_id: str
    label: Optional[str] = None
    source_system: str
    workspace_id: str
    workspace_root: str
    source_paths: List[str] = Field(default_factory=list)
    state_path: str
    conflicts_dir: str
    summary: SyncSourcePushSummary


class SyncSourcePullRequest(BaseModel):
    """Request payload for running one saved source pull."""

    change_limit: int = Field(default=100, ge=1, le=500)


class SyncSourcePullSummary(BaseModel):
    """Summary of one saved source pull run."""

    processed_changes: int = 0
    applied_creates: int = 0
    applied_updates: int = 0
    applied_deletes: int = 0
    written_conflicts: int = 0
    skipped_echoes: int = 0
    needs_conflict_resolution: bool = False
    needs_attention: bool = False


class SyncSourcePullResponse(BaseModel):
    """Response for running one saved source pull."""

    source_id: str
    label: Optional[str] = None
    source_system: str
    workspace_id: str
    workspace_root: str
    source_paths: List[str] = Field(default_factory=list)
    state_path: str
    conflicts_dir: str
    inbox_dir: str
    summary: SyncSourcePullSummary


class SyncSourceSyncRequest(BaseModel):
    """Request payload for running one saved source full sync."""

    batch_size: int = Field(default=50, ge=1, le=200)
    change_limit: int = Field(default=100, ge=1, le=500)
    delete_missing: bool = True


class SyncSourceSyncResponse(BaseModel):
    """Response for running one saved source full sync."""

    source_id: str
    label: Optional[str] = None
    source_system: str
    workspace_id: str
    workspace_root: str
    source_paths: List[str] = Field(default_factory=list)
    state_path: str
    conflicts_dir: str
    inbox_dir: str
    push: SyncSourcePushSummary
    pull: SyncSourcePullSummary


class SyncSourceRestoreRequest(BaseModel):
    """Request payload for restoring deleted local-state records."""

    batch_size: int = Field(default=50, ge=1, le=200)


class SyncSourceRestoreResponse(BaseModel):
    """Response for restoring one saved source."""

    source_id: str
    label: Optional[str] = None
    source_system: str
    workspace_id: str
    workspace_root: str
    source_paths: List[str] = Field(default_factory=list)
    state_path: str
    conflicts_dir: str
    summary: SyncSourcePushSummary


class SyncSourceLocalStateSummary(BaseModel):
    """Local persisted state summary for one saved source."""

    tracked_records: int = 0
    deleted_records: int = 0
    conflict_records: int = 0
    synced_records: int = 0
    last_pulled_seq: int = 0
    recent_mutation_ids: int = 0


class SyncSourceRemoteStateSummary(BaseModel):
    """Remote state summary for one saved source workspace."""

    active_records: int = 0
    tombstones: int = 0
    conflicts: int = 0
    last_change_seq: int = 0
    last_server_change_at: Optional[datetime] = None


class SyncSourceStatusResponse(BaseModel):
    """Combined local/remote status view for one saved source."""

    source_id: str
    label: Optional[str] = None
    source_system: str
    workspace_id: str
    workspace_root: str
    source_paths: List[str] = Field(default_factory=list)
    state_path: str
    conflicts_dir: str
    inbox_dir: str
    matched_files: int = 0
    status: str = 'healthy'
    needs_conflict_resolution: bool = False
    needs_attention: bool = False
    attention_reason: Optional[str] = None
    local_state: SyncSourceLocalStateSummary
    remote_state: SyncSourceRemoteStateSummary


class SyncReconcileResponse(BaseModel):
    """Reconcile response."""

    scan_id: str
    missing_external_ids: List[str] = Field(default_factory=list)
    deleted_external_ids: List[str] = Field(default_factory=list)
    active_count: int


class SyncStateResponse(BaseModel):
    """Workspace sync state response."""

    workspace_id: str
    active_records: int
    tombstones: int
    conflicts: int
    last_change_seq: int
    last_server_change_at: Optional[datetime] = None


class EngramSyncRecordInput(BaseModel):
    """Compat record payload aligned with engram-platform naming."""

    model_config = ConfigDict(populate_by_name=True)

    external_id: str = Field(
        validation_alias=AliasChoices("external_id", "externalId"),
        serialization_alias="externalId",
    )
    source_path: str = Field(
        validation_alias=AliasChoices("source_path", "sourcePath"),
        serialization_alias="sourcePath",
    )
    record_type: str = Field(
        validation_alias=AliasChoices("record_type", "recordType"),
        serialization_alias="recordType",
    )
    title: Optional[str] = None
    content: str
    tags: List[str] = Field(default_factory=list)
    content_checksum: str = Field(
        validation_alias=AliasChoices("content_checksum", "contentChecksum"),
        serialization_alias="contentChecksum",
    )
    external_updated_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("external_updated_at", "externalUpdatedAt"),
        serialization_alias="externalUpdatedAt",
    )
    external_revision: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("external_revision", "externalRevision"),
        serialization_alias="externalRevision",
    )
    base_server_version: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("base_server_version", "baseServerVersion"),
        serialization_alias="baseServerVersion",
    )
    client_mutation_id: str = Field(
        validation_alias=AliasChoices("client_mutation_id", "clientMutationId"),
        serialization_alias="clientMutationId",
    )
    scope: Optional[str] = None
    scope_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("scope_id", "scopeId"),
        serialization_alias="scopeId",
    )
    visibility: Optional[str] = None
    owner: Optional[str] = None
    session_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("session_id", "sessionId"),
        serialization_alias="sessionId",
    )
    thread_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("thread_id", "threadId"),
        serialization_alias="threadId",
    )
    task_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("task_id", "taskId"),
        serialization_alias="taskId",
    )
    artifact_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("artifact_id", "artifactId"),
        serialization_alias="artifactId",
    )
    summary: Optional[str] = None
    confidence: Optional[float] = None
    freshness: Optional[float] = None
    pinned: Optional[bool] = None
    expires_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("expires_at", "expiresAt"),
        serialization_alias="expiresAt",
    )


class EngramSyncPushRequest(BaseModel):
    """Compat push request for engram-platform."""

    model_config = ConfigDict(populate_by_name=True)

    source_system: str = Field(
        default="external",
        validation_alias=AliasChoices("source_system", "sourceSystem"),
        serialization_alias="sourceSystem",
    )
    workspace_id: str = Field(
        validation_alias=AliasChoices("workspace_id", "workspaceId"),
        serialization_alias="workspaceId",
    )
    client_id: str = Field(
        default="engram-platform",
        validation_alias=AliasChoices("client_id", "clientId"),
        serialization_alias="clientId",
    )
    records: List[EngramSyncRecordInput] = Field(default_factory=list)


class EngramSyncPushResult(BaseModel):
    """Compat per-record push result."""

    model_config = ConfigDict(populate_by_name=True)

    external_id: str = Field(serialization_alias="externalId")
    status: str
    memory_id: Optional[str] = Field(default=None, serialization_alias="memoryId")
    server_version: Optional[int] = Field(default=None, serialization_alias="serverVersion")
    detail: Optional[str] = None


class EngramSyncPushResponse(BaseModel):
    """Compat push response."""

    results: List[EngramSyncPushResult] = Field(default_factory=list)


class EngramSyncPullChange(BaseModel):
    """Compat change-feed item."""

    model_config = ConfigDict(populate_by_name=True)

    cursor: int
    change_type: str = Field(serialization_alias="changeType")
    memory_id: str = Field(serialization_alias="memoryId")
    external_id: Optional[str] = Field(default=None, serialization_alias="externalId")
    server_version: int = Field(serialization_alias="serverVersion")
    record: Optional[Dict[str, Any]] = None


class EngramSyncPullResponse(BaseModel):
    """Compat pull response."""

    model_config = ConfigDict(populate_by_name=True)

    next_cursor: int = Field(serialization_alias="nextCursor")
    changes: List[EngramSyncPullChange] = Field(default_factory=list)
    diagnostics: CollectionDiagnostics = Field(default_factory=CollectionDiagnostics)


class EngramSyncStateResponse(BaseModel):
    """Compat workspace state response."""

    model_config = ConfigDict(populate_by_name=True)

    workspace_id: str = Field(serialization_alias="workspaceId")
    active_records: int = Field(serialization_alias="activeRecords")
    tombstones: int
    conflicts: int
    last_change_cursor: int = Field(serialization_alias="lastChangeCursor")
    metadata: Dict[str, Any] = Field(default_factory=dict)
