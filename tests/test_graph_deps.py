#!/usr/bin/env python3
"""
Test script to verify graph algorithm dependencies are working correctly.
"""


def test_igraph_import():
    """Test igraph library import and basic functionality."""
    import igraph

    print(f"[OK] igraph imported successfully (version: {igraph.__version__})")

    # Create a simple test graph
    g = igraph.Graph.Tree(10, 2)
    print(f"[OK] Created test graph with {g.vcount()} vertices and {g.ecount()} edges")
    # Test basic graph properties
    print(f"[OK] Graph diameter: {g.diameter()}")
    print(f"[OK] Graph density: {g.density():.3f}")

    assert g.vcount() == 10
    assert g.ecount() == 9
    assert g.diameter() > 0
    assert g.density() > 0


def test_leidenalg_import():
    """Test leidenalg library import and basic functionality."""
    import igraph
    import leidenalg

    print(f"[OK] leidenalg imported successfully (version: {leidenalg.__version__})")

    # Create a test graph
    g = igraph.Graph.Tree(10, 2)

    # Test Leiden clustering
    partition = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition)
    print(f"[OK] Leiden clustering completed with {len(partition)} communities")

    assert len(partition) > 0


def test_combined_integration():
    """Test both libraries working together."""
    import igraph
    import leidenalg

    # Create a more complex test graph
    g = igraph.Graph.Erdos_Renyi(50, 0.1)

    # Apply Leiden clustering
    partition = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition)

    # Calculate some community metrics
    modularity = partition.quality()
    print(f"[OK] Combined test: Modularity score = {modularity:.3f}")

    assert modularity >= 0


if __name__ == "__main__":
    print("Testing graph algorithm dependencies...")
    print("=" * 50)

    try:
        # Test individual imports
        test_igraph_import()
        print()
        test_leidenalg_import()
        print()

        # Test combined usage
        test_combined_integration()
        print()

        print("[SUCCESS] All tests passed! Graph dependencies are working correctly.")

    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        exit(1)
    except Exception as e:
        print(f"[ERROR] Test error: {e}")
        exit(1)
