"""
Community Detection Module
Implements Leiden algorithm for community detection in graphs
"""

import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

import igraph as ig
import leidenalg as la

from src.core.graph_store import GraphStore
from src.core.models.community import Community, CommunityHierarchy
from src.core.config import get_settings
from src.utils.logger import logger


@dataclass
class DetectionResult:
    """Result of community detection"""

    communities: List[Community]
    hierarchy: CommunityHierarchy
    modularity: float
    num_communities: int
    size_distribution: Dict[int, int]  # community_size -> count


class CommunityDetector:
    """
    Community Detector using Leiden algorithm
    Detects communities in the graph and stores them to GraphStore
    """

    def __init__(self, graph_store: Optional[GraphStore] = None):
        """
        Initialize Community Detector

        Args:
            graph_store: Graph store instance (optional, uses singleton if not provided)
        """
        self.graph_store = graph_store or GraphStore()
        self.settings = get_settings()
        self.config = self.settings.advanced.community_detection

    async def detect_communities(
        self,
        algorithm: Optional[str] = None,
        resolution: Optional[float] = None,
        min_community_size: Optional[int] = None,
    ) -> DetectionResult:
        """
        Detect communities using Leiden algorithm

        Args:
            resolution: Resolution parameter for Leiden (higher = more communities)
            min_community_size: Minimum entities per community

        Returns:
            DetectionResult with communities and statistics
        """
        if not self.config.enabled:
            logger.info("Community detection is disabled in config")
            return DetectionResult(
                communities=[],
                hierarchy=CommunityHierarchy(),
                modularity=0.0,
                num_communities=0,
                size_distribution={},
            )

        algorithm = algorithm or self.config.algorithm
        if algorithm != "leiden":
            logger.warning(
                f"Algorithm '{algorithm}' is not implemented in CommunityDetector, falling back to 'leiden'"
            )
            algorithm = "leiden"

        resolution = resolution or self.config.resolution
        min_community_size = min_community_size or self.config.min_community_size

        logger.info(f"Starting community detection with algorithm={algorithm}, resolution={resolution}")

        # Step 1: Export graph from GraphStore to igraph
        logger.info("Exporting graph from GraphStore...")
        ig_graph, entity_id_map = await self._export_to_igraph()

        if ig_graph.vcount() == 0:
            logger.warning("No entities found in graph, skipping community detection")
            return DetectionResult(
                communities=[],
                hierarchy=CommunityHierarchy(),
                modularity=0.0,
                num_communities=0,
                size_distribution={},
            )

        # Step 2: Handle small graphs - single community
        if ig_graph.vcount() < 10:
            logger.info(
                f"Small graph detected ({ig_graph.vcount()} nodes), creating single community"
            )
            return await self._create_single_community(entity_id_map)

        # Step 3: Run Leiden algorithm
        logger.info(
            f"Running Leiden algorithm on {ig_graph.vcount()} nodes, {ig_graph.ecount()} edges..."
        )
        partition = self._run_leiden(ig_graph, resolution)

        # Step 4: Calculate modularity
        modularity = partition.quality()
        logger.info(f"Leiden completed. Modularity: {modularity:.4f}")

        # Step 5: Convert partition to Community objects
        communities = await self._partition_to_communities(
            partition, entity_id_map, min_community_size
        )

        # Step 6: Store communities to GraphStore
        await self._store_communities(communities)

        # Step 7: Create BELONGS_TO relationships
        await self._create_belongs_to_relationships(communities)

        # Step 8: Build hierarchy (flat for now, level 0)
        hierarchy = CommunityHierarchy(
            communities={c.id: c for c in communities},
            adjacency={},  # No hierarchy yet
        )

        # Step 9: Calculate size distribution
        size_distribution = self._calculate_size_distribution(communities)

        logger.info(
            f"Community detection complete: {len(communities)} communities, "
            f"modularity={modularity:.4f}"
        )
        self._log_community_stats(communities, modularity, size_distribution)

        return DetectionResult(
            communities=communities,
            hierarchy=hierarchy,
            modularity=modularity,
            num_communities=len(communities),
            size_distribution=size_distribution,
        )

    async def _export_to_igraph(self) -> Tuple[ig.Graph, Dict[int, str]]:
        """
        Export the GraphStore graph to igraph format

        Returns:
            Tuple of (igraph.Graph, node_id_map where igraph_index -> entity_id)
        """
        entities = await self.graph_store.query_entities(limit=None)
        entity_id_map: Dict[int, str] = {}
        entity_index_map: Dict[str, int] = {}
        edges = []

        for idx, entity in enumerate(entities):
            entity_id_map[idx] = entity.id
            entity_index_map[entity.id] = idx

        relationships = await self.graph_store.query_relationships_between_entities(
            list(entity_index_map.keys()),
            limit=None,
        )
        for record in relationships:
            if record.source_id in entity_index_map and record.target_id in entity_index_map:
                edges.append(
                    (
                        entity_index_map[record.source_id],
                        entity_index_map[record.target_id],
                    )
                )

        # Create igraph
        ig_graph = ig.Graph(
            n=len(entities),
            edges=edges,
            directed=False,
        )

        # Add vertex attributes
        ig_graph.vs["id"] = [entity_id_map[i] for i in range(len(entities))]
        ig_graph.vs["name"] = [entities[i].name for i in range(len(entities))]
        ig_graph.vs["type"] = [entities[i].type for i in range(len(entities))]

        # Add edge attribute
        if edges:
            ig_graph.es["type"] = "RELATES"

        logger.debug(
            f"Exported {ig_graph.vcount()} nodes, {ig_graph.ecount()} edges to igraph"
        )
        return ig_graph, entity_id_map

    def _run_leiden(self, ig_graph: ig.Graph, resolution: float) -> la.VertexPartition:
        """
        Run Leiden algorithm on igraph

        Args:
            ig_graph: igraph Graph object
            resolution: Resolution parameter (higher = more/fine-grained communities)

        Returns:
            Leiden partition object
        """
        # Handle disconnected components - each component gets communities
        if not ig_graph.is_connected():
            logger.warning(
                "Graph is disconnected, Leiden will handle components separately"
            )

        # Use CPM partition which supports resolution parameter
        # CPM (Constant Potts Model) allows control over community granularity
        partition = la.find_partition(
            ig_graph,
            la.CPMVertexPartition,
            resolution_parameter=resolution,
            n_iterations=-1,  # Run until convergence
            seed=42,  # For reproducibility
        )

        return partition

    async def _partition_to_communities(
        self,
        partition: la.ModularityVertexPartition,
        entity_id_map: Dict[int, str],
        min_community_size: int,
    ) -> List[Community]:
        """
        Convert Leiden partition to Community objects

        Args:
            partition: Leiden partition result
            entity_id_map: igraph index -> entity_id mapping
            min_community_size: Minimum entities per community

        Returns:
            List of Community objects
        """
        # Group entities by community membership
        community_members: Dict[int, List[str]] = {}

        for idx, membership in enumerate(partition.membership):
            entity_id = entity_id_map[idx]
            if membership not in community_members:
                community_members[membership] = []
            community_members[membership].append(entity_id)

        # Create Community objects
        communities = []
        for comm_id, entity_ids in community_members.items():
            # Filter by minimum size
            if len(entity_ids) < min_community_size:
                logger.debug(
                    f"Skipping community {comm_id} with {len(entity_ids)} entities "
                    f"(below minimum {min_community_size})"
                )
                continue

            community = Community(
                id=str(uuid.uuid4()),
                level=0,  # Level 0 = leaf communities
                parent_id=None,  # No parent yet
                entity_ids=entity_ids,
                summary="",  # Generated later
                title=f"Community {comm_id}",
                rank=0.0,  # Calculated later
                created_at=datetime.now(),
            )
            communities.append(community)

        return communities

    async def _create_single_community(
        self, entity_id_map: Dict[int, str]
    ) -> DetectionResult:
        """
        Create a single community for small graphs

        Args:
            entity_id_map: igraph index -> entity_id mapping

        Returns:
            DetectionResult with single community
        """
        entity_ids = list(entity_id_map.values())

        community = Community(
            id=str(uuid.uuid4()),
            level=0,
            parent_id=None,
            entity_ids=entity_ids,
            summary="All entities in a single community (small graph)",
            title="Root Community",
            rank=1.0,
            created_at=datetime.now(),
        )

        await self._store_communities([community])
        await self._create_belongs_to_relationships([community])

        hierarchy = CommunityHierarchy(
            communities={community.id: community},
            adjacency={},
        )

        return DetectionResult(
            communities=[community],
            hierarchy=hierarchy,
            modularity=0.0,  # Single community has modularity 0
            num_communities=1,
            size_distribution={len(entity_ids): 1},
        )

    async def _store_communities(self, communities: List[Community]) -> None:
        """
        Store communities to GraphStore

        Args:
            communities: List of Community objects
        """
        for community in communities:
            await self.graph_store.create_community(community)

        logger.info(f"Stored {len(communities)} communities to GraphStore")

    async def _create_belongs_to_relationships(
        self, communities: List[Community]
    ) -> None:
        """
        Create BELONGS_TO relationships between entities and communities

        Args:
            communities: List of Community objects
        """
        for community in communities:
            await self.graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=community.entity_ids,
                created_at=datetime.now().isoformat(),
            )

        total_rels = sum(len(c.entity_ids) for c in communities)
        logger.info(f"Created {total_rels} BELONGS_TO relationships")

    def _calculate_size_distribution(
        self, communities: List[Community]
    ) -> Dict[int, int]:
        """
        Calculate community size distribution

        Args:
            communities: List of Community objects

        Returns:
            Dictionary mapping size -> count
        """
        distribution: Dict[int, int] = {}
        for community in communities:
            size = len(community.entity_ids)
            distribution[size] = distribution.get(size, 0) + 1
        return distribution

    def _log_community_stats(
        self,
        communities: List[Community],
        modularity: float,
        size_distribution: Dict[int, int],
    ) -> None:
        """
        Log community detection statistics

        Args:
            communities: List of Community objects
            modularity: Modularity score
            size_distribution: Size distribution
        """
        logger.info("=" * 50)
        logger.info("Community Detection Statistics:")
        logger.info(f"  Total communities: {len(communities)}")
        logger.info(f"  Modularity: {modularity:.4f}")
        logger.info(f"  Size distribution: {size_distribution}")

        if communities:
            sizes = [len(c.entity_ids) for c in communities]
            logger.info(f"  Average size: {sum(sizes) / len(sizes):.1f}")
            logger.info(f"  Min size: {min(sizes)}")
            logger.info(f"  Max size: {max(sizes)}")

            # Top 5 largest communities
            sorted_communities = sorted(
                communities, key=lambda c: len(c.entity_ids), reverse=True
            )
            logger.info("  Top 5 largest communities:")
            for i, comm in enumerate(sorted_communities[:5], 1):
                logger.info(f"    {i}. {comm.title}: {len(comm.entity_ids)} entities")

        logger.info("=" * 50)


# ============================================
# Convenience Functions
# ============================================


async def detect_communities(
    graph_store: Optional[GraphStore] = None,
    resolution: Optional[float] = None,
) -> DetectionResult:
    """
    Convenience function to detect communities

    Args:
        graph_store: Graph store instance (optional)
        resolution: Resolution parameter (optional)

    Returns:
        DetectionResult with communities and statistics
    """
    detector = CommunityDetector(graph_store)
    return await detector.detect_communities(resolution=resolution)
