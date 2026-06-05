"""CLI coverage for the generic workspace-main sync wrapper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "scripts" / "source_sync.py"


def create_workspace_main(home: Path) -> Path:
    """Create a minimal workspace-main fixture under one fake HOME."""
    workspace = home / ".openclaw" / "workspace-main"
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "SOUL.md").write_text("# SOUL\n", encoding="utf-8")
    (workspace / "USER.md").write_text("# USER\n", encoding="utf-8")
    (workspace / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
    return workspace


def run_cli(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI under one isolated HOME directory."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_workspace_main_bootstrap_dry_run_uses_canonical_root(temp_dir):
    """Bootstrap dry-run should auto-resolve the workspace-main root and scan it."""
    home = temp_dir / "home"
    workspace = create_workspace_main(home)
    (workspace / "memory" / "2026-03-25.md").write_text(
        "# 2026-03-25\n\n"
        "## Decisions\n\n"
        "### Add Safe Wrapper\n"
        "Ship explicit bootstrap and restore commands.\n",
        encoding="utf-8",
    )

    result = run_cli(home, "bootstrap", "--dry-run")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == "bootstrap"
    assert payload["mode"] == "dry-run"
    assert payload["workspace_root"] == str(workspace)
    assert payload["workspace_id"] == "workspace-main"
    assert payload["scanned_records"] == 2
    assert payload["pending_records"] == 2


def test_workspace_main_bootstrap_requires_yes_in_noninteractive_mode(temp_dir):
    """Mutating workspace-main commands should refuse to run without --yes."""
    home = temp_dir / "home"
    workspace = create_workspace_main(home)
    (workspace / "memory" / "2026-03-25.md").write_text(
        "# 2026-03-25\n\n"
        "## Decisions\n\n"
        "### Add Safe Wrapper\n"
        "Ship explicit bootstrap and restore commands.\n",
        encoding="utf-8",
    )

    result = run_cli(home, "bootstrap")

    assert result.returncode != 0
    assert "without --yes in non-interactive mode" in result.stderr
