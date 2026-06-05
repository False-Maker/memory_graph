"""State persistence for external source sync clients."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.sync.source_models import SyncSourceConfig, SyncState, SyncStateRecord


class SyncStateStore:
    """Load and save the local sync state file."""

    def __init__(self, config: SyncSourceConfig, recent_mutation_limit: int = 512):
        self.config = config
        self.recent_mutation_limit = recent_mutation_limit
        self.path = config.resolved_state_path()

    def load(self) -> SyncState:
        """Load state from disk, or create an empty one."""
        if not self.path.exists():
            return SyncState(workspace_id=self.config.workspace_id)

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return SyncState.from_dict(payload)

    def save(self, state: SyncState):
        """Persist state to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def update_record(
        self,
        state: SyncState,
        record: SyncStateRecord,
    ):
        """Upsert one record entry into the state."""
        state.records[record.external_id] = record

    def remove_record(self, state: SyncState, external_id: str):
        """Remove one record entry from the state."""
        state.records.pop(external_id, None)

    def remember_mutation_id(self, state: SyncState, mutation_id: str):
        """Track recent client mutation IDs for echo dedupe."""
        if mutation_id in state.recent_mutation_ids:
            state.recent_mutation_ids.remove(mutation_id)
        state.recent_mutation_ids.append(mutation_id)
        if len(state.recent_mutation_ids) > self.recent_mutation_limit:
            state.recent_mutation_ids = state.recent_mutation_ids[-self.recent_mutation_limit :]

    def has_mutation_id(self, state: SyncState, mutation_id: str | None) -> bool:
        """Check whether a mutation ID is known locally."""
        if not mutation_id:
            return False
        return mutation_id in state.recent_mutation_ids
