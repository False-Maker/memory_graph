"""Focused tests for /api/v1/communities endpoints."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCommunitiesEndpoint:
    """Test /api/v1/communities endpoints."""

    @pytest.mark.asyncio
    async def test_detect_communities_marks_state_clean(self, client):
        mock_detector = MagicMock()
        mock_detector.detect_communities = AsyncMock(
            return_value=SimpleNamespace(num_communities=4, modularity=0.42)
        )
        mock_store = MagicMock()
        mock_store.mark_community_clean = AsyncMock(
            return_value={
                "dirty": False,
                "last_reason": None,
                "last_marked_at": None,
                "last_rebuild_at": "2026-03-30T12:00:00",
                "last_rebuild_job_id": "community_rebuild_fixed",
            }
        )

        with patch("src.api.routes.communities.CommunityDetector", return_value=mock_detector):
            with patch("src.api.routes.communities.get_graph_store", return_value=mock_store):
                with patch("src.api.routes.communities.uuid.uuid4") as mock_uuid:
                    mock_uuid.return_value.hex = "fixedjobid1234567890"
                    response = await client.post(
                        "/api/v1/communities/detect?algorithm=louvain&resolution=1.5"
                    )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["algorithm"] == "leiden"
        assert body["resolution"] == 1.5
        assert body["num_communities"] == 4
        assert body["modularity"] == 0.42
        assert body["job_id"].startswith("community_rebuild_fixedjobid12")
        mock_store.mark_community_clean.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_community_status(self, client):
        mock_store = MagicMock()
        mock_store.get_community_state = AsyncMock(
            return_value={
                "dirty": True,
                "last_reason": "manual:memory:mem-1",
                "last_marked_at": "2026-03-30T10:00:00",
                "last_rebuild_at": None,
                "last_rebuild_job_id": None,
            }
        )

        with patch("src.api.routes.communities.get_graph_store", return_value=mock_store):
            response = await client.get("/api/v1/communities/status")

        assert response.status_code == 200
        assert response.json() == {
            "dirty": True,
            "last_reason": "manual:memory:mem-1",
            "last_marked_at": "2026-03-30T10:00:00",
            "last_rebuild_at": None,
            "last_rebuild_job_id": None,
        }

    @pytest.mark.asyncio
    async def test_list_communities_by_level(self, client):
        mock_builder = MagicMock()
        mock_builder.get_level_communities = AsyncMock(
            return_value=[
                {
                    "id": "comm-l2",
                    "level": 2,
                    "parent_id": "comm-root",
                    "title": "Level 2 Cluster",
                    "summary": "Filtered branch",
                    "entity_count": 2,
                    "rank": 0.6,
                    "created_at": "2026-03-30T10:30:00",
                }
            ]
        )

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities?level=2")

        assert response.status_code == 200
        assert response.json() == {
            "communities": [
                {
                    "id": "comm-l2",
                    "level": 2,
                    "parent_id": "comm-root",
                    "title": "Level 2 Cluster",
                    "summary": "Filtered branch",
                    "entity_count": 2,
                    "rank": 0.6,
                    "created_at": "2026-03-30T10:30:00",
                }
            ],
            "total": 1,
        }

    @pytest.mark.asyncio
    async def test_list_communities(self, client):
        hierarchy_payload = {
            "roots": [],
            "levels": {
                "1": [
                    {
                        "id": "comm-1",
                        "level": 1,
                        "parent_id": None,
                        "title": "Core Cluster",
                        "summary": "Primary entities",
                        "entity_count": 3,
                        "rank": 0.9,
                        "created_at": "2026-03-30T10:00:00",
                    }
                ]
            },
            "max_level": 1,
            "total_communities": 1,
        }
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=hierarchy_payload)

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities")

        assert response.status_code == 200
        assert response.json() == {
            "communities": [
                {
                    "id": "comm-1",
                    "level": 1,
                    "parent_id": None,
                    "title": "Core Cluster",
                    "summary": "Primary entities",
                    "entity_count": 3,
                    "rank": 0.9,
                    "created_at": "2026-03-30T10:00:00",
                }
            ],
            "total": 1,
        }

    @pytest.mark.asyncio
    async def test_list_communities_supports_qa_forced_failure(self, client):
        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_COMMUNITY_COLLECTIONS": "list"}, clear=False):
            response = await client.get("/api/v1/communities")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to list communities: QA forced failure for communities list"}

    @pytest.mark.asyncio
    async def test_get_community_detail(self, client):
        hierarchy_payload = {
            "roots": [],
            "levels": {
                "2": [
                    {
                        "id": "comm-2",
                        "level": 2,
                        "parent_id": "comm-root",
                        "title": "Secondary Cluster",
                        "summary": "Nested entities",
                        "entity_count": 2,
                        "rank": 0.5,
                        "created_at": "2026-03-30T11:00:00",
                    }
                ]
            },
            "max_level": 2,
            "total_communities": 1,
        }
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=hierarchy_payload)

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/comm-2")

        assert response.status_code == 200
        assert response.json() == {
            "id": "comm-2",
            "level": 2,
            "parent_id": "comm-root",
            "title": "Secondary Cluster",
            "summary": "Nested entities",
            "entity_count": 2,
            "rank": 0.5,
            "created_at": "2026-03-30T11:00:00",
        }

    @pytest.mark.asyncio
    async def test_get_community_detail_returns_404_when_missing(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value={"levels": {}})

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/comm-missing")

        assert response.status_code == 404
        assert response.json() == {"detail": "Community comm-missing not found"}

    @pytest.mark.asyncio
    async def test_get_full_hierarchy(self, client):
        hierarchy_payload = {
            "roots": [
                {
                    "id": "comm-root",
                    "title": "Root Cluster",
                    "level": 0,
                    "entity_count": 5,
                    "children": [
                        {
                            "id": "comm-child",
                            "title": "Child Cluster",
                            "level": 1,
                            "entity_count": 2,
                            "children": [],
                        }
                    ],
                }
            ],
            "levels": {"0": [], "1": []},
            "max_level": 1,
            "total_communities": 2,
        }
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=hierarchy_payload)

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/hierarchy")

        assert response.status_code == 200
        assert response.json() == {
            "roots": [
                {
                    "id": "comm-root",
                    "title": "Root Cluster",
                    "level": 0,
                    "entity_count": 5,
                    "children": [
                        {
                            "id": "comm-child",
                            "title": "Child Cluster",
                            "level": 1,
                            "entity_count": 2,
                            "children": [],
                        }
                    ],
                }
            ],
            "levels": 2,
            "total_communities": 2,
        }

    @pytest.mark.asyncio
    async def test_get_full_hierarchy_supports_qa_forced_failure(self, client):
        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_COMMUNITY_COLLECTIONS": "hierarchy"}, clear=False):
            response = await client.get("/api/v1/communities/hierarchy")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to get hierarchy: QA forced failure for communities hierarchy"}

    @pytest.mark.asyncio
    async def test_get_community_hierarchy_subtree(self, client):
        hierarchy_payload = {
            "roots": [],
            "levels": {
                "0": [
                    {
                        "id": "comm-root",
                        "title": "Root Cluster",
                        "level": 0,
                        "parent_id": None,
                        "entity_count": 5,
                    }
                ],
                "1": [
                    {
                        "id": "comm-child",
                        "title": "Child Cluster",
                        "level": 1,
                        "parent_id": "comm-root",
                        "entity_count": 2,
                    },
                    {
                        "id": "comm-leaf",
                        "title": "Leaf Cluster",
                        "level": 2,
                        "parent_id": "comm-child",
                        "entity_count": 1,
                    },
                ],
            },
        }
        mock_builder = MagicMock()
        mock_builder.get_descendants = AsyncMock(
            return_value=[
                {
                    "id": "comm-leaf",
                    "title": "Leaf Cluster",
                    "level": 2,
                    "parent_id": "comm-child",
                    "entity_count": 1,
                }
            ]
        )
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=hierarchy_payload)

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/comm-child/hierarchy")

        assert response.status_code == 200
        assert response.json() == {
            "id": "comm-child",
            "title": "Child Cluster",
            "level": 1,
            "entity_count": 2,
            "children": [
                {
                    "id": "comm-leaf",
                    "title": "Leaf Cluster",
                    "level": 2,
                    "entity_count": 1,
                    "children": [],
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_get_community_hierarchy_subtree_returns_404_when_missing(self, client):
        mock_builder = MagicMock()
        mock_builder.get_descendants = AsyncMock(return_value=[])

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.get("/api/v1/communities/comm-missing/hierarchy")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Community comm-missing not found or has no descendants",
        }

    @pytest.mark.asyncio
    async def test_regenerate_summary_returns_404_when_missing(self, client):
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value={"levels": {}})

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            response = await client.post(
                "/api/v1/communities/comm-missing/summarize",
                json={"regenerate": True, "max_tokens": 300},
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Community comm-missing not found"}

    @pytest.mark.asyncio
    async def test_regenerate_summary_uses_existing_summary_when_not_forced(self, client):
        hierarchy_payload = {
            "roots": [],
            "levels": {
                "1": [
                    {
                        "id": "comm-1",
                        "title": "Core Cluster",
                        "level": 1,
                        "summary": "Existing summary",
                        "entity_count": 3,
                        "created_at": "2026-03-31T12:00:00",
                    }
                ]
            },
        }
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=hierarchy_payload)
        mock_summarizer = MagicMock()
        mock_summarizer.generate_summary = AsyncMock(return_value="should not be used")

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            with patch("src.api.routes.communities.CommunitySummarizer", return_value=mock_summarizer):
                response = await client.post(
                    "/api/v1/communities/comm-1/summarize",
                    json={"regenerate": False, "max_tokens": 300},
                )

        assert response.status_code == 200
        assert response.json() == {
            "community_id": "comm-1",
            "summary": "Existing summary",
            "generated_at": "2026-03-31T12:00:00",
            "token_count": 2,
        }
        mock_summarizer.generate_summary.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_regenerate_summary_forces_new_summary(self, client):
        hierarchy_payload = {
            "roots": [],
            "levels": {
                "1": [
                    {
                        "id": "comm-1",
                        "title": "Core Cluster",
                        "level": 1,
                        "summary": "",
                        "entity_count": 3,
                        "created_at": "2026-03-31T12:00:00",
                    }
                ]
            },
        }
        mock_builder = MagicMock()
        mock_builder.get_hierarchy_tree = AsyncMock(return_value=hierarchy_payload)
        mock_summarizer = MagicMock()
        mock_summarizer.generate_summary = AsyncMock(return_value="Fresh generated summary")

        with patch("src.api.routes.communities.HierarchyBuilder", return_value=mock_builder):
            with patch("src.api.routes.communities.CommunitySummarizer", return_value=mock_summarizer):
                response = await client.post(
                    "/api/v1/communities/comm-1/summarize",
                    json={"regenerate": True, "max_tokens": 300},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["community_id"] == "comm-1"
        assert body["summary"] == "Fresh generated summary"
        assert body["token_count"] == 3
        mock_summarizer.generate_summary.assert_awaited_once_with("comm-1", max_tokens=300, force_regenerate=True)
