"""Shared helpers for memory/sync graph evidence ingestion."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.core.entity_extractor import ExtractionResult
from src.core.graph_store_models import GraphEntity, GraphRelationship
from src.core.sync.models import CanonicalGraphPayload


class IngestTextUtils:
    """Normalize text and serialize shared ingest payloads."""

    def __init__(self, embedding_text_max_chars: int) -> None:
        self._embedding_text_max_chars = embedding_text_max_chars

    def stable_hash(self, prefix: str, *parts: str) -> str:
        """Build a stable prefixed SHA256 hash."""
        raw = "|".join(parts).encode("utf-8")
        return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"

    @staticmethod
    def normalize_text(value: Optional[str]) -> str:
        """Normalize text for canonical comparisons."""
        return " ".join((value or "").strip().lower().split())

    @staticmethod
    def serialize_json(value: Any) -> str:
        """Serialize JSON content consistently."""
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        """Serialize an optional datetime to ISO-8601."""
        return value.isoformat() if value else None

    def embedding_text(self, content: Optional[str]) -> str:
        """Trim oversized content before sending it to the embedding provider."""
        text = (content or "").strip()
        if len(text) <= self._embedding_text_max_chars:
            return text
        return text[: self._embedding_text_max_chars].rstrip()

    def should_extract_graph_evidence(
        self,
        source_path: Optional[str],
        *,
        skip_extraction: bool = False,
    ) -> bool:
        """Skip graph extraction for generated summary artifacts or explicit metadata."""
        if skip_extraction:
            return False
        if not source_path:
            return True
        filename = Path(source_path).name.lower()
        return not (
            source_path == "MEMORY.md"
            or filename.startswith("weekly-")
            or filename.startswith("monthly-")
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}-.+\.md", filename)
        )


class CanonicalGraphEvidenceBuilder:
    """Canonicalize extracted entities/relationships for persisted graph evidence."""

    def __init__(
        self,
        *,
        normalize_text: Callable[[Optional[str]], str],
        stable_hash: Callable[..., str],
    ) -> None:
        self._normalize_text = normalize_text
        self._stable_hash = stable_hash

    def canonicalize_extraction(
        self,
        *,
        extraction: ExtractionResult,
        content: str,
        created_at: str,
    ) -> CanonicalGraphPayload:
        """Canonicalize extracted graph evidence into stable persisted rows."""
        entity_map: Dict[str, GraphEntity] = {}
        original_to_canonical: Dict[str, str] = {}
        mentions: Dict[str, Dict[str, Any]] = {}

        for entity in extraction.entities:
            name = (entity.name or "").strip()
            if not name:
                continue

            entity_type = self._normalize_text(entity.type) or "concept"
            canonical_id = self._stable_hash(
                "ent",
                self._normalize_text(name),
                entity_type,
            )
            original_to_canonical[entity.id] = canonical_id

            existing_entity = entity_map.get(canonical_id)
            if existing_entity is None or entity.confidence >= existing_entity.confidence:
                entity_map[canonical_id] = GraphEntity(
                    id=canonical_id,
                    name=name,
                    type=entity_type,
                    properties=entity.properties or {},
                    source_text=content[:500],
                    confidence=entity.confidence,
                    created_at=entity.created_at,
                )

            mentions[canonical_id] = {
                "entity_id": canonical_id,
                "mention_text": name,
                "confidence": entity.confidence,
                "created_at": created_at,
            }

        relationship_map: Dict[str, GraphRelationship] = {}
        relationship_evidence: Dict[str, Dict[str, Any]] = {}

        for rel in extraction.relationships:
            source_id = original_to_canonical.get(rel.source_id)
            target_id = original_to_canonical.get(rel.target_id)
            if not source_id or not target_id:
                continue

            rel_type = self._normalize_text(rel.type) or "related_to"
            canonical_rel_id = self._stable_hash("rel", source_id, rel_type, target_id)

            existing_rel = relationship_map.get(canonical_rel_id)
            if existing_rel is None or rel.confidence >= existing_rel.confidence:
                relationship_map[canonical_rel_id] = GraphRelationship(
                    id=canonical_rel_id,
                    source_id=source_id,
                    target_id=target_id,
                    type=rel_type,
                    properties=rel.properties or {},
                    confidence=rel.confidence,
                    created_at=rel.created_at,
                )

            relationship_evidence[canonical_rel_id] = {
                "relationship_id": canonical_rel_id,
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "relationship_type": rel_type,
                "confidence": rel.confidence,
                "created_at": created_at,
            }

        return CanonicalGraphPayload(
            entities=list(entity_map.values()),
            mentions=list(mentions.values()),
            relationships=list(relationship_map.values()),
            relationship_evidence=list(relationship_evidence.values()),
        )
