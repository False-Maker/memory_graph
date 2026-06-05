"""Models for external source sync clients."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class SyncSourceConfig:
    """Runtime configuration for one external source sync client."""

    workspace_root: Path
    source_system: str = "external"
    workspace_id: str = "workspace-main"
    api_url: str = "http://127.0.0.1:8000"
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    state_path: Optional[Path] = None
    conflicts_dir: Optional[Path] = None
    inbox_dir: Optional[Path] = None
    source_paths: List[str] = field(
        default_factory=lambda: [
            "MEMORY.md",
            "memory/**/*.md",
        ]
    )

    @property
    def scan_globs(self) -> List[str]:
        """Backward-compatible alias for older parser code."""
        return self.source_paths

    def resolved_state_path(self) -> Path:
        """Resolve the state JSON path."""
        if self.state_path is not None:
            return self.state_path
        return (
            Path.home()
            / ".openclaw"
            / self.workspace_id
            / "state"
            / "memory-graph-sync.json"
        )

    def resolved_conflicts_dir(self) -> Path:
        """Resolve the conflicts output directory."""
        if self.conflicts_dir is not None:
            return self.conflicts_dir
        return (
            Path.home()
            / ".openclaw"
            / self.workspace_id
            / "conflicts"
            / "memory-graph"
        )

    def resolved_inbox_dir(self) -> Path:
        """Resolve the inbox directory for remote-only records."""
        if self.inbox_dir is not None:
            return self.inbox_dir
        return self.workspace_root / "memory" / "inbox"


@dataclass
class SyncSourceRecord:
    """One parsed markdown-backed sync record."""

    workspace_id: str
    external_id: str
    source_path: str
    file_path: Path
    record_type: str
    title: str
    content: str
    tags: List[str]
    content_checksum: str
    external_updated_at: datetime
    external_revision: str
    marker_present: bool
    span_start: int
    span_end: int
    heading_level: int
    heading_end: int
    record_kind: str = "heading"
    item_indent: str = ""
    item_bullet: str = "-"
    heading_path: List[str] = field(default_factory=list)

    @property
    def is_file_level(self) -> bool:
        """Whether this record represents a whole-file block."""
        return self.heading_level == 0 and not self.is_list_item

    @property
    def is_list_item(self) -> bool:
        """Whether this record is backed by one markdown list item."""
        return self.record_kind == "list_item"


@dataclass
class WorkspaceSnapshot:
    """Full scan output for one workspace."""

    workspace_root: Path
    records: List[SyncSourceRecord] = field(default_factory=list)

    @property
    def by_external_id(self) -> Dict[str, SyncSourceRecord]:
        """Index records by external ID."""
        return {record.external_id: record for record in self.records}


@dataclass
class SyncStateRecord:
    """Persisted per-record sync state."""

    external_id: str
    source_path: str
    last_checksum: str
    last_seen_server_version: Optional[int] = None
    last_client_mutation_id: Optional[str] = None
    memory_id: Optional[str] = None
    marker_present: bool = False
    sync_status: str = "synced"

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SyncStateRecord":
        """Deserialize from JSON data."""
        return cls(**payload)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON persistence."""
        return asdict(self)


@dataclass
class SyncState:
    """Persisted workspace-level sync state."""

    workspace_id: str
    last_pulled_seq: int = 0
    records: Dict[str, SyncStateRecord] = field(default_factory=dict)
    recent_mutation_ids: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SyncState":
        """Deserialize from JSON data."""
        records = {
            external_id: SyncStateRecord.from_dict(record_payload)
            for external_id, record_payload in payload.get("records", {}).items()
        }
        return cls(
            workspace_id=payload["workspace_id"],
            last_pulled_seq=payload.get("last_pulled_seq", 0),
            records=records,
            recent_mutation_ids=list(payload.get("recent_mutation_ids", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON persistence."""
        return {
            "workspace_id": self.workspace_id,
            "last_pulled_seq": self.last_pulled_seq,
            "records": {
                external_id: record.to_dict()
                for external_id, record in self.records.items()
            },
            "recent_mutation_ids": list(self.recent_mutation_ids),
        }
