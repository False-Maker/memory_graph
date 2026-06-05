"""Security helpers for API authentication and local file boundaries."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from src.core.config import get_settings

PUBLIC_PATHS = {
    "/",
    "/health",
    "/ready",
    "/favicon.ico",
}


def _normalized_header_token(header_value: str | None) -> str:
    if not header_value:
        return ""
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def _is_static_asset_path(path: str) -> bool:
    return path.startswith("/assets/") or path.startswith("/static/")


def is_public_request_path(path: str) -> bool:
    """Return whether a request path is intentionally public."""
    if path in PUBLIC_PATHS:
        return True
    return _is_static_asset_path(path)


async def enforce_api_auth(request: Request, call_next):
    """Require a configured Bearer token for non-public HTTP endpoints."""
    if request.method == "OPTIONS":
        return await call_next(request)

    settings = get_settings()
    if not settings.app.api_auth_enabled or is_public_request_path(request.url.path):
        return await call_next(request)

    expected_token = settings.app.api_token
    presented_token = _normalized_header_token(request.headers.get("authorization"))
    if not expected_token or not hmac.compare_digest(presented_token, expected_token):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


def resolve_allowed_path(raw_path: str, *, allowed_roots: Iterable[str] | None = None) -> Path:
    """Resolve a user-supplied path and require it to stay inside configured roots."""
    value = (raw_path or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Path must not be empty")

    candidate = Path(value).expanduser().resolve()
    raw_allowed_roots = list(allowed_roots if allowed_roots is not None else get_settings().app.allowed_file_roots)
    resolved_roots = [Path(root).expanduser().resolve() for root in raw_allowed_roots if str(root).strip()]
    if not resolved_roots:
        raise HTTPException(status_code=500, detail="No allowed file roots configured")

    if not any(candidate == root or candidate.is_relative_to(root) for root in resolved_roots):
        raise HTTPException(
            status_code=403,
            detail="Path is outside configured allowed file roots",
        )

    return candidate


async def read_upload_file_limited(file: UploadFile, *, max_bytes: int | None = None) -> bytes:
    """Read an UploadFile with a hard maximum size."""
    limit = max_bytes if max_bytes is not None else get_settings().app.max_upload_bytes
    if limit <= 0:
        raise HTTPException(status_code=500, detail="Invalid max upload size")

    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file is too large; max size is {limit} bytes",
        )
    return content
