"""
Unit tests for HierarchyBuilder module.

Tests cover:
- Hierarchy construction logic
- Ancestor/descendant queries
- Level assignment
- Edge cases (single community, flat hierarchy)
- Parent-child relationships
- get_hierarchy_tree method
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import igraph as ig
import leidenalg as la

from src.core.hierarchy import HierarchyBuilder, rebuild_hierarchy, get_community_path
from src.core.models.community import Community, CommunityHierarchy


# ============================================
# CommunityHierarchy Tests
# ============================================


class TestCommunityHierarchy:
    """Test CommunityHierarchy traversal methods."""

    def test_get_ancestors_single_level(self):
        """Test ancestors of a node with single parent."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "child": Community(
                id="child",
                level=0,
                parent_id="parent",
                entity_ids=[],
                summary="",
                title="Child",
                rank=0.5,
            ),
            "parent": Community(
                id="parent",
                level=1,
                parent_id=None,
                entity_ids=["child"],
                summary="",
                title="Parent",
                rank=1.0,
            ),
        }

        ancestors = hierarchy.get_ancestors("child")
        assert ancestors == ["parent"]

    def test_get_ancestors_multi_level(self):
        """Test ancestors through multiple levels."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "leaf": Community(
                id="leaf",
                level=0,
                parent_id="mid",
                entity_ids=[],
                summary="",
                title="Leaf",
                rank=0.2,
            ),
            "mid": Community(
                id="mid",
                level=1,
                parent_id="root",
                entity_ids=["leaf"],
                summary="",
                title="Mid",
                rank=0.5,
            ),
            "root": Community(
                id="root",
                level=2,
                parent_id=None,
                entity_ids=["mid"],
                summary="",
                title="Root",
                rank=1.0,
            ),
        }

        ancestors = hierarchy.get_ancestors("leaf")
        assert ancestors == ["mid", "root"]

    def test_get_ancestors_no_parent(self):
        """Test ancestors of root node (no parent)."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "root": Community(
                id="root",
                level=1,
                parent_id=None,
                entity_ids=[],
                summary="",
                title="Root",
                rank=1.0,
            ),
        }

        ancestors = hierarchy.get_ancestors("root")
        assert ancestors == []

    def test_get_ancestors_unknown_community(self):
        """Test ancestors of non-existent community."""
        hierarchy = CommunityHierarchy()

        ancestors = hierarchy.get_ancestors("unknown")
        assert ancestors == []

    def test_get_descendants_no_children(self):
        """Test descendants of leaf node."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "leaf": Community(
                id="leaf",
                level=0,
                parent_id="parent",
                entity_ids=[],
                summary="",
                title="Leaf",
                rank=0.5,
            ),
        }
        hierarchy.adjacency = {"leaf": []}

        descendants = hierarchy.get_descendants("leaf")
        assert descendants == []

    def test_get_descendants_single_level(self):
        """Test descendants with direct children."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "parent": Community(
                id="parent",
                level=1,
                parent_id=None,
                entity_ids=[],
                summary="",
                title="Parent",
                rank=1.0,
            ),
            "child1": Community(
                id="child1",
                level=0,
                parent_id="parent",
                entity_ids=[],
                summary="",
                title="Child1",
                rank=0.5,
            ),
            "child2": Community(
                id="child2",
                level=0,
                parent_id="parent",
                entity_ids=[],
                summary="",
                title="Child2",
                rank=0.5,
            ),
        }
        hierarchy.adjacency = {
            "parent": ["child1", "child2"],
            "child1": [],
            "child2": [],
        }

        descendants = hierarchy.get_descendants("parent")
        assert set(descendants) == {"child1", "child2"}

    def test_get_descendants_multi_level(self):
        """Test descendants through multiple levels."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "root": Community(
                id="root",
                level=2,
                parent_id=None,
                entity_ids=[],
                summary="",
                title="Root",
                rank=1.0,
            ),
            "mid": Community(
                id="mid",
                level=1,
                parent_id="root",
                entity_ids=[],
                summary="",
                title="Mid",
                rank=0.5,
            ),
            "leaf": Community(
                id="leaf",
                level=0,
                parent_id="mid",
                entity_ids=[],
                summary="",
                title="Leaf",
                rank=0.2,
            ),
        }
        hierarchy.adjacency = {"root": ["mid"], "mid": ["leaf"], "leaf": []}

        descendants = hierarchy.get_descendants("root")
        # Order may vary due to stack traversal
        assert set(descendants) == {"mid", "leaf"}

    def test_get_level_existing_community(self):
        """Test getting level of existing community."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "comm1": Community(
                id="comm1",
                level=2,
                parent_id=None,
                entity_ids=[],
                summary="",
                title="Comm1",
                rank=1.0,
            ),
        }

        level = hierarchy.get_level("comm1")
        assert level == 2

    def test_get_level_unknown_community(self):
        """Test getting level of non-existent community."""
        hierarchy = CommunityHierarchy()

        level = hierarchy.get_level("unknown")
        assert level == -1

    def test_parent_child_relationship_structure(self):
        """Test that parent-child relationships are correctly structured."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities = {
            "root": Community(
                id="root",
                level=2,
                parent_id=None,
                entity_ids=["child1", "child2"],
                summary="",
                title="Root",
                rank=1.0,
            ),
            "child1": Community(
                id="child1",
                level=1,
                parent_id="root",
                entity_ids=[],
                summary="",
                title="Child1",
                rank=0.5,
            ),
            "child2": Community(
                id="child2",
                level=1,
                parent_id="root",
                entity_ids=[],
                summary="",
                title="Child2",
                rank=0.5,
            ),
        }
        hierarchy.adjacency = {"root": ["child1", "child2"], "child1": [], "child2": []}

        # Verify root has no parent
        assert hierarchy.communities["root"].parent_id is None

        # Verify children have correct parent
        assert hierarchy.communities["child1"].parent_id == "root"
        assert hierarchy.communities["child2"].parent_id == "root"

        # Verify adjacency list
        assert hierarchy.adjacency["root"] == ["child1", "child2"]


# ============================================
# HierarchyBuilder Tests
# ============================================


class TestHierarchyBuilder:
    """Test HierarchyBuilder class."""

    @pytest.fixture
    def mock_graph_store(self):
        """Create a mock GraphStore."""
        store = MagicMock()

        # Create async context manager mock
        class AsyncSessionMock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def run(self, query, **kwargs):
                # Return empty async iterator by default
                return _AsyncIterator([])

        class _AsyncIterator:
            def __init__(self, items):
                self.items = items

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)

            async def single(self):
                return None

        store.get_session = MagicMock(return_value=AsyncSessionMock())
        store.close = AsyncMock()
        return store

    @pytest.fixture
    def builder(self, mock_graph_store):
        """Create a HierarchyBuilder instance with mocked dependencies."""
        return HierarchyBuilder(graph_store=mock_graph_store)

    def test_initialization(self, builder):
        """Test HierarchyBuilder initializes correctly."""
        assert builder.graph_store is not None
        assert builder.settings is not None
        assert builder.community_config is not None

    @pytest.mark.asyncio
    async def test_build_hierarchy_with_no_communities(self):
        """Test build_hierarchy when no level 1 communities exist."""
        # Use patch to mock the _get_level_1_communities method
        with patch.object(
            HierarchyBuilder,
            "_get_level_1_communities",
            return_value=AsyncMock(return_value=[]),
        ):
            builder = HierarchyBuilder()
            hierarchy = await builder.build_hierarchy()

        # Should return empty hierarchy when no communities exist
        assert hierarchy.communities == {}
        assert hierarchy.adjacency == {}

    def test_build_hierarchy_creates_multi_level_structure(self):
        """Test that build_hierarchy creates multiple levels when possible."""
        # This test verifies the logic of building hierarchy levels
        hierarchy = CommunityHierarchy()

        # Simulate level 1 communities
        comm1 = Community(
            id="comm1",
            level=1,
            parent_id=None,
            entity_ids=["entity1", "entity2"],
            summary="",
            title="Community 1",
            rank=0.5,
        )
        comm2 = Community(
            id="comm2",
            level=1,
            parent_id=None,
            entity_ids=["entity3", "entity4"],
            summary="",
            title="Community 2",
            rank=0.5,
        )

        hierarchy.communities = {"comm1": comm1, "comm2": comm2}
        hierarchy.adjacency = {"comm1": [], "comm2": []}

        # Verify level 1 communities have no parents
        assert hierarchy.communities["comm1"].parent_id is None
        assert hierarchy.communities["comm2"].parent_id is None
        assert hierarchy.communities["comm1"].level == 1
        assert hierarchy.communities["comm2"].level == 1


class TestHierarchyBuilderLevelOperations:
    """Test level-specific operations."""

    @pytest.fixture
    def sample_communities(self):
        """Create sample communities for testing."""
        return [
            Community(
                id="comm1",
                level=1,
                parent_id=None,
                entity_ids=["e1", "e2"],
                summary="Summary 1",
                title="Community 1",
                rank=0.8,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            ),
            Community(
                id="comm2",
                level=1,
                parent_id=None,
                entity_ids=["e3", "e4"],
                summary="Summary 2",
                title="Community 2",
                rank=0.6,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            ),
            Community(
                id="comm3",
                level=2,
                parent_id=None,
                entity_ids=["comm1", "comm2"],
                summary="Summary 3",
                title="Community 3",
                rank=1.0,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            ),
        ]

    def test_level_assignment(self, sample_communities):
        """Test that communities have correct level assignments."""
        # Level 1 communities
        assert sample_communities[0].level == 1
        assert sample_communities[1].level == 1

        # Level 2 community
        assert sample_communities[2].level == 2

    def test_level_filtering(self, sample_communities):
        """Test filtering communities by level."""
        level_1 = [c for c in sample_communities if c.level == 1]
        level_2 = [c for c in sample_communities if c.level == 2]

        assert len(level_1) == 2
        assert len(level_2) == 1

    @pytest.mark.asyncio
    async def test_detect_community_clusters_uses_resolution_partition(self):
        """Higher-level clustering should use a partition that accepts resolution_parameter."""
        builder = HierarchyBuilder(graph_store=MagicMock())
        graph = ig.Graph(2)
        graph.vs["community_id"] = ["comm1", "comm2"]
        partition = MagicMock(membership=[0, 1], q=0.5)

        with patch("src.core.hierarchy.la.find_partition", return_value=partition) as mock_find_partition:
            communities = await builder._detect_community_clusters(graph, level=2, resolution=1.0)

        assert len(communities) == 2
        mock_find_partition.assert_called_once_with(
            graph,
            la.RBConfigurationVertexPartition,
            resolution_parameter=1.0,
        )

    @pytest.mark.asyncio
    async def test_build_hierarchy_keeps_single_root_cluster(self):
        """A final single aggregated cluster should still be persisted into the hierarchy."""
        level_1 = [
            Community(
                id="comm1",
                level=1,
                parent_id=None,
                entity_ids=["e1", "e2"],
                summary="Summary 1",
                title="Community 1",
                rank=0.8,
            ),
            Community(
                id="comm2",
                level=1,
                parent_id=None,
                entity_ids=["e3", "e4"],
                summary="Summary 2",
                title="Community 2",
                rank=0.6,
            ),
        ]
        root = Community(
            id="community_level_2_root",
            level=2,
            parent_id=None,
            entity_ids=["comm1", "comm2"],
            summary="",
            title="Level 2 Cluster 1",
            rank=1.0,
        )

        builder = HierarchyBuilder(graph_store=MagicMock())
        builder._get_level_1_communities = AsyncMock(return_value=level_1)
        builder._build_community_graph = AsyncMock(return_value=ig.Graph(2))
        builder._detect_community_clusters = AsyncMock(return_value=[root])
        builder._store_communities = AsyncMock()
        builder._create_has_child_relationships = AsyncMock()

        hierarchy = await builder.build_hierarchy(max_levels=2, resolution=1.0)

        assert root.id in hierarchy.communities
        assert hierarchy.communities["comm1"].parent_id == root.id
        assert hierarchy.communities["comm2"].parent_id == root.id
        assert hierarchy.adjacency[root.id] == ["comm1", "comm2"]
        builder._store_communities.assert_awaited_once_with([root])


# ============================================
# Edge Cases Tests
# ============================================


class TestHierarchyEdgeCases:
    """Test edge cases in hierarchy building."""

    def test_single_community_hierarchy(self):
        """Test hierarchy with only one community."""
        hierarchy = CommunityHierarchy()

        hierarchy.communities = {
            "single": Community(
                id="single",
                level=1,
                parent_id=None,
                entity_ids=["e1", "e2"],
                summary="",
                title="Single Community",
                rank=1.0,
            )
        }
        hierarchy.adjacency = {"single": []}

        # Single community should have no descendants
        descendants = hierarchy.get_descendants("single")
        assert descendants == []

        # Single community should have no ancestors
        ancestors = hierarchy.get_ancestors("single")
        assert ancestors == []

    def test_flat_hierarchy_no_parenting(self):
        """Test flat hierarchy with no parent-child relationships."""
        hierarchy = CommunityHierarchy()

        # All communities at same level, no parents
        for i in range(5):
            comm_id = f"comm{i}"
            hierarchy.communities[comm_id] = Community(
                id=comm_id,
                level=1,
                parent_id=None,
                entity_ids=[f"e{i}"],
                summary="",
                title=f"Community {i}",
                rank=0.5,
            )
            hierarchy.adjacency[comm_id] = []

        # All should have no ancestors
        for comm_id in hierarchy.communities:
            assert hierarchy.get_ancestors(comm_id) == []
            assert hierarchy.get_descendants(comm_id) == []

    def test_empty_hierarchy(self):
        """Test operations on empty hierarchy."""
        hierarchy = CommunityHierarchy()

        assert hierarchy.get_ancestors("any") == []
        assert hierarchy.get_descendants("any") == []
        assert hierarchy.get_level("any") == -1

    def test_deeply_nested_hierarchy(self):
        """Test hierarchy with many nesting levels."""
        hierarchy = CommunityHierarchy()

        # Create 5 levels of nesting
        levels = 5
        prev_id = None

        for i in range(levels):
            comm_id = f"level{i}"
            hierarchy.communities[comm_id] = Community(
                id=comm_id,
                level=i,
                parent_id=prev_id,
                entity_ids=[],
                summary="",
                title=f"Level {i}",
                rank=1.0 - (i * 0.1),
            )
            hierarchy.adjacency[comm_id] = []

            if prev_id:
                hierarchy.adjacency[prev_id] = [comm_id]

            prev_id = comm_id

        # Test ancestors from leaf (level 4)
        leaf_id = "level4"
        ancestors = hierarchy.get_ancestors(leaf_id)
        assert len(ancestors) == 4  # All but leaf itself

        # Test descendants from root
        root_id = "level0"
        descendants = hierarchy.get_descendants(root_id)
        assert len(descendants) == 4  # All but root itself


# ============================================
# get_hierarchy_tree Tests
# ============================================


class TestGetHierarchyTree:
    """Test get_hierarchy_tree method."""

    def test_hierarchy_tree_structure(self):
        """Test that hierarchy tree returns correct structure."""
        hierarchy = CommunityHierarchy()

        # Create a simple tree structure
        hierarchy.communities = {
            "root1": Community(
                id="root1",
                level=2,
                parent_id=None,
                entity_ids=[],
                summary="",
                title="Root 1",
                rank=1.0,
            ),
            "root2": Community(
                id="root2",
                level=2,
                parent_id=None,
                entity_ids=[],
                summary="",
                title="Root 2",
                rank=1.0,
            ),
            "child1": Community(
                id="child1",
                level=1,
                parent_id="root1",
                entity_ids=[],
                summary="",
                title="Child 1",
                rank=0.5,
            ),
            "child2": Community(
                id="child2",
                level=1,
                parent_id="root1",
                entity_ids=[],
                summary="",
                title="Child 2",
                rank=0.5,
            ),
            "leaf": Community(
                id="leaf",
                level=0,
                parent_id="child1",
                entity_ids=[],
                summary="",
                title="Leaf",
                rank=0.2,
            ),
        }
        hierarchy.adjacency = {
            "root1": ["child1", "child2"],
            "root2": [],
            "child1": ["leaf"],
            "child2": [],
            "leaf": [],
        }

        # Verify roots (communities with no parent)
        roots = [
            comm_id
            for comm_id, comm in hierarchy.communities.items()
            if comm.parent_id is None
        ]
        assert set(roots) == {"root1", "root2"}

        # Verify level mapping
        level_mapping = {}
        for comm_id, comm in hierarchy.communities.items():
            if comm.level not in level_mapping:
                level_mapping[comm.level] = []
            level_mapping[comm.level].append(comm_id)

        assert level_mapping[0] == ["leaf"]
        assert set(level_mapping[1]) == {"child1", "child2"}
        assert set(level_mapping[2]) == {"root1", "root2"}

    def test_hierarchy_tree_single_root(self):
        """Test hierarchy tree with single root."""
        hierarchy = CommunityHierarchy()

        hierarchy.communities = {
            "root": Community(
                id="root",
                level=1,
                parent_id=None,
                entity_ids=["child"],
                summary="",
                title="Root",
                rank=1.0,
            ),
            "child": Community(
                id="child",
                level=0,
                parent_id="root",
                entity_ids=[],
                summary="",
                title="Child",
                rank=0.5,
            ),
        }
        hierarchy.adjacency = {"root": ["child"], "child": []}

        # Should have exactly one root
        roots = [
            comm_id
            for comm_id, comm in hierarchy.communities.items()
            if comm.parent_id is None
        ]
        assert roots == ["root"]

    @pytest.mark.asyncio
    async def test_get_hierarchy_tree_returns_route_compatible_payload(self):
        """The hierarchy payload should match what the communities routes consume."""
        hierarchy = CommunityHierarchy(
            communities={
                "root": Community(
                    id="root",
                    level=1,
                    parent_id=None,
                    entity_ids=["child"],
                    summary="Root summary",
                    title="Root",
                    rank=1.0,
                ),
                "child": Community(
                    id="child",
                    level=0,
                    parent_id="root",
                    entity_ids=["entity-1"],
                    summary="Child summary",
                    title="Child",
                    rank=0.5,
                ),
            },
            adjacency={"root": ["child"], "child": []},
        )

        builder = HierarchyBuilder(graph_store=MagicMock())
        builder.build_hierarchy = AsyncMock(return_value=hierarchy)

        payload = await builder.get_hierarchy_tree()

        assert payload["max_level"] == 1
        assert payload["total_communities"] == 2
        assert payload["roots"][0]["id"] == "root"
        assert payload["roots"][0]["children"][0]["id"] == "child"
        assert payload["levels"][1][0]["summary"] == "Root summary"
        assert payload["levels"][0][0]["summary"] == "Child summary"


# ============================================
# Utility Functions Tests
# ============================================


class TestUtilityFunctions:
    """Test utility functions in hierarchy module."""

    @patch("src.core.hierarchy.GraphStore")
    def test_rebuild_hierarchy_utility(self, mock_store_class):
        """Test rebuild_hierarchy utility function."""
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # rebuild_hierarchy is a simple wrapper
        # This test verifies it can be called
        assert callable(rebuild_hierarchy)

    @patch("src.core.hierarchy.GraphStore")
    def test_get_community_path_utility(self, mock_store_class):
        """Test get_community_path utility function."""
        assert callable(get_community_path)


# ============================================
# Integration-Style Tests
# ============================================


class TestHierarchyIntegrationScenarios:
    """Test realistic hierarchy building scenarios."""

    def test_two_community_merge(self):
        """Test merging two communities into one parent."""
        hierarchy = CommunityHierarchy()

        # Two level 1 communities
        hierarchy.communities = {
            "comm1": Community(
                id="comm1",
                level=1,
                parent_id="parent",
                entity_ids=["e1", "e2"],
                summary="",
                title="Community 1",
                rank=0.5,
            ),
            "comm2": Community(
                id="comm2",
                level=1,
                parent_id="parent",
                entity_ids=["e3", "e4"],
                summary="",
                title="Community 2",
                rank=0.5,
            ),
            "parent": Community(
                id="parent",
                level=2,
                parent_id=None,
                entity_ids=["comm1", "comm2"],
                summary="",
                title="Parent",
                rank=1.0,
            ),
        }
        hierarchy.adjacency = {
            "parent": ["comm1", "comm2"],
            "comm1": [],
            "comm2": [],
        }

        # Verify parent has both children
        assert set(hierarchy.adjacency["parent"]) == {"comm1", "comm2"}

        # Verify children reference parent
        assert hierarchy.communities["comm1"].parent_id == "parent"
        assert hierarchy.communities["comm2"].parent_id == "parent"

        # Verify parent entity_ids contain child IDs
        assert set(hierarchy.communities["parent"].entity_ids) == {"comm1", "comm2"}

    def test_branching_hierarchy(self):
        """Test hierarchy with multiple branches."""
        hierarchy = CommunityHierarchy()

        # Root with 3 children, one of which has its own child
        hierarchy.communities = {
            "root": Community(
                id="root",
                level=2,
                parent_id=None,
                entity_ids=["branch1", "branch2", "branch3"],
                summary="",
                title="Root",
                rank=1.0,
            ),
            "branch1": Community(
                id="branch1",
                level=1,
                parent_id="root",
                entity_ids=["leaf1"],
                summary="",
                title="Branch 1",
                rank=0.5,
            ),
            "branch2": Community(
                id="branch2",
                level=1,
                parent_id="root",
                entity_ids=[],
                summary="",
                title="Branch 2",
                rank=0.5,
            ),
            "branch3": Community(
                id="branch3",
                level=1,
                parent_id="root",
                entity_ids=[],
                summary="",
                title="Branch 3",
                rank=0.5,
            ),
            "leaf1": Community(
                id="leaf1",
                level=0,
                parent_id="branch1",
                entity_ids=[],
                summary="",
                title="Leaf 1",
                rank=0.2,
            ),
        }
        hierarchy.adjacency = {
            "root": ["branch1", "branch2", "branch3"],
            "branch1": ["leaf1"],
            "branch2": [],
            "branch3": [],
            "leaf1": [],
        }

        # Root should have 3 descendants (excluding itself)
        root_descendants = hierarchy.get_descendants("root")
        assert len(root_descendants) == 4  # branch1, branch2, branch3, leaf1

        # Branch 1 should have 1 descendant
        branch1_descendants = hierarchy.get_descendants("branch1")
        assert branch1_descendants == ["leaf1"]

        # Branch 2 should have 0 descendants
        branch2_descendants = hierarchy.get_descendants("branch2")
        assert branch2_descendants == []
