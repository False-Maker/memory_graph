"""Lazy exports for the sync package."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "SyncConflictError": ("src.core.sync.service", "SyncConflictError"),
    "SyncNotFoundError": ("src.core.sync.service", "SyncNotFoundError"),
    "SyncService": ("src.core.sync.service", "SyncService"),
    "get_sync_service": ("src.core.sync.service", "get_sync_service"),
    "SyncApiClient": ("src.core.sync.sync_api_client", "SyncApiClient"),
    "SyncConflictStore": ("src.core.sync.sync_conflicts", "SyncConflictStore"),
    "SyncSourceConfig": ("src.core.sync.source_models", "SyncSourceConfig"),
    "SyncSourceRecord": ("src.core.sync.source_models", "SyncSourceRecord"),
    "WorkspaceSnapshot": ("src.core.sync.source_models", "WorkspaceSnapshot"),
    "SyncStateRecord": ("src.core.sync.source_models", "SyncStateRecord"),
    "SyncState": ("src.core.sync.source_models", "SyncState"),
    "WorkspaceSourceParser": ("src.core.sync.source_parser", "WorkspaceSourceParser"),
    "SyncStateStore": ("src.core.sync.sync_state_store", "SyncStateStore"),
    "SourceSyncWorker": ("src.core.sync.sync_worker", "SourceSyncWorker"),
    "PushSummary": ("src.core.sync.sync_worker", "PushSummary"),
    "PullSummary": ("src.core.sync.sync_worker", "PullSummary"),
    "run_sync": ("src.core.sync.sync_worker", "run_sync"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve exported sync symbols lazily on first access."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__():
    """Expose lazy exports to interactive tooling."""
    return sorted(set(globals()) | set(__all__))
