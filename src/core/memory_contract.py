"""Shared Engram-facing memory metadata contract helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


MEMORY_METADATA_FIELDS: tuple[str, ...] = (
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
    "scope",
    "scope_id",
    "visibility",
    "owner",
    "session_id",
    "thread_id",
    "task_id",
    "artifact_id",
    "summary",
    "confidence",
    "freshness",
    "pinned",
    "expires_at",
)

_DATETIME_FIELDS = {
    "timestamp",
    "external_updated_at",
    "archived_at",
    "expires_at",
}
_LIST_FIELDS = {"tags"}
_FLOAT_FIELDS = {"confidence", "freshness"}
_BOOL_FIELDS = {"archived", "pinned"}


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]

    normalized: list[str] = []
    for item in values:
        if item is None:
            continue
        for chunk in str(item).split(","):
            candidate = chunk.strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
    return normalized


def coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def serialize_datetime(value: Any) -> str | None:
    parsed = coerce_datetime(value)
    return parsed.isoformat() if parsed else None


def normalize_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def metadata_contract_view(raw_metadata: Any) -> dict[str, Any]:
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    normalized: dict[str, Any] = {}
    for field_name in MEMORY_METADATA_FIELDS:
        value = metadata.get(field_name)
        if field_name in _LIST_FIELDS:
            normalized[field_name] = normalize_string_list(value)
        elif field_name in _DATETIME_FIELDS:
            normalized[field_name] = serialize_datetime(value)
        elif field_name in _FLOAT_FIELDS:
            normalized[field_name] = normalize_float(value)
        elif field_name in _BOOL_FIELDS:
            normalized[field_name] = normalize_bool(value)
        else:
            normalized[field_name] = normalize_string(value)
    return normalized


def resolve_memory_summary(raw_metadata: Any) -> str | None:
    return metadata_contract_view(raw_metadata).get("summary")


def is_memory_expired(raw_metadata: Any, *, now: datetime | None = None) -> bool:
    expires_at = coerce_datetime(metadata_contract_view(raw_metadata).get("expires_at"))
    if expires_at is None:
        return False

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    return expires_at <= current_time


def metadata_matches_filters(
    raw_metadata: Any,
    *,
    scopes: Iterable[str] | None = None,
    scope_ids: Iterable[str] | None = None,
    types: Iterable[str] | None = None,
    visibility: str | None = None,
    tags: Iterable[str] | None = None,
    workspace_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    thread_id: str | None = None,
    owner: str | None = None,
    include_expired: bool = False,
) -> bool:
    metadata = metadata_contract_view(raw_metadata)
    if not include_expired and is_memory_expired(metadata):
        return False

    normalized_scopes = normalize_string_list(scopes)
    normalized_scope_ids = normalize_string_list(scope_ids)
    normalized_types = normalize_string_list(types)
    normalized_tags = normalize_string_list(tags)

    if normalized_scopes and metadata.get("scope") not in normalized_scopes:
        return False
    if normalized_scope_ids and metadata.get("scope_id") not in normalized_scope_ids:
        return False
    if normalized_types and metadata.get("record_type") not in normalized_types:
        return False
    if visibility and metadata.get("visibility") != normalize_string(visibility):
        return False
    if workspace_id and metadata.get("workspace_id") != normalize_string(workspace_id):
        return False
    if session_id and metadata.get("session_id") != normalize_string(session_id):
        return False
    if task_id and metadata.get("task_id") != normalize_string(task_id):
        return False
    if thread_id and metadata.get("thread_id") != normalize_string(thread_id):
        return False
    if owner and metadata.get("owner") != normalize_string(owner):
        return False
    if normalized_tags and not set(normalized_tags).intersection(metadata.get("tags") or []):
        return False
    return True
