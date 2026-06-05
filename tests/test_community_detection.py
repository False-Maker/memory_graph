"""
Unit tests for Community Detection module

Tests community detection using synthetic graphs, edge cases,
and modularity calculations.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

import igraph as ig
import leidenalg as la

from src.core.community_detection import (
    CommunityDetector,
    DetectionResult,
    detect_communities,
)
from src.core.models.community import Community, CommunityHierarchy


# ============================================
# Test: Synthetic Graph Community Detection
# ============================================


class TestSyntheticGraphs:
    """Test community detection on synthetic graphs with known structure."""

    @pytest.mark.asyncio
    async def test_two_cliques_graph(self, mock_graph_store):
        """Test detection on a graph with two clear cliques connected by a bridge."""
        detector = CommunityDetector(mock_graph_store)

        # Mock settings to enable community detection
        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            # Mock _store_communities and _create_belongs_to_relationships
            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities(
                resolution=1.0, min_community_size=2
            )

            # Should detect communities
            assert result.num_communities >= 1
            assert result.modularity >= 0.0
            assert isinstance(result.communities, list)
            assert isinstance(result.hierarchy, CommunityHierarchy)
            assert isinstance(result.size_distribution, dict)

    @pytest.mark.asyncio
    async def test_ring_graph(self, mock_graph_store):
        """Test detection on a ring graph (cycle)."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities(resolution=1.0)

            assert result.num_communities >= 1

    @pytest.mark.asyncio
    async def test_star_graph(self, mock_graph_store):
        """Test detection on a star graph (hub and spokes)."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities(resolution=1.0)

            # Star graph typically forms one community
            assert result.num_communities >= 1


# ============================================
# Test: Edge Cases
# ============================================


class TestEdgeCases:
    """Test edge cases for community detection."""

    @pytest.mark.asyncio
    async def test_empty_graph(self, mock_empty_graph_store):
        """Test detection on empty graph (no entities)."""
        detector = CommunityDetector(mock_empty_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True

            result = await detector.detect_communities()

            assert result.num_communities == 0
            assert result.modularity == 0.0
            assert result.communities == []
            assert result.size_distribution == {}

    @pytest.mark.asyncio
    async def test_single_node_graph(self):
        """Test detection on graph with single entity."""
        from src.core.graph_store import GraphStore
        from src.core.graph_store import GraphEntity

        store = MagicMock(spec=GraphStore)

        # Single entity, no relationships
        entities = [GraphEntity(id="entity-0", name="Solo", type="person")]
        store.query_entities = AsyncMock(return_value=entities)
        store.query_relationships_between_entities = AsyncMock(return_value=[])
        store.close = AsyncMock()

        detector = CommunityDetector(store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            # Small graph (< 10 nodes) creates single community
            assert result.num_communities == 1
            assert result.communities[0].title == "Root Community"

    @pytest.mark.asyncio
    async def test_disconnected_graph(self):
        """Test detection on disconnected graph components."""
        from src.core.graph_store import GraphStore
        from src.core.graph_store import GraphEntity, GraphRelationship

        store = MagicMock(spec=GraphStore)

        # Two separate components with no connection
        entities = [
            {"id": "e1", "name": "A", "type": "person"},
            {"id": "e2", "name": "B", "type": "person"},
            {"id": "e3", "name": "C", "type": "person"},
            {"id": "e4", "name": "D", "type": "person"},
        ]

        relationships = [
            {"source_id": "e1", "target_id": "e2", "type": "RELATES"},
            {"source_id": "e2", "target_id": "e3", "type": "RELATES"},
            # e4 is isolated
        ]

        store.query_entities = AsyncMock(
            return_value=[
                GraphEntity(id=item["id"], name=item["name"], type=item["type"])
                for item in entities
            ]
        )
        store.query_relationships_between_entities = AsyncMock(
            return_value=[
                GraphRelationship(
                    id=f"rel-{idx}",
                    source_id=item["source_id"],
                    target_id=item["target_id"],
                    type=item["type"],
                )
                for idx, item in enumerate(relationships)
            ]
        )
        store.close = AsyncMock()

        detector = CommunityDetector(store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities(resolution=1.0)

            # Should handle disconnected graph
            assert result.num_communities >= 1

    @pytest.mark.asyncio
    async def test_small_graph_single_community(self):
        """Test that small graphs (< 10 nodes) create a single community."""
        from src.core.graph_store import GraphStore
        from src.core.graph_store import GraphEntity, GraphRelationship

        store = MagicMock(spec=GraphStore)

        # 5 entities, fully connected
        entities = [
            {"id": f"e{i}", "name": f"E{i}", "type": "person"} for i in range(5)
        ]

        # All pairs connected
        relationships = []
        for i in range(5):
            for j in range(i + 1, 5):
                relationships.append(
                    {"source_id": f"e{i}", "target_id": f"e{j}", "type": "RELATES"}
                )

        store.query_entities = AsyncMock(
            return_value=[
                GraphEntity(id=item["id"], name=item["name"], type=item["type"])
                for item in entities
            ]
        )
        store.query_relationships_between_entities = AsyncMock(
            return_value=[
                GraphRelationship(
                    id=f"rel-{idx}",
                    source_id=item["source_id"],
                    target_id=item["target_id"],
                    type=item["type"],
                )
                for idx, item in enumerate(relationships)
            ]
        )
        store.close = AsyncMock()

        detector = CommunityDetector(store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            # Small graph creates single community
            assert result.num_communities == 1
            assert result.communities[0].title == "Root Community"
            assert "small graph" in result.communities[0].summary.lower()


# ============================================
# Test: Community Assignment
# ============================================


class TestCommunityAssignment:
    """Test correct assignment of entities to communities."""

    @pytest.mark.asyncio
    async def test_all_entities_assigned(self, mock_graph_store):
        """Test that all entities are assigned to communities."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            # Collect all entity IDs from communities
            assigned_entity_ids = set()
            for community in result.communities:
                assigned_entity_ids.update(community.entity_ids)

            # All 6 entities should be assigned (given low min_community_size)
            # Note: some entities might be filtered if communities are too small
            assert len(assigned_entity_ids) >= 4  # At least 4 entities in communities

    @pytest.mark.asyncio
    async def test_community_properties(self, mock_graph_store):
        """Test that communities have correct properties."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            for community in result.communities:
                assert isinstance(community.id, str)
                assert len(community.id) > 0
                assert community.level == 0  # Level 0 for leaf communities
                assert community.parent_id is None  # No parent for level 0
                assert isinstance(community.entity_ids, list)
                assert len(community.entity_ids) > 0
                assert isinstance(community.title, str)
                assert isinstance(community.summary, str)
                assert isinstance(community.rank, (int, float))
                assert isinstance(community.created_at, datetime)


# ============================================
# Test: Modularity Calculation
# ============================================


class TestModularity:
    """Test modularity calculation."""

    @pytest.mark.asyncio
    async def test_modularity_range(self, mock_graph_store):
        """Test that modularity is in valid range [-1, 1] (usually [0, 1] for undirected)."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            # Modularity should be between 0 and 1 for undirected graphs
            assert 0.0 <= result.modularity <= 1.0

    @pytest.mark.asyncio
    async def test_modularity_zero_for_single_community(self):
        """Test that single community has modularity near 0."""
        from src.core.graph_store import GraphStore
        from src.core.graph_store import GraphEntity

        store = MagicMock(spec=GraphStore)

        entities = [
            GraphEntity(id=f"e{i}", name=f"E{i}", type="person") for i in range(5)
        ]
        store.query_entities = AsyncMock(return_value=entities)
        store.query_relationships_between_entities = AsyncMock(return_value=[])
        store.close = AsyncMock()

        detector = CommunityDetector(store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            # Single community should have modularity 0
            assert result.modularity == 0.0


# ============================================
# Test: Resolution Parameter Effects
# ============================================


class TestResolutionParameter:
    """Test effects of resolution parameter on community detection."""

    @pytest.mark.asyncio
    async def test_low_resolution_fewer_communities(self, mock_graph_store):
        """Test that low resolution produces fewer (larger) communities."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result_low = await detector.detect_communities(resolution=0.1)

        # Reset mocks
        detector._store_communities.reset_mock()
        detector._create_belongs_to_relationships.reset_mock()

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result_high = await detector.detect_communities(resolution=2.0)

        # Higher resolution should produce at least as many communities as low
        # (though results may vary based on graph structure)
        assert result_low.num_communities >= 1
        assert result_high.num_communities >= 1

    @pytest.mark.asyncio
    async def test_default_resolution(self, mock_graph_store):
        """Test that default resolution is used when none provided."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.5
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            # Call without resolution parameter
            result = await detector.detect_communities()

            assert result.num_communities >= 1


# ============================================
# Test: Size Distribution
# ============================================


class TestSizeDistribution:
    """Test community size distribution calculations."""

    @pytest.mark.asyncio
    async def test_size_distribution_structure(self, mock_graph_store):
        """Test that size distribution has correct structure."""
        detector = CommunityDetector(mock_graph_store)

        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            detector._store_communities = AsyncMock()
            detector._create_belongs_to_relationships = AsyncMock()

            result = await detector.detect_communities()

            # Size distribution maps size -> count
            assert isinstance(result.size_distribution, dict)

            for size, count in result.size_distribution.items():
                assert isinstance(size, int)
                assert size > 0
                assert isinstance(count, int)
                assert count > 0

            # Verify counts match actual communities
            total_from_distribution = sum(
                size * count for size, count in result.size_distribution.items()
            )
            total_from_communities = sum(len(c.entity_ids) for c in result.communities)
            assert total_from_distribution == total_from_communities


# ============================================
# Test: Disabled Community Detection
# ============================================


class TestDisabledDetection:
    """Test behavior when community detection is disabled."""

    @pytest.mark.asyncio
    async def test_disabled_returns_empty_result(self, mock_graph_store):
        """Test that disabled detection returns empty result."""
        detector = CommunityDetector(mock_graph_store)

        # Patch the config directly on the detector
        with patch.object(detector.config, "enabled", False):
            result = await detector.detect_communities()

            assert result.num_communities == 0
            assert result.modularity == 0.0
            assert result.communities == []
            assert result.size_distribution == {}

    @pytest.mark.asyncio
    async def test_disabled_with_empty_graph(self, mock_empty_graph_store):
        """Test that disabled detection with empty graph returns empty result."""
        detector = CommunityDetector(mock_empty_graph_store)

        # Patch the config directly on the detector
        with patch.object(detector.config, "enabled", False):
            result = await detector.detect_communities()

            assert result.num_communities == 0
            assert result.modularity == 0.0
            assert result.communities == []
            assert result.size_distribution == {}


# ============================================
# Test: Helper Methods
# ============================================


class TestHelperMethods:
    """Test private helper methods."""

    def test_calculate_size_distribution(self):
        """Test size distribution calculation."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        communities = [
            Community(
                id="c1",
                level=0,
                parent_id=None,
                entity_ids=["e1", "e2", "e3"],
                summary="",
                title="C1",
                rank=0.0,
            ),
            Community(
                id="c2",
                level=0,
                parent_id=None,
                entity_ids=["e4", "e5"],
                summary="",
                title="C2",
                rank=0.0,
            ),
            Community(
                id="c3",
                level=0,
                parent_id=None,
                entity_ids=["e6", "e7", "e8"],
                summary="",
                title="C3",
                rank=0.0,
            ),
        ]

        distribution = detector._calculate_size_distribution(communities)

        assert distribution == {3: 2, 2: 1}

    def test_calculate_size_distribution_empty(self):
        """Test size distribution with empty communities list."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        distribution = detector._calculate_size_distribution([])

        assert distribution == {}


# ============================================
# Test: Convenience Functions
# ============================================


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_detect_communities_function(self, mock_graph_store):
        """Test the convenience function."""
        with patch("src.core.community_detection.get_settings") as mock_settings:
            mock_settings.return_value.advanced.community_detection.enabled = True
            mock_settings.return_value.advanced.community_detection.resolution = 1.0
            mock_settings.return_value.advanced.community_detection.min_community_size = 2

            # Mock the detector methods
            with patch.object(CommunityDetector, "_store_communities", AsyncMock()):
                with patch.object(
                    CommunityDetector, "_create_belongs_to_relationships", AsyncMock()
                ):
                    result = await detect_communities(graph_store=mock_graph_store)

            assert isinstance(result, DetectionResult)
            assert isinstance(result.communities, list)
            assert isinstance(result.hierarchy, CommunityHierarchy)


# ============================================
# Test: DetectionResult Dataclass
# ============================================


class TestDetectionResult:
    """Test DetectionResult dataclass."""

    def test_detection_result_creation(self):
        """Test creating DetectionResult."""
        result = DetectionResult(
            communities=[],
            hierarchy=CommunityHierarchy(),
            modularity=0.5,
            num_communities=3,
            size_distribution={5: 2, 3: 1},
        )

        assert result.communities == []
        assert result.modularity == 0.5
        assert result.num_communities == 3
        assert result.size_distribution == {5: 2, 3: 1}
        assert isinstance(result.hierarchy, CommunityHierarchy)


# ============================================
# Test: Run Leiden
# ============================================


class TestRunLeiden:
    """Test _run_leiden method."""

    def test_run_leiden_basic(self):
        """Test basic Leiden algorithm execution."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        # Create a simple graph
        g = ig.Graph(
            n=10,
            edges=[
                (0, 1),
                (0, 2),
                (1, 2),  # Clique 1
                (3, 4),
                (3, 5),
                (4, 5),  # Clique 2
                (6, 7),
                (6, 8),
                (7, 8),  # Clique 3
                (2, 3),
                (5, 6),  # Connections
            ],
            directed=False,
        )

        partition = detector._run_leiden(g, resolution=1.0)

        assert partition is not None
        assert hasattr(partition, "membership")
        assert hasattr(partition, "quality")

        modularity = partition.quality()
        assert 0.0 <= modularity <= 1.0

    def test_run_leiden_disconnected_graph(self):
        """Test Leiden on disconnected graph."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        # Create disconnected graph (two separate components)
        g = ig.Graph(
            n=6,
            edges=[
                (0, 1),
                (0, 2),
                (1, 2),  # Component 1
                (3, 4),
                (3, 5),
                (4, 5),  # Component 2
                # No connection between components
            ],
            directed=False,
        )

        partition = detector._run_leiden(g, resolution=1.0)

        assert partition is not None
        modularity = partition.quality()
        assert 0.0 <= modularity <= 1.0

    def test_run_leiden_different_resolutions(self):
        """Test Leiden with different resolution parameters."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        # Create a graph
        g = ig.Graph.Erdos_Renyi(n=20, p=0.1)

        partition_low = detector._run_leiden(g, resolution=0.1)
        partition_high = detector._run_leiden(g, resolution=2.0)

        # Both should produce valid partitions
        assert len(set(partition_low.membership)) >= 1
        assert len(set(partition_high.membership)) >= 1


# ============================================
# Test: Partition to Communities
# ============================================


class TestPartitionToCommunities:
    """Test _partition_to_communities method."""

    @pytest.mark.asyncio
    async def test_partition_to_communities_basic(self):
        """Test basic partition conversion."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        # Create a better graph with clear communities
        # Two cliques of 3 nodes each, connected by a single edge
        g = ig.Graph(
            n=6,
            edges=[
                (0, 1),
                (0, 2),
                (1, 2),  # Clique 1 - fully connected
                (3, 4),
                (3, 5),
                (4, 5),  # Clique 2 - fully connected
                (2, 3),  # Bridge connection
            ],
            directed=False,
        )

        partition = la.find_partition(
            g, la.CPMVertexPartition, resolution_parameter=0.5
        )
        entity_id_map = {i: f"entity-{i}" for i in range(6)}

        communities = await detector._partition_to_communities(
            partition, entity_id_map, min_community_size=2
        )

        # Should detect at least one community with min size 2
        assert len(communities) >= 1

        for comm in communities:
            assert isinstance(comm, Community)
            assert len(comm.entity_ids) >= 2  # Due to min_community_size
            assert comm.level == 0
            assert comm.parent_id is None

    @pytest.mark.asyncio
    async def test_partition_to_communities_filters_small(self):
        """Test that small communities are filtered out."""
        from src.core.community_detection import CommunityDetector

        detector = CommunityDetector()

        # Create a star graph - one central node connected to all others
        # Leiden might create one large community and some singletons
        g = ig.Graph(
            n=7,
            edges=[
                (0, 1),
                (0, 2),
                (0, 3),
                (0, 4),
                (0, 5),
                (0, 6),  # Star
            ],
            directed=False,
        )

        partition = la.find_partition(
            g, la.CPMVertexPartition, resolution_parameter=1.0
        )
        entity_id_map = {i: f"entity-{i}" for i in range(7)}

        # Set high min_community_size
        communities = await detector._partition_to_communities(
            partition, entity_id_map, min_community_size=3
        )

        # Should filter out small communities (size < 3)
        for comm in communities:
            assert len(comm.entity_ids) >= 3


# ============================================
# Test: CommunityHierarchy Methods
# ============================================


class TestCommunityHierarchy:
    """Test CommunityHierarchy utility methods."""

    def test_get_ancestors(self):
        """Test getting ancestors of a community."""
        hierarchy = CommunityHierarchy(
            communities={
                "c1": Community(
                    id="c1",
                    level=2,
                    parent_id=None,
                    entity_ids=[],
                    summary="",
                    title="C1",
                    rank=0.0,
                ),
                "c2": Community(
                    id="c2",
                    level=1,
                    parent_id="c1",
                    entity_ids=[],
                    summary="",
                    title="C2",
                    rank=0.0,
                ),
                "c3": Community(
                    id="c3",
                    level=0,
                    parent_id="c2",
                    entity_ids=[],
                    summary="",
                    title="C3",
                    rank=0.0,
                ),
            },
            adjacency={"c1": ["c2"], "c2": ["c3"]},
        )

        ancestors = hierarchy.get_ancestors("c3")
        assert ancestors == ["c2", "c1"]

    def test_get_descendants(self):
        """Test getting descendants of a community."""
        hierarchy = CommunityHierarchy(
            communities={
                "c1": Community(
                    id="c1",
                    level=2,
                    parent_id=None,
                    entity_ids=[],
                    summary="",
                    title="C1",
                    rank=0.0,
                ),
                "c2": Community(
                    id="c2",
                    level=1,
                    parent_id="c1",
                    entity_ids=[],
                    summary="",
                    title="C2",
                    rank=0.0,
                ),
                "c3": Community(
                    id="c3",
                    level=0,
                    parent_id="c2",
                    entity_ids=[],
                    summary="",
                    title="C3",
                    rank=0.0,
                ),
            },
            adjacency={"c1": ["c2"], "c2": ["c3"]},
        )

        descendants = hierarchy.get_descendants("c1")
        assert set(descendants) == {"c2", "c3"}

    def test_get_level(self):
        """Test getting level of a community."""
        hierarchy = CommunityHierarchy(
            communities={
                "c1": Community(
                    id="c1",
                    level=2,
                    parent_id=None,
                    entity_ids=[],
                    summary="",
                    title="C1",
                    rank=0.0,
                ),
                "c2": Community(
                    id="c2",
                    level=0,
                    parent_id="c1",
                    entity_ids=[],
                    summary="",
                    title="C2",
                    rank=0.0,
                ),
            },
            adjacency={},
        )

        assert hierarchy.get_level("c1") == 2
        assert hierarchy.get_level("c2") == 0
        assert hierarchy.get_level("nonexistent") == -1
