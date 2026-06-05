"""
Test script for GraphConverter
Creates sample data in GraphStore and tests export/import
"""

import asyncio
import logging
from datetime import datetime

import pytest

from src.core.graph_store import GraphStore, GraphEntity, GraphRelationship
from src.core.graph_converter import GraphConverter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_sample_data():
    """Create sample entities and relationships for testing"""
    graph_store = GraphStore()

    # Create sample entities
    entities = [
        GraphEntity(
            id="e1",
            name="Alice",
            type="Person",
            properties={"age": 30},
            created_at=datetime.now(),
        ),
        GraphEntity(
            id="e2",
            name="Bob",
            type="Person",
            properties={"age": 25},
            created_at=datetime.now(),
        ),
        GraphEntity(
            id="e3",
            name="Charlie",
            type="Person",
            properties={"age": 35},
            created_at=datetime.now(),
        ),
        GraphEntity(
            id="e4",
            name="CompanyA",
            type="Organization",
            properties={"industry": "Tech"},
            created_at=datetime.now(),
        ),
        GraphEntity(
            id="e5",
            name="ProjectX",
            type="Project",
            properties={"status": "active"},
            created_at=datetime.now(),
        ),
    ]

    # Create entities
    for entity in entities:
        await graph_store.create_entity(entity)
        logger.info(f"Created entity: {entity.name}")

    # Create relationships
    relationships = [
        GraphRelationship(
            id="r1",
            source_id="e1",
            target_id="e2",
            type="KNOWS",
            properties={"since": "2020"},
            created_at=datetime.now(),
        ),
        GraphRelationship(
            id="r2",
            source_id="e2",
            target_id="e3",
            type="KNOWS",
            properties={"since": "2019"},
            created_at=datetime.now(),
        ),
        GraphRelationship(
            id="r3",
            source_id="e1",
            target_id="e4",
            type="WORKS_FOR",
            properties={},
            created_at=datetime.now(),
        ),
        GraphRelationship(
            id="r4",
            source_id="e2",
            target_id="e4",
            type="WORKS_FOR",
            properties={},
            created_at=datetime.now(),
        ),
        GraphRelationship(
            id="r5",
            source_id="e3",
            target_id="e5",
            type="MANAGES",
            properties={},
            created_at=datetime.now(),
        ),
    ]

    for rel in relationships:
        await graph_store.create_relationship(rel)
        logger.info(
            f"Created relationship: {rel.source_id} -> {rel.target_id} ({rel.type})"
        )

    logger.info("Sample data created successfully")


async def export_graph():
    """Export the current graph to igraph."""
    converter = GraphConverter()

    # Export graph
    logger.info("=== Testing export_to_igraph ===")
    g = await converter.export_to_igraph()

    logger.info(f"igraph Graph created:")
    logger.info(f"  - Vertices: {g.vcount()}")
    logger.info(f"  - Edges: {g.ecount()}")

    # Print vertex attributes
    logger.info(f"  - Vertex attributes: {g.vertex_attributes()}")
    if g.vcount() > 0:
        logger.info(
            f"  - Sample vertex: id={g.vs[0]['id']}, name={g.vs[0]['name']}, type={g.vs[0]['type']}"
        )

    # Print edge attributes
    logger.info(f"  - Edge attributes: {g.edge_attributes()}")
    if g.ecount() > 0:
        logger.info(f"  - Sample edge: {g.es[0].tuple}, type={g.es[0]['type']}")

    # Validate export
    is_valid, message = await converter.validate_export(g)
    logger.info(f"  - Validation: {message}")

    return g


async def import_partition(g):
    """Import a mock community partition."""
    from igraph import VertexClustering

    converter = GraphConverter()

    # Create a mock partition (assign entities to communities)
    # For testing, we'll create 2 communities
    membership = []
    for i in range(g.vcount()):
        if i < 3:
            membership.append(0)  # First 3 entities in community 0
        else:
            membership.append(1)  # Rest in community 1

    partition = VertexClustering(g, membership)

    logger.info("=== Testing import_from_igraph ===")
    logger.info(f"Mock partition created with {len(partition)} communities")

    # Import community assignments
    member_counts = await converter.import_from_igraph(g, partition, community_level=0)

    logger.info(f"Community member counts:")
    for comm_id, count in member_counts.items():
        logger.info(f"  - {comm_id}: {count} members")

    return member_counts


@pytest.fixture
async def exported_graph():
    """Prepare sample data and export it once per test."""
    await setup_sample_data()
    return await export_graph()


@pytest.mark.asyncio
async def test_export_to_igraph(exported_graph):
    """Test exporting GraphStore graph to igraph."""
    converter = GraphConverter()
    g = exported_graph

    assert g.vcount() > 0
    assert g.ecount() > 0
    assert "id" in g.vertex_attributes()
    assert "type" in g.edge_attributes()

    is_valid, _ = await converter.validate_export(g)
    assert is_valid is True


@pytest.mark.asyncio
async def test_import_from_igraph(exported_graph):
    """Test importing community assignments back to GraphStore."""
    g = exported_graph
    member_counts = await import_partition(g)

    assert member_counts

    graph_store = GraphStore()
    communities = await graph_store.list_communities(limit=None)
    assert communities

    membership_count = await graph_store.count_community_memberships()
    assert membership_count >= g.vcount()


async def main():
    """Main test function"""
    try:
        # Setup sample data
        logger.info("Setting up sample data...")
        await setup_sample_data()

        # Test export
        g = await export_graph()

        # Test import
        await import_partition(g)

        logger.info("=== All tests passed! ===")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
