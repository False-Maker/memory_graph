"""Focused tests for /api/v1/communities/* detail read-only endpoints."""

from datetime import datetime, timezone
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.graph_store_models import GraphEntity


def _tree_with_community(community_id: str = "comm-1"):
    return {
        "roots": [],
        "levels": {
            "1": [
                {
                    "id": community_id,
                    "level": 1,
                    "parent_id": None,
                    "title": "Core Cluster",
                    "summary": "Primary entities",
                    "entity_count": 2,
                    "rank": 0.9,
                    "created_at": "2026-04-03T10:00:00+00:00",
                }
            ]
        },
        "max_level": 1,
        "total_communities": 1,
    }


class TestCommunityDetailEndpoints:
    @pytest.mark.asyncio
    async def test_get_community_entities_returns_structured_payload(self, client):
        created_at = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-1"))

        mock_store = MagicMock()
        mock_store.get_community_entities = AsyncMock(
            return_value=[
                GraphEntity(
                    id="entity-1",
                    name="Alice",
                    type="person",
                    properties={"role": "owner"},
                    created_at=created_at,
                )
            ]
        )

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            with patch("src.api.routes.communities.get_graph_store", return_value=mock_store):
                response = await client.get("/api/v1/communities/comm-1/entities?limit=20")

        assert response.status_code == 200
        assert response.json() == {
            "community_id": "comm-1",
            "entities": [
                {
                    "id": "entity-1",
                    "name": "Alice",
                    "type": "person",
                    "properties": {"role": "owner"},
                    "source_text": "",
                    "confidence": 1.0,
                    "created_at": "2026-04-03T10:00:00+00:00",
                }
            ],
            "total": 1,
        }
        mock_store.get_community_entities.assert_awaited_once_with("comm-1", limit=20)

    @pytest.mark.asyncio
    async def test_get_community_relationships_returns_structured_payload(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-2"))

        mock_store = MagicMock()
        mock_store.get_community_relationships = AsyncMock(
            return_value=[
                {
                    "id": "rel-1",
                    "source_id": "entity-1",
                    "source": "Alice",
                    "target_id": "entity-2",
                    "target": "Bob",
                    "type": "depends_on",
                    "created_at": datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
                }
            ]
        )

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            with patch("src.api.routes.communities.get_graph_store", return_value=mock_store):
                response = await client.get("/api/v1/communities/comm-2/relationships")

        assert response.status_code == 200
        assert response.json() == {
            "community_id": "comm-2",
            "relationships": [
                {
                    "id": "rel-1",
                    "source_id": "entity-1",
                    "source": "Alice",
                    "target_id": "entity-2",
                    "target": "Bob",
                    "type": "depends_on",
                    "created_at": "2026-04-03T11:00:00+00:00",
                }
            ],
            "total": 1,
        }
        mock_store.get_community_relationships.assert_awaited_once_with("comm-2", limit=50)

    @pytest.mark.asyncio
    async def test_get_community_ancestors_returns_structured_payload(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-3"))
        mock_builder.get_ancestors = AsyncMock(
            return_value=[
                {"id": "comm-parent", "level": 0, "title": "Parent Cluster", "parent_id": None}
            ]
        )

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/comm-3/ancestors")

        assert response.status_code == 200
        assert response.json() == {
            "community_id": "comm-3",
            "ancestors": [
                {"id": "comm-parent", "level": 0, "title": "Parent Cluster", "parent_id": None}
            ],
            "total": 1,
        }
        mock_builder.get_ancestors.assert_awaited_once_with("comm-3")

    @pytest.mark.asyncio
    async def test_get_community_descendants_returns_structured_payload(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-4"))
        mock_builder.get_descendants = AsyncMock(
            return_value=[
                {"id": "comm-child", "level": 2, "title": "Child Cluster", "parent_id": "comm-4"}
            ]
        )

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/comm-4/descendants")

        assert response.status_code == 200
        assert response.json() == {
            "community_id": "comm-4",
            "descendants": [
                {"id": "comm-child", "level": 2, "title": "Child Cluster", "parent_id": "comm-4"}
            ],
            "total": 1,
        }
        mock_builder.get_descendants.assert_awaited_once_with("comm-4")

    @pytest.mark.asyncio
    async def test_get_community_ancestors_supports_qa_forced_failure(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-qa"))

        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_COMMUNITY_FACETS": "comm-qa:ancestors"}, clear=False):
            with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
                response = await client.get("/api/v1/communities/comm-qa/ancestors")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to get community ancestors: QA forced failure for community ancestors: comm-qa"}

    @pytest.mark.asyncio
    async def test_get_community_descendants_supports_qa_forced_failure(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-qa"))

        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_COMMUNITY_FACETS": "comm-qa:descendants"}, clear=False):
            with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
                response = await client.get("/api/v1/communities/comm-qa/descendants")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to get community descendants: QA forced failure for community descendants: comm-qa"}

    @pytest.mark.asyncio
    async def test_get_community_entities_supports_qa_forced_failure(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-qa"))

        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_COMMUNITY_FACETS": "comm-qa:entities"}, clear=False):
            with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
                response = await client.get("/api/v1/communities/comm-qa/entities")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to get community entities: QA forced failure for community entities: comm-qa"}

    @pytest.mark.asyncio
    async def test_get_community_relationships_supports_qa_forced_failure(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=_tree_with_community("comm-qa"))

        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_COMMUNITY_FACETS": "comm-qa:relationships"}, clear=False):
            with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
                response = await client.get("/api/v1/communities/comm-qa/relationships")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to get community relationships: QA forced failure for community relationships: comm-qa"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/communities/comm-missing/entities",
            "/api/v1/communities/comm-missing/relationships",
            "/api/v1/communities/comm-missing/ancestors",
            "/api/v1/communities/comm-missing/descendants",
        ],
    )
    async def test_detail_endpoints_return_404_when_community_missing(self, client, endpoint):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value={"levels": {}})

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get(endpoint)

        assert response.status_code == 404
        assert response.json() == {"detail": "Community comm-missing not found"}
