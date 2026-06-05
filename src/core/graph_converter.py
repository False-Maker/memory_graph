"""
Graph Converter Module
Convert between GraphStore (NetworkX + SQLite) and igraph formats for community detection
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

import igraph as ig

from src.core.graph_store import GraphStore

logger = logging.getLogger(__name__)


# ============================================
# Graph Converter
# ============================================


class GraphConverter:
    """
    Graph Converter
    Export GraphStore (NetworkX + SQLite) graph to igraph for community detection algorithms
    Import community assignments back to GraphStore
    """

    def __init__(self, graph_store: Optional[GraphStore] = None):
        """
        Initialize converter

        Args:
            graph_store: GraphStore instance used for graph access
        """
        self.graph_store = graph_store or GraphStore()
        self._entity_id_to_idx: Dict[str, int] = {}
        self._idx_to_entity_id: Dict[int, str] = {}
        self._direct_fetch_threshold = 5000

    # ========================================
    # Export: GraphStore → igraph
    # ========================================

    async def export_to_igraph(
        self,
        entity_types: Optional[List[str]] = None,
        batch_size: int = 1000,
        progress_callback: Optional[callable] = None,
    ) -> ig.Graph:
        """
        Export the GraphStore graph to igraph format

        Args:
            entity_types: Filter to specific entity types (None = all)
            batch_size: Batch size for fetching nodes (for large graphs)
            progress_callback: Optional callback for progress updates

        Returns:
            igraph.Graph with nodes and edges from GraphStore
        """
        logger.info("Starting GraphStore → igraph export...")

        # Step 1: Fetch all Entity nodes
        entities = await self._fetch_entities_batch(
            entity_types=entity_types,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )

        if not entities:
            logger.warning("No entities found in GraphStore")
            return ig.Graph(n=0)

        # Step 2: Build entity ID → index mapping
        self._build_entity_mapping(entities)

        # Step 3: Create igraph Graph
        g = ig.Graph(n=len(entities))

        # Add vertex attributes
        g.vs["id"] = [e["id"] for e in entities]
        g.vs["name"] = [e["name"] for e in entities]
        g.vs["type"] = [e["type"] for e in entities]
        g.vs["graph_entity_id"] = [e["id"] for e in entities]  # For mapping back

        logger.info(f"Created igraph with {g.vcount()} vertices")

        # Step 4: Fetch and add edges
        await self._add_edges(
            g=g,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )

        logger.info(f"Export complete: {g.vcount()} nodes, {g.ecount()} edges")

        return g

    async def _fetch_entities_batch(
        self,
        entity_types: Optional[List[str]],
        batch_size: int,
        progress_callback: Optional[callable],
    ) -> List[Dict[str, Any]]:
        """
        Fetch all Entity nodes with pagination for large graphs

        Args:
            entity_types: Filter to specific entity types
            batch_size: Number of entities per batch
            progress_callback: Progress callback

        Returns:
            List of entity dictionaries
        """
        entities = []
        skip = 0
        has_more = True

        # Count total entities for progress tracking
        total_count = await self._count_entities(entity_types)
        logger.info(f"Fetching {total_count} entities from GraphStore...")

        if total_count <= self._direct_fetch_threshold:
            batch_entities = await self.graph_store.query_entities(
                entity_types=entity_types,
                limit=None,
                offset=0,
            )
            entities = [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                }
                for entity in batch_entities
            ]
            if progress_callback and total_count:
                progress_callback("fetching_entities", len(entities), total_count)
            return entities

        while has_more:
            batch_entities = await self.graph_store.query_entities(
                entity_types=entity_types,
                limit=batch_size,
                offset=skip,
            )
            batch = [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                }
                for entity in batch_entities
            ]

            if not batch:
                has_more = False
            else:
                entities.extend(batch)
                skip += batch_size

                # Progress update
                if progress_callback:
                    progress_callback("fetching_entities", len(entities), total_count)

                logger.debug(f"Fetched {len(entities)}/{total_count} entities")

                # Stop if we've fetched all
                if len(entities) >= total_count:
                    has_more = False

        return entities

    async def _count_entities(self, entity_types: Optional[List[str]]) -> int:
        """Count total entities for progress tracking"""
        return await self.graph_store.count_entities(entity_types=entity_types)

    def _build_entity_mapping(self, entities: List[Dict[str, Any]]) -> None:
        """
        Build bidirectional mapping between entity IDs and vertex indices

        Args:
            entities: List of entity dictionaries
        """
        self._entity_id_to_idx = {
            entity["id"]: idx for idx, entity in enumerate(entities)
        }
        self._idx_to_entity_id = {
            idx: entity["id"] for idx, entity in enumerate(entities)
        }

    async def _add_edges(
        self,
        g: ig.Graph,
        batch_size: int,
        progress_callback: Optional[callable],
    ) -> None:
        """
        Fetch and add RELATES relationships to igraph

        Args:
            g: igraph Graph to add edges to
            batch_size: Batch size for fetching edges
            progress_callback: Progress callback
        """
        logger.info("Fetching relationships from GraphStore...")

        entity_ids = list(self._entity_id_to_idx.keys())
        total_edges = await self._count_edges(entity_ids)
        logger.info(f"Fetching {total_edges} relationships...")
        edges = []
        edge_types = []

        if total_edges <= self._direct_fetch_threshold:
            batch = await self.graph_store.query_relationships_between_entities(
                entity_ids,
                limit=None,
                offset=0,
            )
            for record in batch:
                source_id = record.source_id
                target_id = record.target_id
                rel_type = record.type

                if (
                    source_id in self._entity_id_to_idx
                    and target_id in self._entity_id_to_idx
                ):
                    edges.append(
                        (
                            self._entity_id_to_idx[source_id],
                            self._entity_id_to_idx[target_id],
                        )
                    )
                    edge_types.append(rel_type)

            if progress_callback and total_edges:
                progress_callback("fetching_edges", len(edges), total_edges)
        else:
            skip = 0
            has_more = True
            while has_more:
                batch = await self.graph_store.query_relationships_between_entities(
                    entity_ids,
                    limit=batch_size,
                    offset=skip,
                )

                if not batch:
                    has_more = False
                else:
                    for record in batch:
                        source_id = record.source_id
                        target_id = record.target_id
                        rel_type = record.type

                        # Map to vertex indices
                        if (
                            source_id in self._entity_id_to_idx
                            and target_id in self._entity_id_to_idx
                        ):
                            edges.append(
                                (
                                    self._entity_id_to_idx[source_id],
                                    self._entity_id_to_idx[target_id],
                                )
                            )
                            edge_types.append(rel_type)

                    skip += batch_size

                    # Progress update
                    if progress_callback:
                        progress_callback("fetching_edges", len(edges), total_edges)

                    logger.debug(f"Fetched {len(edges)}/{total_edges} edges")

                    # Stop if we've fetched all
                    if len(edges) >= total_edges:
                        has_more = False

        # Add edges to graph
        if edges:
            g.add_edges(edges)
            g.es["type"] = edge_types
            logger.info(f"Added {g.ecount()} edges to igraph")

    async def _count_edges(self, entity_ids: List[str]) -> int:
        """Count total edges for progress tracking"""
        return await self.graph_store.count_relationships_between_entities(entity_ids)

    # ========================================
    # Import: igraph → GraphStore (community assignments)
    # ========================================

    async def import_from_igraph(
        self,
        g: ig.Graph,
        partition: Any,
        community_level: int = 0,
        batch_size: int = 500,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, int]:
        """
        Import community assignments from igraph partition to GraphStore

        Creates BELONGS_TO relationships from Entity to Community nodes.
        Communities are created if they don't exist.

        Args:
            g: igraph Graph with vertices
            partition: igraph.VertexClustering partition from community detection
            community_level: Hierarchy level for communities
            batch_size: Batch size for updating community assignments
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary mapping community_id → member count
        """
        logger.info("Starting igraph → GraphStore import (community assignments)...")

        # Build community assignments
        community_assignments: Dict[int, List[str]] = {}
        for vertex_idx in range(g.vcount()):
            community_id = partition.membership[vertex_idx]
            entity_id = g.vs[vertex_idx]["graph_entity_id"]

            if community_id not in community_assignments:
                community_assignments[community_id] = []
            community_assignments[community_id].append(entity_id)

        logger.info(f"Partition contains {len(community_assignments)} communities")

        # Create communities and BELONGS_TO relationships
        community_member_counts = {}
        total_processed = 0
        total_communities = len(community_assignments)

        for comm_id, entity_ids in community_assignments.items():
            # Generate unique community ID
            community_node_id = f"comm_{community_level}_{comm_id}"

            # Create Community node
            await self._create_community_node(
                community_id=community_node_id,
                level=community_level,
                entity_ids=entity_ids,
            )

            # Create BELONGS_TO relationships
            await self._create_belongs_to_relationships(
                community_id=community_node_id,
                entity_ids=entity_ids,
                batch_size=batch_size,
            )

            community_member_counts[community_node_id] = len(entity_ids)
            total_processed += 1

            # Progress update
            if progress_callback:
                progress_callback(
                    "importing_communities", total_processed, total_communities
                )

            logger.debug(
                f"Imported community {community_node_id}: {len(entity_ids)} members"
            )

        logger.info(
            f"Import complete: {total_communities} communities, "
            f"{sum(community_member_counts.values())} total members"
        )

        return community_member_counts

    async def _create_community_node(
        self,
        community_id: str,
        level: int,
        entity_ids: List[str],
    ) -> None:
        """
        Create or update a Community node in GraphStore

        Args:
            community_id: Unique community ID
            level: Hierarchy level
            entity_ids: List of member entity IDs
        """
        community = type(
            "CommunityRecord",
            (),
            {
                "id": community_id,
                "level": level,
                "parent_id": None,
                "title": f"Community {community_id}",
                "summary": "",
                "rank": 0.0,
                "entity_ids": entity_ids,
                "created_at": datetime.now(),
            },
        )()
        await self.graph_store.create_community(community)

    async def _create_belongs_to_relationships(
        self,
        community_id: str,
        entity_ids: List[str],
        batch_size: int,
    ) -> None:
        """
        Create BELONGS_TO relationships from entities to community

        Args:
            community_id: Target community ID
            entity_ids: List of entity IDs to connect
            batch_size: Batch size for updates
        """
        del batch_size  # Membership persistence is handled natively in one call.
        await self.graph_store.replace_community_memberships(
            community_id=community_id,
            entity_ids=entity_ids,
            created_at=datetime.now().isoformat(),
        )

    # ========================================
    # Validation
    # ========================================

    async def validate_export(
        self, g: ig.Graph, tolerance: float = 0.01
    ) -> Tuple[bool, str]:
        """
        Validate that igraph graph matches GraphStore

        Args:
            g: igraph Graph to validate
            tolerance: Acceptable percentage difference

        Returns:
            Tuple of (is_valid, message)
        """
        # Count nodes in GraphStore
        graph_node_count = await self._count_entities(None)
        igraph_node_count = g.vcount()

        # Count edges in GraphStore
        entity_ids = list(self._entity_id_to_idx.keys()) or list(g.vs["id"])
        graph_edge_count = await self._count_edges(entity_ids)
        igraph_edge_count = g.ecount()

        # Compare with tolerance
        node_diff_pct = abs(graph_node_count - igraph_node_count) / max(
            graph_node_count, 1
        )
        edge_diff_pct = abs(graph_edge_count - igraph_edge_count) / max(
            graph_edge_count, 1
        )

        if node_diff_pct > tolerance or edge_diff_pct > tolerance:
            return (
                False,
                f"Validation failed: GraphStore ({graph_node_count} nodes, {graph_edge_count} edges) "
                f"vs igraph ({igraph_node_count} nodes, {igraph_edge_count} edges)",
            )

        return (
            True,
            f"Validation passed: {igraph_node_count} nodes, {igraph_edge_count} edges",
        )

    def clear_mapping(self) -> None:
        """Clear entity ID → index mappings"""
        self._entity_id_to_idx.clear()
        self._idx_to_entity_id.clear()
