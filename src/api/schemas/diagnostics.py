"""Shared response diagnostics schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CollectionDiagnostics(BaseModel):
    """Cross-endpoint diagnostics for filtered or paginated result sets."""

    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    server_side_filtered: bool = False
    truncated: bool = False
    candidate_window: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
