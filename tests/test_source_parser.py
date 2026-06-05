"""Tests for the generic markdown source parser."""

from pathlib import Path

from src.core.sync.source_models import SyncSourceConfig
from src.core.sync.source_parser import WorkspaceSourceParser


class TestWorkspaceSourceParser:
    """Markdown parsing and marker writeback."""

    def test_scan_workspace_parses_leaf_records_and_generates_ids(self, temp_dir):
        """Container headings should be skipped while leaf records are synced."""
        workspace = temp_dir
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "2026-03-23.md").write_text(
            "# 2026-03-23\n\n"
            "## Decisions\n\n"
            "### Choose PostgreSQL\n"
            "Use PostgreSQL as the main database. #database\n\n"
            "### Keep Redis Cache\n"
            "<!-- mg:id=external:workspace-main:decision_fixed -->\n\n"
            "Redis remains the cache layer.\n",
            encoding="utf-8",
        )

        parser = WorkspaceSourceParser(
            SyncSourceConfig(workspace_root=workspace, workspace_id="workspace-main")
        )
        snapshot = parser.scan_workspace()

        assert len(snapshot.records) == 2
        first = snapshot.records[0]
        second = snapshot.records[1]
        assert first.record_type == "decision"
        assert first.marker_present is False
        assert first.external_id.startswith("external:workspace-main:decision_")
        assert first.tags == ["database"]
        assert second.external_id == "external:workspace-main:decision_fixed"
        assert second.marker_present is True
        assert first.record_kind == "heading"

    def test_memory_digest_sections_are_itemized_by_bullet(self, temp_dir):
        """MEMORY.md Decisions/Preferences/Important Events should sync as list items."""
        workspace = temp_dir
        target = workspace / "MEMORY.md"
        target.write_text(
            "# MEMORY.md\n\n"
            "## Decisions\n"
            "- [2026-03-23] Choose PostgreSQL (source: memory/2026-03-23.md)\n"
            "<!-- mg:id=external:workspace-main:item_fixed -->\n"
            "- [2026-03-23] Keep Redis cache (source: memory/2026-03-23.md)\n\n"
            "## Preferences\n"
            "- Prefer explicit API contracts #api\n",
            encoding="utf-8",
        )

        parser = WorkspaceSourceParser(
            SyncSourceConfig(workspace_root=workspace, workspace_id="workspace-main")
        )
        records = parser.scan_workspace().records

        assert len(records) == 3
        assert [record.record_type for record in records] == ["decision", "decision", "preference"]
        assert all(record.record_kind == "list_item" for record in records)
        assert records[0].title == "Choose PostgreSQL"
        assert records[1].external_id == "external:workspace-main:item_fixed"
        assert records[2].tags == ["api"]

    def test_weekly_summary_sections_are_itemized_by_bullet(self, temp_dir):
        """Weekly/monthly digest sections should also split bullet records."""
        workspace = temp_dir
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        target = memory_dir / "weekly-2026-W12.md"
        target.write_text(
            "# Weekly Memory Summary: 2026-W12\n\n"
            "## Snapshot\n"
            "- Decisions: 2\n\n"
            "## Decisions\n"
            "- [2026-03-23] Keep weekly summaries itemized.\n"
            "- [2026-03-23] Keep monthly summaries itemized.\n",
            encoding="utf-8",
        )

        parser = WorkspaceSourceParser(
            SyncSourceConfig(workspace_root=workspace, workspace_id="workspace-main")
        )
        records = parser.scan_workspace().records

        assert len(records) == 3
        assert records[0].title == "Snapshot"
        assert records[0].record_kind == "heading"
        assert records[1].record_type == "decision"
        assert records[1].record_kind == "list_item"
        assert records[2].record_type == "decision"

    def test_write_markers_inserts_marker_after_heading(self, temp_dir):
        """Missing markers should be written directly below the heading."""
        workspace = temp_dir
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        target = memory_dir / "2026-03-23.md"
        target.write_text(
            "# 2026-03-23\n\n"
            "## Decisions\n\n"
            "### Choose PostgreSQL\n"
            "Use PostgreSQL as the main database.\n",
            encoding="utf-8",
        )

        parser = WorkspaceSourceParser(
            SyncSourceConfig(workspace_root=workspace, workspace_id="workspace-main")
        )
        record = parser.scan_workspace().records[0]
        parser.write_markers([record])

        updated = target.read_text(encoding="utf-8")
        assert "### Choose PostgreSQL\n<!-- mg:id=" in updated

    def test_write_markers_skips_summary_list_items(self, temp_dir):
        """Derived summary files should not receive marker writeback."""
        workspace = temp_dir
        target = workspace / "MEMORY.md"
        target.write_text(
            "# MEMORY.md\n\n"
            "## Decisions\n"
            "- [2026-03-23] Choose PostgreSQL (source: memory/2026-03-23.md)\n",
            encoding="utf-8",
        )

        parser = WorkspaceSourceParser(
            SyncSourceConfig(workspace_root=workspace, workspace_id="workspace-main")
        )
        record = parser.scan_workspace().records[0]
        written = parser.write_markers([record])

        updated = target.read_text(encoding="utf-8")
        assert written == 0
        assert "<!-- mg:id=" not in updated
