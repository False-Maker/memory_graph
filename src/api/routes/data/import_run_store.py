"""Lightweight JSON store for recent data import runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

DEFAULT_IMPORT_RUNS_PATH = Path("data") / "import-runs.json"
MAX_STORED_IMPORT_RUNS = 200
_STORE_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_optional_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return dict(value)


def _normalize_run(raw: dict[str, Any], *, include_internal: bool = True) -> dict[str, Any]:
    """Normalize one run record and keep backward compatibility for older entries."""
    run_type = str(raw.get("run_type") or raw.get("type") or "unknown")
    retry_request = _to_optional_dict(raw.get("retry_request"))
    raw_retryable = raw.get("retryable")
    retryable = (
        bool(raw_retryable) if isinstance(raw_retryable, bool) else run_type == "directory_import"
    ) and retry_request is not None

    normalized = {
        "id": str(raw.get("id") or raw.get("run_id") or uuid4()),
        "created_at": str(raw.get("created_at") or raw.get("started_at") or _now_iso()),
        "started_at": _to_optional_str(raw.get("started_at") or raw.get("created_at")),
        "finished_at": _to_optional_str(raw.get("finished_at") or raw.get("updated_at")),
        "status": str(raw.get("status") or "unknown"),
        "run_type": run_type,
        "source": raw.get("source"),
        "source_id": _to_optional_str(raw.get("source_id")),
        "workspace_id": _to_optional_str(raw.get("workspace_id")),
        "label": _to_optional_str(raw.get("label")),
        "filename": raw.get("filename"),
        "source_path": _to_optional_str(raw.get("source_path")),
        "directory_path": _to_optional_str(raw.get("directory_path")),
        "imported": _to_int(raw.get("imported"), 0),
        "attempted": _to_int(raw.get("attempted"), 0),
        "failed": _to_int(raw.get("failed"), 0),
        "skipped": _to_int(raw.get("skipped"), 0),
        "message": _to_optional_str(raw.get("message")),
        "detail": raw.get("detail"),
        "error": raw.get("error"),
        "summary": _to_optional_dict(raw.get("summary")),
        "retryable": retryable,
        "retry_of": _to_optional_str(raw.get("retry_of")),
    }

    if include_internal:
        normalized["retry_request"] = retry_request

    return normalized


def get_import_runs_path() -> Path:
    from os import getenv

    configured = getenv("IMPORT_RUNS_STORE_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_IMPORT_RUNS_PATH


def _read_runs(path: Path, *, include_internal: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []
    return [
        _normalize_run(item, include_internal=include_internal)
        for item in payload
        if isinstance(item, dict)
    ]


def _write_runs(path: Path, runs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(runs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_import_run(run: dict[str, Any]) -> dict[str, Any]:
    """Persist one import run summary and return the stored payload."""
    path = get_import_runs_path()
    entry = _normalize_run(run)

    with _STORE_LOCK:
        runs = _read_runs(path)
        runs.insert(0, entry)
        _write_runs(path, runs[:MAX_STORED_IMPORT_RUNS])
    return entry


def list_recent_import_runs(*, limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent import runs, newest first."""
    safe_limit = max(0, int(limit))
    path = get_import_runs_path()
    with _STORE_LOCK:
        runs = _read_runs(path, include_internal=False)
    return runs[:safe_limit]


def get_import_run(run_id: str) -> dict[str, Any] | None:
    """Return one normalized import run by ID."""
    safe_run_id = _to_optional_str(run_id)
    if safe_run_id is None:
        return None

    path = get_import_runs_path()
    with _STORE_LOCK:
        runs = _read_runs(path)

    for run in runs:
        if run.get("id") == safe_run_id:
            return run
    return None
