"""Conflict file output for external source sync clients."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.sync.source_models import SyncSourceConfig


class SyncConflictStore:
    """Write human-readable conflict files."""

    def __init__(self, config: SyncSourceConfig):
        self.config = config

    def _sanitize_filename(self, external_id: str) -> str:
        """Make an external ID filesystem-safe."""
        return re.sub(r"[^a-zA-Z0-9._-]+", "_", external_id)

    def write_conflict(
        self,
        external_id: str,
        source_path: Optional[str],
        local_content: Optional[str],
        remote_record: Optional[Dict[str, Any]],
        server_version: Optional[int],
    ) -> Path:
        """Write one conflict file and return its path."""
        target_dir = self.config.resolved_conflicts_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{self._sanitize_filename(external_id)}.md"

        remote_payload = json.dumps(remote_record or {}, ensure_ascii=False, indent=2)
        body = (
            f"# Sync Conflict\n\n"
            f"- external_id: `{external_id}`\n"
            f"- source_path: `{source_path or ''}`\n"
            f"- server_version: `{server_version if server_version is not None else ''}`\n\n"
            f"## Local Content\n\n"
            f"```md\n{(local_content or '').rstrip()}\n```\n\n"
            f"## Remote Record\n\n"
            f"```json\n{remote_payload}\n```\n"
        )
        path.write_text(body, encoding="utf-8")
        return path
