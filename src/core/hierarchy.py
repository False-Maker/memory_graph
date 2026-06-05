"""
Hierarchy Builder Module
Builds hierarchical community structure using recursive community merging
"""

import hashlib
import uuid
import logging
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field

import igraph as ig
import leidenalg as la

from src.core.config import get_settings
from src.core.models.community import Community, CommunityHierarchy
from src.core.graph_store import GraphStore

logger = logging.getLogger(__name__)


class HierarchyBuilder:
    """
    Builds hierarchical community structure from detected communities.

    Process:
    1. Level 0: Original entities (leaf level)
    2. Level 1: Leiden communities from entity graph
    3. Level 2+: Communities as nodes, re-run Leiden on community graph
    4. Stop when < 2 communities remain

    Creates parent-child relationships and stores them via GraphStore.
    """

    def __init__(self, graph_store: Optional[GraphStore] = None):
        """Initialize hierarchy builder"""
        self.graph_store = graph_store or GraphStore()
        self.settings = get_settings()
        self.community_config = self.settings.advanced.community_detection

    async def build_hierarchy(
        self,
        max_levels: Optional[int] = None,
        resolution: Optional[float] = None,
    ) -> CommunityHierarchy:
        """
        Build complete community hierarchy.

        Args:
            max_levels: Maximum hierarchy depth (default from config)
            resolution: Leiden resolution parameter (default from config)

        Returns:
            CommunityHierarchy with all levels and relationships
        """
        max_levels = max_levels or self.community_config.max_levels
        resolution = resolution or self.community_config.resolution

        logger.info(
            f"Building hierarchy: max_levels={max_levels}, resolution={resolution}"
        )

        hierarchy = CommunityHierarchy()

        # Fetch existing level 1 communities from previous detection
        level_1_communities = await self._get_level_1_communities()

        if not level_1_communities:
            logger.warning(
                "No level 1 communities found, run community detection first"
            )
            return hierarchy

        # Add level 1 communities to hierarchy
        for comm in level_1_communities:
            hierarchy.communities[comm.id] = comm
            hierarchy.adjacency[comm.id] = []

        # Build higher levels recursively
        current_level = 1
        current_communities = level_1_communities

        while current_level < max_levels and len(current_communities) >= 2:
            logger.info(
                f"Building level {current_level + 1} from {len(current_communities)} communities"
            )

            # Build community graph
            community_graph = await self._build_community_graph(current_communities)

            if community_graph.vcount() < 2:
                logger.info(f"Only {community_graph.vcount()} communities, stopping")
                break

            # Run Leiden on community graph
            next_communities = await self._detect_community_clusters(
                community_graph, current_level + 1, resolution
            )

            if len(next_communities) == 0:
                logger.info(
                    f"Only {len(next_communities)} clusters, stopping hierarchy"
                )
                break

            # Add new level to hierarchy
            for comm in next_communities:
                hierarchy.communities[comm.id] = comm
                hierarchy.adjacency[comm.id] = []

                # Link to parent communities
                for child_id in comm.entity_ids:
                    if child_id in hierarchy.communities:
                        hierarchy.communities[child_id].parent_id = comm.id
                        hierarchy.adjacency[comm.id].append(child_id)

            # Persist the newly derived communities
            await self._store_communities(next_communities)
            await self._create_has_child_relationships(next_communities)

            current_level += 1
            current_communities = next_communities

            if len(next_communities) == 1:
                logger.info("Hierarchy reached a single root cluster; stopping")
                break

        logger.info(
            f"Hierarchy built: {len(hierarchy.communities)} communities across {current_level} levels"
        )

        return hierarchy

    async def _get_level_1_communities(self) -> List[Community]:
        """Fetch existing level 1 communities from GraphStore."""
        community_rows = await self.graph_store.list_communities(
            level=1,
            limit=None,
            include_entity_ids=True,
        )

        communities = []
        for record in community_rows:
            communities.append(
                Community(
                    id=record["id"],
                    level=record["level"],
                    parent_id=record.get("parent_id"),
                    entity_ids=record.get("entity_ids", []),
                    summary=record.get("summary", ""),
                    title=record.get("title", f"Community {record['id']}"),
                    rank=record.get("rank", 0.0),
                )
            )

        logger.info(f"Found {len(communities)} level 1 communities")
        return communities

    async def _build_community_graph(self, communities: List[Community]) -> ig.Graph:
        """
        Build igraph from communities using inter-community connections.

        Two communities are connected if entities from one community
        have relationships with entities from another community.
        """
        # Get all entity IDs across communities
        comm_id_to_index: Dict[str, int] = {
            comm.id: i for i, comm in enumerate(communities)
        }
        index_to_comm_id: Dict[int, str] = {
            i: comm.id for comm, i in zip(communities, comm_id_to_index.values())
        }

        # Build community leaf-entity sets for fast lookup.
        community_entity_sets: Dict[str, Set[str]] = {
            comm.id: set(await self.graph_store.get_leaf_entity_ids(comm.id))
            for comm in communities
        }

        # Track connections between communities
        connections: Set[tuple[str, str]] = set()
        all_leaf_entity_ids = sorted(
            {
                entity_id
                for entity_set in community_entity_sets.values()
                for entity_id in entity_set
            }
        )
        relationships = await self.graph_store.query_relationships_between_entities(
            all_leaf_entity_ids,
            limit=None,
        )

        for relationship in relationships:
            id1, id2 = relationship.source_id, relationship.target_id

            comm1 = None
            comm2 = None
            for comm_id, entity_set in community_entity_sets.items():
                if comm1 is None and id1 in entity_set:
                    comm1 = comm_id
                if comm2 is None and id2 in entity_set:
                    comm2 = comm_id
                if comm1 and comm2:
                    break

            if comm1 and comm2 and comm1 != comm2:
                edge = (comm1, comm2) if comm1 < comm2 else (comm2, comm1)
                connections.add(edge)

        # Build igraph
        edges = list(connections)
        vertices = list(comm_id_to_index.keys())

        graph = ig.Graph(len(vertices), edges=[])

        # Add vertex attributes
        graph.vs["community_id"] = vertices

        # Add edges (convert community IDs to indices)
        if edges:
            edge_indices = []
            for comm1, comm2 in edges:
                edge_indices.append((comm_id_to_index[comm1], comm_id_to_index[comm2]))
            graph.add_edges(edge_indices)

        logger.info(
            f"Built community graph: {graph.vcount()} vertices, {graph.ecount()} edges"
        )

        return graph

    async def _detect_community_clusters(
        self, graph: ig.Graph, level: int, resolution: float
    ) -> List[Community]:
        """
        Run Leiden algorithm on community graph to detect clusters.

        Returns new communities at the next level.
        """
        if graph.vcount() < 2:
            # Single community contains all
            return [
                Community(
                    id=str(uuid.uuid4()),
                    level=level,
                    parent_id=None,
                    entity_ids=graph.vs["community_id"],
                    summary="",
                    title=f"Level {level} Root",
                    rank=1.0,
                )
            ]

        # Find optimal partition using Leiden
        partition = la.find_partition(
            graph, la.RBConfigurationVertexPartition, resolution_parameter=resolution
        )

        # Build communities from partition
        communities = []
        community_id_to_entities: Dict[int, List[str]] = {}

        for vertex_idx, community_id in enumerate(partition.membership):
            if community_id not in community_id_to_entities:
                community_id_to_entities[community_id] = []
            community_id_to_entities[community_id].append(
                graph.vs[vertex_idx]["community_id"]
            )

        for cluster_id, entity_ids in community_id_to_entities.items():
            # Generate title based on contained communities
            title = f"Level {level} Cluster {cluster_id + 1}"

            # Calculate rank based on size
            rank = float(len(entity_ids)) / graph.vcount()

            stable_suffix = hashlib.sha256(
                f"{level}|{'|'.join(sorted(entity_ids))}".encode("utf-8")
            ).hexdigest()[:12]
            communities.append(
                Community(
                    id=f"community_level_{level}_{stable_suffix}",
                    level=level,
                    parent_id=None,
                    entity_ids=entity_ids,
                    summary="",
                    title=title,
                    rank=rank,
                )
            )

        logger.info(
            f"Detected {len(communities)} clusters at level {level} "
            f"(modularity: {partition.q if hasattr(partition, 'q') else 'N/A'})"
        )

        return communities

    async def _store_communities(self, communities: List[Community]) -> None:
        """Store communities to GraphStore."""
        for comm in communities:
            await self.graph_store.create_community(comm)

        logger.info(f"Stored {len(communities)} communities to GraphStore")

    async def _create_has_child_relationships(
        self, communities: List[Community]
    ) -> None:
        """Create HAS_CHILD relationships in GraphStore."""
        for comm in communities:
            for child_id in comm.entity_ids:
                await self.graph_store.set_community_parent(child_id, comm.id)
            await self.graph_store.refresh_community_entity_count(comm.id)

        logger.info("Created HAS_CHILD relationships in GraphStore")

    async def get_hierarchy_tree(self) -> Dict[str, Any]:
        """
        Get complete hierarchy tree as nested dictionary.

        Returns:
            Dict with roots, levels, and adjacency information
        """
        hierarchy = await self.build_hierarchy()

        def serialize_community(comm: Community) -> Dict[str, Any]:
            return {
                "id": comm.id,
                "level": comm.level,
                "parent_id": comm.parent_id,
                "title": comm.title,
                "summary": comm.summary,
                "entity_count": len(comm.entity_ids),
                "rank": comm.rank,
                "created_at": comm.created_at,
            }

        def build_node(comm_id: str) -> Dict[str, Any]:
            comm = hierarchy.communities[comm_id]
            node = serialize_community(comm)
            node["children"] = [
                build_node(child_id)
                for child_id in hierarchy.adjacency.get(comm_id, [])
                if child_id in hierarchy.communities
            ]
            return node

        root_ids = sorted(
            comm_id
            for comm_id, comm in hierarchy.communities.items()
            if comm.parent_id is None
        )

        level_mapping: Dict[int, List[Dict[str, Any]]] = {}
        for comm in hierarchy.communities.values():
            level_mapping.setdefault(comm.level, []).append(serialize_community(comm))
        for communities in level_mapping.values():
            communities.sort(key=lambda item: (-item.get("rank", 0.0), item["id"]))

        max_level = max(level_mapping.keys(), default=-1)

        return {
            "roots": [build_node(comm_id) for comm_id in root_ids],
            "levels": level_mapping,
            "adjacency": hierarchy.adjacency,
            "communities": {
                comm_id: serialize_community(comm)
                for comm_id, comm in hierarchy.communities.items()
            },
            "max_level": max_level,
            "total_communities": len(hierarchy.communities),
        }

    async def get_ancestors(self, community_id: str) -> List[Dict[str, Any]]:
        """
        Get all ancestors of a community.

        Args:
            community_id: ID of community to query

        Returns:
            List of ancestor communities (closest first)
        """
        return await self.graph_store.get_community_ancestors(community_id)

    async def get_descendants(self, community_id: str) -> List[Dict[str, Any]]:
        """
        Get all descendants of a community.

        Args:
            community_id: ID of community to query

        Returns:
            List of descendant communities (immediate children first)
        """
        return await self.graph_store.get_community_descendants(community_id)

    async def get_level_communities(self, level: int) -> List[Dict[str, Any]]:
        """
        Get all communities at a specific level.

        Args:
            level: Hierarchy level (0=leaf, higher=more aggregated)

        Returns:
            List of communities at the requested level
        """
        return await self.graph_store.list_communities(level=level, limit=None)


# ============================================
# Utility Functions
# ============================================


async def rebuild_hierarchy(
    max_levels: Optional[int] = None,
    resolution: Optional[float] = None,
) -> CommunityHierarchy:
    """
    Rebuild the entire community hierarchy.

    Args:
        max_levels: Maximum hierarchy depth
        resolution: Leiden resolution parameter

    Returns:
        CommunityHierarchy with all levels
    """
    builder = HierarchyBuilder()
    return await builder.build_hierarchy(max_levels=max_levels, resolution=resolution)


async def get_community_path(
    community_id: str,
) -> List[Dict[str, Any]]:
    """
    Get the full path from root to a community.

    Args:
        community_id: ID of community

    Returns:
        List of communities from root to target (inclusive)
    """
    return await GraphStore().get_community_path(community_id)
