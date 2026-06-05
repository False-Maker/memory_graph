"""Directory scan/import routes for v1 data API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.routes.collectors_scan import (
    DirectoryScanRequest,
    ScanResult,
    import_scan_results,
    perform_directory_scan,
)
from src.api.routes.data.deps import get_detector, get_memory_service
from src.api.routes.data.import_run_store import record_import_run
from src.api.security import resolve_allowed_path
from src.api.routes.data_helpers import build_conversation_metadata

router = APIRouter(prefix="/api/v1/data", tags=["data"])


class DataDirectoryRequest(BaseModel):
    """Request payload for v1 directory scan/import endpoints."""

    directory_path: str = Field(..., min_length=1)
    recursive: bool = True
    extensions: list[str] = Field(default_factory=lambda: [".txt", ".md", ".json", ".jsonl"])
    include_patterns: list[str] | None = None
    skip_patterns: list[str] | None = None
    import_retries: int = Field(default=1, ge=0, le=5)


def _to_scan_request(request: DataDirectoryRequest) -> DirectoryScanRequest:
    return DirectoryScanRequest(
        directory=request.directory_path,
        recursive=request.recursive,
        extensions=request.extensions,
        include_patterns=request.include_patterns,
        skip_patterns=request.skip_patterns,
        import_retries=request.import_retries,
    )


def _record_import_run_safe(payload: dict[str, object]) -> None:
    try:
        record_import_run(payload)
    except Exception:
        # History tracking must never break API behavior.
        return


def _build_retry_request(request: DataDirectoryRequest) -> dict[str, object]:
    return request.model_dump(mode="python")


@router.post("/scan-directory", response_model=ScanResult)
async def scan_directory(request: DataDirectoryRequest):
    """Scan directory and classify importable conversation files."""
    try:
        return await perform_directory_scan(_to_scan_request(request))
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"Directory not found: {exc.args[0]}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _import_scanned_file(file_path: str):
    """Import one scanned file through the data memory service."""
    detector = get_detector()
    service = get_memory_service()

    resolved_file_path = resolve_allowed_path(file_path)
    content = resolved_file_path.read_bytes()
    conversations, platform = detector.parse_file(content, str(resolved_file_path))
    if not conversations:
        raise ValueError("no valid conversations found")

    imported = 0
    for conversation in conversations:
        metadata = build_conversation_metadata(conversation, platform)
        await service.ingest_memory(
            content=conversation.to_memory_content(),
            metadata=metadata,
            source_system=conversation.platform.value,
        )
        imported += 1

    return {"imported_memories": imported}


@router.post("/import-directory")
async def import_directory(request: DataDirectoryRequest):
    """Scan and batch import conversations from a directory."""
    return await run_directory_import(request)


async def run_directory_import(
    request: DataDirectoryRequest,
    *,
    retry_of: str | None = None,
):
    """Run one directory import and persist a retryable history record."""
    try:
        scan_response = await perform_directory_scan(_to_scan_request(request))
        result = await import_scan_results(
            scan_response=scan_response,
            import_file=_import_scanned_file,
            retries=request.import_retries,
        )
        _record_import_run_safe(
            {
                "status": str(result.get("status") or "completed"),
                "run_type": "directory_import",
                "source": "data/import-directory",
                "source_path": request.directory_path,
                "directory_path": request.directory_path,
                "filename": request.directory_path,
                "message": result.get("message"),
                "imported": int(result.get("imported", 0) or 0),
                "attempted": int(result.get("attempted", 0) or 0),
                "failed": int(result.get("failed", 0) or 0),
                "skipped": int(result.get("skipped", 0) or 0),
                "detail": f"directory_path={request.directory_path}",
                "retryable": True,
                "retry_request": _build_retry_request(request),
                "retry_of": retry_of,
            }
        )
        return result
    except FileNotFoundError as exc:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "directory_import",
                "source": "data/import-directory",
                "source_path": request.directory_path,
                "directory_path": request.directory_path,
                "filename": request.directory_path,
                "message": f"Directory not found: {exc.args[0]}",
                "imported": 0,
                "attempted": 0,
                "failed": 1,
                "skipped": 0,
                "error": str(exc),
                "detail": f"directory_path={request.directory_path}",
                "retryable": True,
                "retry_request": _build_retry_request(request),
                "retry_of": retry_of,
            }
        )
        raise HTTPException(status_code=400, detail=f"Directory not found: {exc.args[0]}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "directory_import",
                "source": "data/import-directory",
                "source_path": request.directory_path,
                "directory_path": request.directory_path,
                "filename": request.directory_path,
                "message": "Directory import failed",
                "imported": 0,
                "attempted": 0,
                "failed": 1,
                "skipped": 0,
                "error": str(exc),
                "detail": f"directory_path={request.directory_path}",
                "retryable": True,
                "retry_request": _build_retry_request(request),
                "retry_of": retry_of,
            }
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
