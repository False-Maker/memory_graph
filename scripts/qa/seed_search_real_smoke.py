#!/usr/bin/env python3
"""Seed one deterministic Search -> Memory -> Community fixture into the temp workspace."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.core.config import Settings
from src.core.entity_extractor import Entity, ExtractionResult, Relationship
from src.core.graph_store import GraphStore
from src.core.graph_store_models import GraphEntity
from src.core.memory_service import MemoryService
from src.core.models.community import Community
from src.core.vector_store import VectorStore


class FakeLLM:
    async def embed(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


async def _seed() -> None:
    workspace_root = Path.cwd()
    vector_dir = workspace_root / "data" / "faiss-search-real-smoke"
    profile = os.environ.get("SEED_PROFILE", "basic").strip() or "basic"
    created_at = datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc)
    seed_without_memory = False
    manual_entities: list[GraphEntity] = []
    runtime_settings = Settings(
        llm={"provider": "ollama"},
        embedding={
            "model": "search-real-smoke-embedding",
            "dimensions": 4,
            "cloud_dimensions": 4,
            "provider_preference": "remote_only",
        },
        database={
            "vector": {
                "type": "faiss",
                "faiss": {"persist_directory": str(vector_dir)},
            }
        },
        app={"host": "127.0.0.1", "port": 8000},
    )

    if profile == "large_summary":
        content = "Alice coordinates the launch checklist, release runbook, integration tests, and rollout approvals."
        title = "Launch coordination dossier"
        extracted_entities = [
            Entity(
                id="raw-alice",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text=content,
                confidence=0.97,
                created_at=created_at,
            ),
            Entity(
                id="raw-launch-checklist",
                name="Launch Checklist",
                type="document",
                properties={"status": "active"},
                source_text=content,
                confidence=0.95,
                created_at=created_at,
            ),
            Entity(
                id="raw-release-runbook",
                name="Release Runbook",
                type="document",
                properties={"status": "approved"},
                source_text=content,
                confidence=0.94,
                created_at=created_at,
            ),
            Entity(
                id="raw-integration-tests",
                name="Integration Tests",
                type="project",
                properties={"status": "passing"},
                source_text=content,
                confidence=0.93,
                created_at=created_at,
            ),
        ]
        relationships = [
            Relationship(
                id="raw-rel-ownership",
                source_id="raw-alice",
                target_id="raw-launch-checklist",
                type="owns",
                properties={"scope": "release"},
                confidence=0.96,
                created_at=created_at,
            ),
            Relationship(
                id="raw-rel-checklist-depends",
                source_id="raw-launch-checklist",
                target_id="raw-release-runbook",
                type="depends_on",
                properties={"scope": "runbook"},
                confidence=0.92,
                created_at=created_at,
            ),
            Relationship(
                id="raw-rel-tests-validate",
                source_id="raw-integration-tests",
                target_id="raw-launch-checklist",
                type="validates",
                properties={"scope": "qa"},
                confidence=0.91,
                created_at=created_at,
            ),
        ]
        facts = ["Alice coordinates the launch checklist, runbook, and tests."]
        summary = "Launch coordination dossier"
        community_summary = "stale large summary should be replaced"
        extra_memories = []
        community_definitions = [
            {
                "id": "comm-launch-owners",
                "title": "Launch Owners",
                "summary": community_summary,
                "entity_names": ["Alice", "Launch Checklist", "Release Runbook", "Integration Tests"],
                "rank": 0.97,
            }
        ]
    elif profile == "multi_aggregate":
        content = "Alice owns the launch checklist and release coordination."
        title = "Launch ownership note"
        extracted_entities = [
            Entity(
                id="raw-alice",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text=content,
                confidence=0.97,
                created_at=created_at,
            ),
            Entity(
                id="raw-launch-checklist",
                name="Launch Checklist",
                type="document",
                properties={"status": "active"},
                source_text=content,
                confidence=0.95,
                created_at=created_at,
            ),
        ]
        relationships = []
        facts = ["Alice owns the launch checklist."]
        summary = "Launch ownership note"
        community_summary = "Alice owns the launch checklist and release coordination."
        extra_memories = [
            {
                "content": "Release Runbook documents rollback checkpoints and deployment approvals.",
                "title": "Release runbook note",
                "timestamp": datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc).isoformat(),
                "source_path": "notes/release-runbook.md",
                "facts": ["Release Runbook tracks rollback checkpoints."],
                "summary": "Release runbook note",
                "entities": [
                    Entity(
                        id="raw-release-runbook",
                        name="Release Runbook",
                        type="document",
                        properties={"status": "approved"},
                        source_text="Release Runbook documents rollback checkpoints and deployment approvals.",
                        confidence=0.95,
                        created_at=created_at,
                    ),
                    Entity(
                        id="raw-deployment-approval",
                        name="Deployment Approval",
                        type="document",
                        properties={"status": "signed"},
                        source_text="Release Runbook documents rollback checkpoints and deployment approvals.",
                        confidence=0.93,
                        created_at=created_at,
                    ),
                ],
                "relationships": [
                    Relationship(
                        id="raw-rel-runbook-depends",
                        source_id="raw-release-runbook",
                        target_id="raw-deployment-approval",
                        type="depends_on",
                        properties={"scope": "approval"},
                        confidence=0.92,
                        created_at=created_at,
                    )
                ],
            },
            {
                "content": "Integration Tests validate launch readiness before rollout approval.",
                "title": "QA readiness note",
                "timestamp": datetime(2026, 4, 8, 11, 0, tzinfo=timezone.utc).isoformat(),
                "source_path": "notes/qa-readiness.md",
                "facts": ["Integration Tests validate launch readiness."],
                "summary": "QA readiness note",
                "entities": [
                    Entity(
                        id="raw-integration-tests",
                        name="Integration Tests",
                        type="project",
                        properties={"status": "passing"},
                        source_text="Integration Tests validate launch readiness before rollout approval.",
                        confidence=0.94,
                        created_at=created_at,
                    ),
                    Entity(
                        id="raw-launch-checklist-repeat",
                        name="Launch Checklist",
                        type="document",
                        properties={"status": "active"},
                        source_text="Integration Tests validate launch readiness before rollout approval.",
                        confidence=0.9,
                        created_at=created_at,
                    ),
                ],
                "relationships": [
                    Relationship(
                        id="raw-rel-tests-validate",
                        source_id="raw-integration-tests",
                        target_id="raw-launch-checklist-repeat",
                        type="validates",
                        properties={"scope": "qa"},
                        confidence=0.91,
                        created_at=created_at,
                    )
                ],
            },
        ]
        community_definitions = [
            {
                "id": "comm-launch-owners",
                "title": "Launch Owners",
                "summary": community_summary,
                "entity_names": ["Alice", "Launch Checklist"],
                "rank": 0.97,
            },
            {
                "id": "comm-release-readiness",
                "title": "Release Readiness",
                "summary": "Runbook, approvals, and QA readiness artifacts.",
                "entity_names": ["Release Runbook", "Deployment Approval", "Integration Tests"],
                "rank": 0.94,
            },
        ]
    elif profile == "memories_list":
        content = "Alice owns the launch checklist and release coordination."
        title = "Launch ownership note"
        extracted_entities = [
            Entity(
                id="raw-alice",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text=content,
                confidence=0.97,
                created_at=created_at,
            ),
            Entity(
                id="raw-launch-checklist",
                name="Launch Checklist",
                type="document",
                properties={"status": "active"},
                source_text=content,
                confidence=0.95,
                created_at=created_at,
            ),
        ]
        relationships = []
        facts = ["Alice owns the launch checklist."]
        summary = "Launch ownership note"
        community_summary = "Alice owns the launch checklist and release coordination."
        extra_memories = []
        for index in range(1, 23):
            archived = index in {5, 11, 17, 22}
            extra_memories.append(
                {
                    "content": f"List memory {index:02d} captures rollout note {index}.",
                    "title": f"List memory {index:02d}",
                    "timestamp": datetime(2026, 4, 8, 9, index, tzinfo=timezone.utc).isoformat(),
                    "source_path": f"notes/list-memory-{index:02d}.md",
                    "facts": [f"List memory {index:02d} captures rollout note {index}."],
                    "summary": f"List memory {index:02d}",
                    "entities": [],
                    "relationships": [],
                    "metadata": {
                        "archived": archived,
                        "archived_at": datetime(2026, 4, 8, 12, index, tzinfo=timezone.utc).isoformat() if archived else None,
                    },
                }
            )
        community_definitions = [
            {
                "id": "comm-launch-owners",
                "title": "Launch Owners",
                "summary": community_summary,
                "entity_names": ["Alice", "Launch Checklist"],
                "rank": 0.97,
            }
        ]
    elif profile == "missing_memory_id":
        seed_without_memory = True
        content = ""
        title = ""
        extracted_entities = []
        relationships = []
        facts = []
        summary = ""
        extra_memories = []
        manual_entities = [
            GraphEntity(
                id="entity-orphan-alice",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text="Alice owns the launch checklist through community-only evidence without a direct memory record.",
                confidence=0.97,
                created_at=created_at,
            ),
            GraphEntity(
                id="entity-orphan-launch-checklist",
                name="Launch Checklist",
                type="document",
                properties={"status": "active"},
                source_text="Alice owns the launch checklist through community-only evidence without a direct memory record.",
                confidence=0.95,
                created_at=created_at,
            ),
        ]
        community_definitions = [
            {
                "id": "comm-missing-memory-id",
                "title": "Launch Owners Without Memory",
                "summary": "Alice owns the launch checklist, but this community currently has no direct memory mapping.",
                "entity_names": ["Alice", "Launch Checklist"],
                "rank": 0.95,
            }
        ]
    else:
        content = "Alice owns the launch checklist and release coordination."
        title = "Launch ownership note"
        extracted_entities = [
            Entity(
                id="raw-alice",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text=content,
                confidence=0.97,
                created_at=created_at,
            ),
            Entity(
                id="raw-launch-checklist",
                name="Launch Checklist",
                type="document",
                properties={"status": "active"},
                source_text=content,
                confidence=0.95,
                created_at=created_at,
            ),
        ]
        relationships = [
            Relationship(
                id="raw-rel-ownership",
                source_id="raw-alice",
                target_id="raw-launch-checklist",
                type="owns",
                properties={"scope": "release"},
                confidence=0.96,
                created_at=created_at,
            )
        ]
        facts = ["Alice owns the launch checklist."]
        summary = "Launch ownership note"
        community_summary = "Alice owns the launch checklist and release coordination."
        extra_memories = []
        community_definitions = [
            {
                "id": "comm-launch-owners",
                "title": "Launch Owners",
                "summary": community_summary,
                "entity_names": ["Alice", "Launch Checklist"],
                "rank": 0.97,
            }
        ]

    with ExitStack() as stack:
        stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
        stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

        graph_store = GraphStore()
        vector_store = VectorStore()
        memory_service = MemoryService(
            llm=FakeLLM(),
            vector_store=vector_store,
            graph_store=graph_store,
        )
        memory_service.extractor.extract = AsyncMock(
            return_value=ExtractionResult(
                entities=extracted_entities,
                relationships=relationships,
                facts=facts,
                summary=summary,
            )
        )

        try:
            result = None
            memory_ids = []
            if seed_without_memory:
                for entity in manual_entities:
                    await graph_store.create_entity(entity)
            else:
                result = await memory_service.ingest_memory(
                    content=content,
                    metadata={
                        "source": "manual",
                        "title": title,
                        "tags": ["search-real-smoke", "release"],
                        "source_path": "notes/launch-checklist.md",
                        "record_type": "decision",
                        "timestamp": created_at.isoformat(),
                    },
                )

                memory_ids = [result.memory_id]

                for memory_spec in extra_memories:
                    memory_service.extractor.extract = AsyncMock(
                        return_value=ExtractionResult(
                            entities=memory_spec["entities"],
                            relationships=memory_spec["relationships"],
                            facts=memory_spec["facts"],
                            summary=memory_spec["summary"],
                        )
                    )
                    extra_result = await memory_service.ingest_memory(
                        content=memory_spec["content"],
                        metadata={
                            "source": "manual",
                            "title": memory_spec["title"],
                            "tags": ["search-real-smoke", "release"],
                            "source_path": memory_spec["source_path"],
                            "record_type": "decision",
                            "timestamp": memory_spec["timestamp"],
                            **(memory_spec.get("metadata") or {}),
                        },
                    )
                    memory_ids.append(extra_result.memory_id)

            resolved_entity_ids = {}
            for community_def in community_definitions:
                entity_ids = []
                for entity_name in community_def["entity_names"]:
                    matched_entities = await graph_store.find_entities_by_name(entity_name, limit=10)
                    if not matched_entities:
                        raise RuntimeError(f"Failed to resolve seeded entity by name: {entity_name}")
                    entity_ids.append(matched_entities[0].id)
                    resolved_entity_ids[entity_name] = matched_entities[0].id

                community = Community(
                    id=community_def["id"],
                    level=1,
                    parent_id=None,
                    entity_ids=entity_ids,
                    summary=community_def["summary"],
                    title=community_def["title"],
                    rank=community_def["rank"],
                    created_at=created_at,
                )
                await graph_store.create_community(community)
                await graph_store.replace_community_memberships(
                    community_id=community.id,
                    entity_ids=entity_ids,
                    created_at=created_at.isoformat(),
                )
                await graph_store.refresh_community_entity_count(community.id)

            payload = {
                "memory_id": result.memory_id if result else None,
                "community_id": community_definitions[0]["id"],
                "memory_ids": memory_ids,
                "community_ids": [community_def["id"] for community_def in community_definitions],
                "entity_ids": resolved_entity_ids,
                "profile": profile,
                "workspace_root": str(workspace_root),
                "vector_dir": str(vector_dir),
            }
            output_path = os.environ.get("SEED_OUTPUT_PATH")
            if output_path:
                Path(output_path).write_text(
                    f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
                    encoding="utf-8",
                )
            print(json.dumps(payload, ensure_ascii=False))
        finally:
            await graph_store.close()
            await vector_store.close()


if __name__ == "__main__":
    asyncio.run(_seed())
