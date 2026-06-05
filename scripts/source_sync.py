#!/usr/bin/env python3
"""CLI for the external source sync client."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.sync.source_models import SyncSourceConfig
from src.core.sync.sync_worker import SourceSyncWorker

WORKSPACE_MAIN_ID = "workspace-main"
WORKSPACE_MAIN_ROOT = Path.home() / ".openclaw" / WORKSPACE_MAIN_ID
WORKSPACE_MAIN_SENTINELS = ("SOUL.md", "USER.md", "MEMORY.md", "memory")
PROTECTED_COMMANDS = {"push", "pull", "sync", "bootstrap", "restore"}


def load_workspace_profile(workspace_id: str) -> Dict[str, Any]:
    """Load optional workspace-local Memory Graph config."""
    path = Path.home() / ".openclaw" / workspace_id / "config" / "memory-graph.json"
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid workspace config at {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid workspace config at {path}: top-level JSON must be an object")
    return payload


def resolve_setting(
    cli_value: Any,
    env_key: str,
    profile: Dict[str, Any],
    profile_keys: tuple[str, ...],
    default: Any,
) -> Any:
    """Resolve one setting from CLI, env, workspace config, then fallback."""
    if cli_value not in (None, ""):
        return cli_value

    env_value = os.getenv(env_key)
    if env_value not in (None, ""):
        return env_value

    for key in profile_keys:
        value = profile.get(key)
        if value not in (None, ""):
            return value

    return default


def resolve_timeout(cli_value: float | None, profile: Dict[str, Any]) -> float:
    """Resolve timeout and coerce it to float."""
    raw = resolve_setting(
        cli_value,
        "MEMORY_GRAPH_TIMEOUT",
        profile,
        ("timeout", "timeout_seconds"),
        30.0,
    )
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid timeout value: {raw!r}") from exc


def resolve_workspace_root(args: argparse.Namespace) -> Path:
    """Resolve the workspace root with a safe default for workspace-main."""
    if args.workspace_root:
        return Path(args.workspace_root).resolve()

    if args.workspace_id == WORKSPACE_MAIN_ID and WORKSPACE_MAIN_ROOT.exists():
        return WORKSPACE_MAIN_ROOT.resolve()

    return Path(".").resolve()


def build_config(args: argparse.Namespace) -> SyncSourceConfig:
    """Build client config from CLI args."""
    profile = load_workspace_profile(args.workspace_id)
    workspace_root = resolve_workspace_root(args)
    return SyncSourceConfig(
        workspace_root=workspace_root,
        source_system="external",
        workspace_id=args.workspace_id,
        api_url=resolve_setting(
            args.api_url,
            "MEMORY_GRAPH_URL",
            profile,
            ("api_url", "url"),
            "http://127.0.0.1:8000",
        ),
        api_key=resolve_setting(
            args.api_key,
            "MEMORY_GRAPH_API_KEY",
            profile,
            ("api_key",),
            None,
        ),
        timeout_seconds=resolve_timeout(args.timeout, profile),
        state_path=Path(args.state_path).resolve() if args.state_path else None,
        conflicts_dir=Path(args.conflicts_dir).resolve() if args.conflicts_dir else None,
        inbox_dir=Path(args.inbox_dir).resolve() if args.inbox_dir else None,
    )


def ensure_workspace_main_guard(args: argparse.Namespace, config: SyncSourceConfig):
    """Require an explicit confirmation before mutating workspace-main."""
    if config.workspace_id != WORKSPACE_MAIN_ID:
        return

    expected_root = WORKSPACE_MAIN_ROOT.resolve() if WORKSPACE_MAIN_ROOT.exists() else None
    if expected_root is not None and config.workspace_root.resolve() != expected_root:
        raise SystemExit(
            "Refusing to run workspace-main sync against a non-canonical root: "
            f"{config.workspace_root} != {expected_root}"
        )

    missing = []
    for name in WORKSPACE_MAIN_SENTINELS:
        target = config.workspace_root / name
        if name == "memory":
            if not target.is_dir():
                missing.append(name)
        elif not target.exists():
            missing.append(name)
    if missing:
        raise SystemExit(
            "Refusing to run workspace-main sync because the workspace root "
            f"{config.workspace_root} is missing sentinels: {', '.join(missing)}"
        )

    if args.command not in PROTECTED_COMMANDS:
        return

    if getattr(args, "dry_run", False) or getattr(args, "yes", False):
        return

    if not sys.stdin.isatty():
        raise SystemExit(
            f"Refusing to mutate {config.workspace_id} without --yes in non-interactive mode"
        )

    confirmation = input(
        f"About to run '{args.command}' against {config.workspace_root}. "
        f"Type '{config.workspace_id}' to continue: "
    ).strip()
    if confirmation != config.workspace_id:
        raise SystemExit("Workspace confirmation mismatch; aborting.")


def print_plan(args: argparse.Namespace, config: SyncSourceConfig, restore_only: bool) -> int:
    """Print a dry-run plan for bootstrap/restore."""
    worker = SourceSyncWorker(config)
    plan = worker.plan_push(restore_only=restore_only)
    print(
        json.dumps(
            {
                "command": args.command,
                "mode": "dry-run",
                "workspace_root": str(config.workspace_root),
                "workspace_id": config.workspace_id,
                "api_url": config.api_url,
                "state_path": str(config.resolved_state_path()),
                "scanned_records": plan.scanned_records,
                "pending_records": plan.pending_records,
                "restore_candidates": plan.restore_candidates,
                "marker_candidates": plan.marker_candidates,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


async def main_async(args: argparse.Namespace) -> int:
    """Run the selected CLI command."""
    config = build_config(args)
    ensure_workspace_main_guard(args, config)

    if args.command == "scan":
        worker = SourceSyncWorker(config)
        snapshot = worker.scan()
        print(
            json.dumps(
                {
                    "workspace_root": str(config.workspace_root),
                    "workspace_id": config.workspace_id,
                    "record_count": len(snapshot.records),
                    "records": [
                        {
                            "external_id": record.external_id,
                            "source_path": record.source_path,
                            "record_type": record.record_type,
                            "title": record.title,
                            "marker_present": record.marker_present,
                        }
                        for record in snapshot.records
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "push":
        worker = SourceSyncWorker(config)
        summary = await worker.push(
            batch_size=args.batch_size,
            reconcile=not args.no_reconcile,
            delete_missing=not args.no_delete_missing,
        )
        print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
        return 0

    if args.command == "pull":
        worker = SourceSyncWorker(config)
        summary = await worker.pull(limit=args.limit)
        print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
        return 0

    if args.command == "sync":
        worker = SourceSyncWorker(config)
        result = await worker.sync(batch_size=args.batch_size, change_limit=args.limit)
        print(
            json.dumps(
                {
                    "push": result["push"].__dict__,
                    "pull": result["pull"].__dict__,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "state":
        worker = SourceSyncWorker(config)
        print(json.dumps(worker.get_local_state().to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "bootstrap":
        if getattr(args, "dry_run", False):
            return print_plan(args, config, restore_only=False)

        worker = SourceSyncWorker(config)
        summary = await worker.bootstrap(batch_size=args.batch_size)
        print(
            json.dumps(
                {
                    "command": "bootstrap",
                    "workspace_root": str(config.workspace_root),
                    **summary.__dict__,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "restore":
        if getattr(args, "dry_run", False):
            return print_plan(args, config, restore_only=True)

        worker = SourceSyncWorker(config)
        summary = await worker.restore(batch_size=args.batch_size)
        print(
            json.dumps(
                {
                    "command": "restore",
                    "workspace_root": str(config.workspace_root),
                    **summary.__dict__,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    raise ValueError(f"Unknown command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="External source <-> Memory Graph sync client")
    parser.add_argument("--workspace-root", default=None, help="Local source workspace root")
    parser.add_argument("--workspace-id", default="workspace-main", help="Workspace identifier")
    parser.add_argument("--api-url", default=None, help="Memory Graph API base URL")
    parser.add_argument("--api-key", default=None, help="Optional API key")
    parser.add_argument("--timeout", type=float, default=None, help="HTTP timeout in seconds")
    parser.add_argument("--state-path", default=None, help="Override local state file path")
    parser.add_argument("--conflicts-dir", default=None, help="Override conflicts directory")
    parser.add_argument("--inbox-dir", default=None, help="Override inbox directory")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the workspace-main confirmation prompt for mutating commands",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan the workspace and print parsed records")

    push_parser = subparsers.add_parser("push", help="Push local changes to the server")
    push_parser.add_argument("--batch-size", type=int, default=50)
    push_parser.add_argument("--no-reconcile", action="store_true")
    push_parser.add_argument("--no-delete-missing", action="store_true")

    pull_parser = subparsers.add_parser("pull", help="Pull remote changes into the workspace")
    pull_parser.add_argument("--limit", type=int, default=100)

    sync_parser = subparsers.add_parser("sync", help="Run push then pull")
    sync_parser.add_argument("--batch-size", type=int, default=50)
    sync_parser.add_argument("--limit", type=int, default=100)

    subparsers.add_parser("state", help="Print the local sync state file")

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Safely push the current workspace snapshot upstream without reconcile deletes",
    )
    bootstrap_parser.add_argument("--batch-size", type=int, default=10)
    bootstrap_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview bootstrap counts without mutating local or remote state",
    )

    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore records that are still marked deleted in the local sync state",
    )
    restore_parser.add_argument("--batch-size", type=int, default=10)
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview restore candidates without mutating local or remote state",
    )
    return parser


def main() -> int:
    """Program entrypoint."""
    args = build_parser().parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
