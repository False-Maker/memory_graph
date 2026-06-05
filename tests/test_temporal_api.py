"""Focused tests for /api/v1/temporal endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTemporalApi:
    @pytest.mark.asyncio
    async def test_create_temporal_triple(self, client):
        mock_temporal = MagicMock()
        mock_temporal.upsert_triple = AsyncMock(
            return_value=SimpleNamespace(
                id="triple-1",
                entity_id="entity-1",
                relation_type="works_on",
                target_entity_id="entity-2",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_to=None,
                confidence=0.9,
                source="manual",
                created_at="2026-04-16T10:00:00+00:00",
                metadata={"ticket": "MG-1"},
            )
        )

        with patch("src.api.routes.temporal.get_temporal_kg", return_value=mock_temporal):
            response = await client.post(
                "/api/v1/temporal/triples",
                json={
                    "entity_id": "entity-1",
                    "relation_type": "works_on",
                    "target_entity_id": "entity-2",
                    "valid_from": "2026-04-01",
                    "confidence": 0.9,
                    "source": "manual",
                    "metadata": {"ticket": "MG-1"},
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "id": "triple-1",
            "entity_id": "entity-1",
            "relation_type": "works_on",
            "target_entity_id": "entity-2",
            "valid_from": "2026-04-01T00:00:00+00:00",
            "valid_to": None,
            "confidence": 0.9,
            "source": "manual",
            "created_at": "2026-04-16T10:00:00+00:00",
            "metadata": {"ticket": "MG-1"},
        }

    @pytest.mark.asyncio
    async def test_create_temporal_triple_returns_400_for_invalid_interval(self, client):
        mock_temporal = MagicMock()
        mock_temporal.upsert_triple = AsyncMock(side_effect=ValueError("valid_from must be earlier than or equal to valid_to"))

        with patch("src.api.routes.temporal.get_temporal_kg", return_value=mock_temporal):
            response = await client.post(
                "/api/v1/temporal/triples",
                json={
                    "entity_id": "entity-1",
                    "relation_type": "works_on",
                    "valid_from": "2026-05-01",
                    "valid_to": "2026-04-01",
                },
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "valid_from must be earlier than or equal to valid_to"}

    @pytest.mark.asyncio
    async def test_get_entity_timeline(self, client):
        mock_temporal = MagicMock()
        mock_temporal.get_entity_timeline = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="triple-1",
                    entity_id="entity-1",
                    relation_type="works_on",
                    target_entity_id="entity-2",
                    valid_from="2026-04-01T00:00:00+00:00",
                    valid_to=None,
                    confidence=0.9,
                    source="manual",
                    created_at="2026-04-16T10:00:00+00:00",
                    metadata={},
                )
            ]
        )

        with patch("src.api.routes.temporal.get_temporal_kg", return_value=mock_temporal):
            response = await client.get("/api/v1/temporal/entities/entity-1/timeline")

        assert response.status_code == 200
        assert response.json() == {
            "entity_id": "entity-1",
            "total": 1,
            "triples": [
                {
                    "id": "triple-1",
                    "entity_id": "entity-1",
                    "relation_type": "works_on",
                    "target_entity_id": "entity-2",
                    "valid_from": "2026-04-01T00:00:00+00:00",
                    "valid_to": None,
                    "confidence": 0.9,
                    "source": "manual",
                    "created_at": "2026-04-16T10:00:00+00:00",
                    "metadata": {},
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_get_entity_state_as_of_requires_query_param(self, client):
        response = await client.get("/api/v1/temporal/entities/entity-1")

        assert response.status_code == 400
        assert response.json() == {"detail": "as_of query parameter is required"}

    @pytest.mark.asyncio
    async def test_get_entity_state_as_of(self, client):
        mock_temporal = MagicMock()
        mock_temporal.get_entity_state_as_of = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="triple-2",
                    entity_id="entity-1",
                    relation_type="uses",
                    target_entity_id="entity-3",
                    valid_from="2026-04-01T00:00:00+00:00",
                    valid_to="2026-04-30T00:00:00+00:00",
                    confidence=1.0,
                    source="import",
                    created_at="2026-04-16T11:00:00+00:00",
                    metadata={"note": "active during April"},
                )
            ]
        )

        with patch("src.api.routes.temporal.get_temporal_kg", return_value=mock_temporal):
            response = await client.get("/api/v1/temporal/entities/entity-1?as_of=2026-04-16")

        assert response.status_code == 200
        assert response.json() == {
            "entity_id": "entity-1",
            "as_of": "2026-04-16",
            "total": 1,
            "triples": [
                {
                    "id": "triple-2",
                    "entity_id": "entity-1",
                    "relation_type": "uses",
                    "target_entity_id": "entity-3",
                    "valid_from": "2026-04-01T00:00:00+00:00",
                    "valid_to": "2026-04-30T00:00:00+00:00",
                    "confidence": 1.0,
                    "source": "import",
                    "created_at": "2026-04-16T11:00:00+00:00",
                    "metadata": {"note": "active during April"},
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_delete_temporal_triple(self, client):
        mock_temporal = MagicMock()
        mock_temporal.delete_triple = AsyncMock(return_value=True)

        with patch("src.api.routes.temporal.get_temporal_kg", return_value=mock_temporal):
            response = await client.delete("/api/v1/temporal/triples/triple-1")

        assert response.status_code == 200
        assert response.json() == {"success": True, "triple_id": "triple-1"}

    @pytest.mark.asyncio
    async def test_get_temporal_stats(self, client):
        mock_temporal = MagicMock()
        mock_temporal.get_stats = AsyncMock(
            return_value=SimpleNamespace(
                total_triples=3,
                entities_with_temporal_data=2,
                open_intervals=1,
                bounded_intervals=2,
            )
        )

        with patch("src.api.routes.temporal.get_temporal_kg", return_value=mock_temporal):
            response = await client.get("/api/v1/temporal/stats")

        assert response.status_code == 200
        assert response.json() == {
            "total_triples": 3,
            "entities_with_temporal_data": 2,
            "open_intervals": 1,
            "bounded_intervals": 2,
        }
