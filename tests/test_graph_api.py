"""Focused tests for /api/v1/graph endpoints."""

import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGraphEndpoint:
    """Test /api/v1/graph endpoints."""

    @pytest.mark.asyncio
    async def test_get_graph_stats(self, client):
        mock_store = MagicMock()
        mock_store.get_stats = AsyncMock(
            return_value=SimpleNamespace(
                total_entities=3,
                total_relationships=2,
                entity_types={"Person": 2, "Project": 1},
                total_memories=1,
            )
        )

        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            response = await client.get("/api/v1/graph/stats")

        assert response.status_code == 200
        assert response.json() == {
            "total_entities": 3,
            "total_relationships": 2,
            "entity_types": {"Person": 2, "Project": 1},
            "total_memories": 1,
        }

    @pytest.mark.asyncio
    async def test_get_graph_stats_supports_qa_forced_failure(self, client):
        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_GRAPH_READS": "stats"}, clear=False):
            response = await client.get("/api/v1/graph/stats")

        assert response.status_code == 500
        assert response.json() == {"detail": "QA forced failure for graph stats"}

    @pytest.mark.asyncio
    async def test_get_entities(self, client):
        mock_store = MagicMock()
        mock_store.get_entities = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="entity-1",
                    name="Alice",
                    type="Person",
                    properties={"role": "engineer"},
                    source_text="Alice works here",
                    confidence=0.95,
                    created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
                )
            ]
        )

        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            response = await client.get("/api/v1/graph/entities")

        assert response.status_code == 200
        assert response.json() == {
            "entities": [
                {
                    "id": "entity-1",
                    "name": "Alice",
                    "type": "Person",
                    "properties": {"role": "engineer"},
                    "source_text": "Alice works here",
                    "confidence": 0.95,
                    "created_at": "2026-03-26T09:00:00",
                }
            ],
            "total": 1,
        }

    @pytest.mark.asyncio
    async def test_get_entities_supports_qa_forced_failure(self, client):
        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_GRAPH_READS": "entities"}, clear=False):
            response = await client.get("/api/v1/graph/entities")

        assert response.status_code == 500
        assert response.json() == {"detail": "QA forced failure for graph entities"}

    @pytest.mark.asyncio
    async def test_get_entity_detail(self, client):
        mock_store = MagicMock()
        mock_store.get_entity = AsyncMock(
            return_value=SimpleNamespace(
                id="entity-1",
                name="Alice",
                type="Person",
                properties={"role": "engineer"},
                source_text="Alice works here",
                confidence=0.95,
                created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
            )
        )

        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            response = await client.get("/api/v1/graph/entities/entity-1")

        assert response.status_code == 200
        assert response.json() == {
            "id": "entity-1",
            "name": "Alice",
            "type": "Person",
            "properties": {"role": "engineer"},
            "source_text": "Alice works here",
            "confidence": 0.95,
            "created_at": "2026-03-26T09:00:00",
        }

    @pytest.mark.asyncio
    async def test_get_relationships(self, client):
        mock_store = MagicMock()
        mock_store.get_relationships = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="rel-1",
                    source_id="entity-1",
                    target_id="entity-2",
                    type="WORKS_WITH",
                    properties={"weight": 3},
                    confidence=0.88,
                )
            ]
        )

        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            response = await client.get("/api/v1/graph/relationships")

        assert response.status_code == 200
        assert response.json() == {
            "relationships": [
                {
                    "id": "rel-1",
                    "source_id": "entity-1",
                    "target_id": "entity-2",
                    "type": "WORKS_WITH",
                    "properties": {"weight": 3},
                    "confidence": 0.88,
                }
            ],
            "total": 1,
        }

    @pytest.mark.asyncio
    async def test_get_relationships_supports_qa_forced_failure(self, client):
        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_GRAPH_READS": "relationships"}, clear=False):
            response = await client.get("/api/v1/graph/relationships")

        assert response.status_code == 500
        assert response.json() == {"detail": "QA forced failure for graph relationships"}

    @pytest.mark.asyncio
    async def test_get_neighbors(self, client):
        mock_store = MagicMock()
        mock_store.get_neighbors = AsyncMock(
            return_value=[
                {
                    "nodes": [
                        {"id": "entity-1", "name": "Alice"},
                        {"id": "entity-2", "name": "Bob"},
                    ],
                    "distance": 1,
                }
            ]
        )

        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            response = await client.get("/api/v1/graph/entities/entity-1/neighbors?depth=1")

        assert response.status_code == 200
        assert response.json() == {
            "entity_id": "entity-1",
            "neighbors": [
                {
                    "nodes": [
                        {"id": "entity-1", "name": "Alice"},
                        {"id": "entity-2", "name": "Bob"},
                    ],
                    "distance": 1,
                }
            ],
        }
