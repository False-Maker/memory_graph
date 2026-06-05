"""Directory scan/import helpers for collectors routes."""

from __future__ import annotations

import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import BaseModel

from src.api.security import resolve_allowed_path
from src.core.parsers import get_detector


class DirectoryScanRequest(BaseModel):
    """Directory scan request payload."""

    directory: str
    recursive: bool = True
    extensions: Optional[List[str]] = [".txt", ".md", ".json", ".jsonl"]
    include_patterns: Optional[List[str]] = None
    skip_patterns: Optional[List[str]] = None
    import_retries: int = 1


class ScanResult(BaseModel):
    """Directory scan result."""

    total_files: int
    conversation_files: List[Dict[str, Any]]
    skipped_files: List[Dict[str, Any]]
    errors: List[str]


async def perform_directory_scan(request: DirectoryScanRequest) -> ScanResult:
    """Scan a directory tree and classify importable conversation files."""
    detector = get_detector()
    conversation_files: List[Dict[str, Any]] = []
    skipped_files: List[Dict[str, Any]] = []
    errors: List[str] = []

    skip_patterns = request.skip_patterns or [
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".cache",
    ]

    def should_skip(path: str) -> bool:
        path_normalized = path.replace("\\", "/")
        return any(pattern in path_normalized for pattern in skip_patterns)

    def matches_include_patterns(path: str) -> bool:
        if not request.include_patterns:
            return True

        path_normalized = path.replace("\\", "/")
        for pattern in request.include_patterns:
            pattern_normalized = pattern.replace("\\", "/")
            if pattern_normalized.startswith("**/"):
                if pattern_normalized[3:] in path_normalized:
                    return True
            elif pattern_normalized in path_normalized:
                return True
        return False

    root_directory = resolve_allowed_path(request.directory)

    def scan_dir(directory: str) -> None:
        try:
            for entry in os.scandir(directory):
                full_path = entry.path

                if should_skip(full_path):
                    skipped_files.append(
                        {
                            "path": full_path,
                            "reason": "matches skip pattern",
                        }
                    )
                    continue

                if not matches_include_patterns(full_path):
                    skipped_files.append(
                        {
                            "path": full_path,
                            "reason": "does not match include patterns",
                        }
                    )
                    continue

                if entry.is_dir() and request.recursive:
                    scan_dir(full_path)
                    continue

                if not entry.is_file():
                    continue

                ext = os.path.splitext(full_path)[1].lower()
                if ext not in (request.extensions or []):
                    skipped_files.append(
                        {
                            "path": full_path,
                            "reason": f"extension {ext} not in list",
                        }
                    )
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
                        content = handle.read()

                    if not content.strip():
                        skipped_files.append(
                            {
                                "path": full_path,
                                "reason": "empty file",
                            }
                        )
                        continue

                    try:
                        platform = detector.detect_platform(content)
                        if platform and platform.value != "unknown":
                            conversation_files.append(
                                {
                                    "path": full_path,
                                    "format": platform.value,
                                    "size": len(content),
                                    "preview": content[:200],
                                }
                            )
                        else:
                            skipped_files.append(
                                {
                                    "path": full_path,
                                    "reason": "not a recognized conversation format",
                                }
                            )
                    except Exception:
                        conversation_files.append(
                            {
                                "path": full_path,
                                "format": "text",
                                "size": len(content),
                                "preview": content[:200],
                            }
                        )
                except Exception as exc:
                    errors.append(f"Error reading {full_path}: {exc}")
        except PermissionError:
            errors.append(f"Permission denied: {directory}")
        except Exception as exc:
            errors.append(f"Error scanning {directory}: {exc}")

    if not root_directory.is_dir():
        raise FileNotFoundError(str(root_directory))

    scan_dir(str(root_directory))

    return ScanResult(
        total_files=len(conversation_files) + len(skipped_files),
        conversation_files=conversation_files,
        skipped_files=skipped_files[:50],
        errors=errors,
    )


async def import_scan_results(
    scan_response: ScanResult,
    import_file: Callable[[str], Awaitable[Any]],
    retries: int = 1,
) -> Dict[str, Any]:
    """Import scanned conversation files via a provided async importer."""
    if not scan_response.conversation_files:
        return {
            "status": "no_files",
            "message": "No conversation files found in the directory",
            "imported": 0,
            "skipped": len(scan_response.skipped_files),
            "attempted": 0,
            "duplicates_skipped": 0,
            "retryable_failed_files": [],
            "retryable_count": 0,
        }

    imported_count = 0
    failed_files: List[Dict[str, Any]] = []
    retryable_failed_files: List[Dict[str, Any]] = []
    deduped_files: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()
    max_retries = max(0, retries)

    for file_info in scan_response.conversation_files:
        file_path = file_info["path"]
        normalized = str(file_path).replace("\\", "/").lower()
        if normalized in seen_paths:
            deduped_files.append(
                {
                    "path": file_path,
                    "reason": "duplicate conversation file in scan result",
                }
            )
            continue
        seen_paths.add(normalized)

        last_error: Optional[str] = None
        attempts = 0
        max_attempts = max_retries + 1

        while attempts < max_attempts:
            attempts += 1
            try:
                result = await import_file(file_path)
                if result:
                    imported_count += 1
                    last_error = None
                    break
                last_error = "import returned None"
            except Exception as exc:
                last_error = str(exc)

        if last_error is not None:
            failure_record = {
                "path": file_path,
                "reason": last_error,
                "attempts": attempts,
                "retry_exhausted": attempts > 1,
            }
            failed_files.append(failure_record)
            retryable_failed_files.append(failure_record)

    attempted = len(seen_paths)
    skipped_total = len(scan_response.skipped_files) + len(deduped_files)

    return {
        "status": "completed",
        "message": f"Imported {imported_count} conversations",
        "imported": imported_count,
        "attempted": attempted,
        "failed": len(failed_files),
        "failed_files": failed_files,
        "skipped": skipped_total,
        "duplicates_skipped": len(deduped_files),
        "retryable_failed_files": retryable_failed_files,
        "retryable_count": len(retryable_failed_files),
        "total_scanned": scan_response.total_files,
    }
