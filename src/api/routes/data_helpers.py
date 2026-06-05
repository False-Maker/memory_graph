"""Helper functions for data management routes."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Iterable, Sequence

from src.api.schemas.memory import ConversationImportResponse, ConversationParseResult
from src.core.entity_detector_regex import ConversationEntityDetector

EXPORT_PAYLOAD_VERSION = 1
REGEX_ENTITY_HINT_TYPES = (
    "organization",
    "name",
    "email",
    "url",
    "file_path",
    "uuid",
    "phone",
    "ip_address",
)
REGEX_ENTITY_MAX_HINTS = 24


def build_export_payload(
    memories: Iterable[Any],
    entities: Iterable[Any],
    relationships: Iterable[Any],
) -> dict[str, Any]:
    """Serialize memory, entity, and relationship collections for export."""
    serialized_memories = [
        {
            "id": memory.id,
            "content": memory.content,
            "metadata": memory.metadata,
        }
        for memory in memories
    ]
    serialized_entities = [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "properties": entity.properties,
            "source_text": entity.source_text,
        }
        for entity in entities
    ]
    serialized_relationships = [
        {
            "id": relationship.id,
            "source_id": relationship.source_id,
            "target_id": relationship.target_id,
            "type": relationship.type,
            "properties": relationship.properties,
        }
        for relationship in relationships
    ]

    return {
        "manifest": {
            "format": "memory_graph_export",
            "version": EXPORT_PAYLOAD_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "memories": len(serialized_memories),
                "entities": len(serialized_entities),
                "relationships": len(serialized_relationships),
            },
        },
        "memories": serialized_memories,
        "entities": serialized_entities,
        "relationships": serialized_relationships,
    }


def _render_memory_content(conversation: Any, output_format: str) -> str:
    """Convert a parsed conversation into persisted memory content."""
    if output_format == "plain_text":
        return conversation.to_plain_text()
    return conversation.to_memory_content()


def _normalize_message_payload(conversation: Any) -> list[dict[str, str]]:
    """Normalize conversation messages for regex entity detection."""
    normalized_messages = []

    for message in getattr(conversation, "messages", []) or []:
        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        else:
            role = getattr(message, "role", None)
            content = getattr(message, "content", None)

        text = str(content or "").strip()
        if not text:
            continue

        normalized_messages.append(
            {
                "role": str(role or "user"),
                "content": text,
            }
        )

    return normalized_messages


def _build_regex_entity_hints(conversation: Any) -> list[dict[str, Any]]:
    """Extract conservative regex entity hints from conversation messages."""
    messages = _normalize_message_payload(conversation)
    if not messages:
        return []

    detector = ConversationEntityDetector(min_frequency=1)
    raw_entities = detector.process_conversation(messages)
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}

    for entity_type in REGEX_ENTITY_HINT_TYPES:
        for entity in raw_entities.get(entity_type, []):
            raw_text = str(entity.get("text") or "").strip()
            normalized_text = " ".join(raw_text.split()).lower()
            if not normalized_text:
                continue

            key = (normalized_text, entity_type)
            current = aggregated.get(key)
            if current is None:
                current = {
                    "text": raw_text,
                    "type": entity_type,
                    "frequency": 0,
                    "confidence": float(entity.get("confidence", 0.0) or 0.0),
                    "context": entity.get("context"),
                    "message_indexes": [],
                    "message_roles": [],
                    "detection_method": "regex",
                }
                aggregated[key] = current

            current["frequency"] += 1
            current["confidence"] = max(current["confidence"], float(entity.get("confidence", 0.0) or 0.0))

            message_index = entity.get("message_index")
            if isinstance(message_index, int) and message_index not in current["message_indexes"]:
                current["message_indexes"].append(message_index)

            message_role = str(entity.get("message_role") or "").strip()
            if message_role and message_role not in current["message_roles"]:
                current["message_roles"].append(message_role)

    filtered_hints = [
        item
        for item in aggregated.values()
        if int(item.get("frequency", 0) or 0) >= (2 if item["type"] in {"name", "organization"} else 1)
    ]

    hints = sorted(
        filtered_hints,
        key=lambda item: (
            -int(item.get("frequency", 0) or 0),
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("text") or "").lower(),
        ),
    )
    return hints[:REGEX_ENTITY_MAX_HINTS]


def build_conversation_metadata(conversation: Any, platform: str) -> dict[str, Any]:
    """Build persistence metadata for an imported conversation."""
    conversation_id = conversation.metadata.get("conversation_id")
    metadata = {
        "source": conversation.platform.value,
        "title": conversation.title,
        "platform": platform,
        "conversation_id": conversation_id,
        "external_id": (
            f"{conversation.platform.value}:default:{conversation_id}"
            if conversation_id
            else None
        ),
        "workspace_id": "default",
        "record_type": "conversation",
        "timestamp": conversation.created_at,
    }

    regex_entity_hints = _build_regex_entity_hints(conversation)
    if regex_entity_hints:
        metadata["regex_entity_hints"] = regex_entity_hints
        metadata["entity_detection"] = {
            "regex_hint_count": len(regex_entity_hints),
            "regex_hint_types": sorted({item["type"] for item in regex_entity_hints}),
        }

    return metadata


async def build_conversation_import_response(
    *,
    conversations: Sequence[Any],
    platform: str,
    output_format: str,
    service: Any,
    started_at: float,
) -> ConversationImportResponse:
    """Import parsed conversations and serialize the response payload."""
    parsed_results = []
    imported_count = 0
    failed_count = 0

    for conversation in conversations:
        try:
            memory_content = _render_memory_content(conversation, output_format)
            metadata = build_conversation_metadata(conversation, platform)

            result = await service.ingest_memory(
                content=memory_content,
                metadata=metadata,
                source_system=conversation.platform.value,
            )

            preview = memory_content[:200].replace("\n", " ")
            parsed_results.append(
                ConversationParseResult(
                    conversation_id=metadata["conversation_id"] or result.memory_id,
                    title=conversation.title or "Untitled",
                    platform=platform,
                    message_count=len(conversation.messages),
                    created_at=conversation.created_at,
                    preview=preview,
                )
            )
            imported_count += 1
        except Exception:
            failed_count += 1

    return ConversationImportResponse(
        success=True,
        parsed_conversations=parsed_results,
        imported_memories=imported_count,
        failed_count=failed_count,
        platform=platform,
        processing_time_ms=int((time.time() - started_at) * 1000),
    )
