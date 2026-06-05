"""Test configuration and fixtures for Memory Graph tests."""

import os
import sys
import pytest
import httpx
import pytest_asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("MEMORY_GRAPH_API_TOKEN", "test-api-token")

from src.core.config import get_settings


# ============================================
# Fixtures
# ============================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def phase1_import_fixture_dir() -> Path:
    """Directory containing sample export fixtures for Phase 1 import coverage."""
    return Path(__file__).parent / "fixtures" / "phase1_import"


@pytest_asyncio.fixture
async def client():
    """Create async API test client."""
    from src.api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": "Bearer test-api-token"},
    ) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    """Keep config cache isolated between tests."""
    monkeypatch.setenv("MEMORY_GRAPH_API_TOKEN", "test-api-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    from src.core.config import (
        Settings,
        LLMConfig,
        DatabaseConfig,
        VectorConfig,
        EmbeddingConfig,
        StorageConfig,
        AppConfig,
        AdvancedConfig,
    )

    return Settings(
        version="1.0.0",
        llm=LLMConfig(
            provider="openai",
            openai=MagicMock(
                api_key="test-key", model="gpt-4o", base_url="https://api.openai.com/v1"
            ),
            anthropic=MagicMock(api_key="", model="claude-sonnet-4-20250514"),
            ollama=MagicMock(url="http://localhost:11434", model="qwen2.5:14b"),
        ),
        embedding=EmbeddingConfig(
            model="bge-m3",
            dimensions=768,
            cloud_model="text-embedding-3-small",
            cloud_dimensions=1536,
        ),
        database=DatabaseConfig(
            vector=VectorConfig(
                type="faiss",
                faiss=MagicMock(persist_directory="./data/faiss"),
            ),
        ),
        storage=StorageConfig(data_dir="./data", models_dir="./models"),
        app=AppConfig(host="0.0.0.0", port=8000, debug=True),
        advanced=AdvancedConfig(extraction_batch_size=10, top_k=5, community_level=2),
    )


@pytest.fixture
def sample_text():
    """Sample text for entity extraction testing."""
    return """
    Today I had a discussion about the Cursor project with John and Sarah.
    Cursor is an AI-powered code editor built on VS Code.
    It uses the GraphRAG architecture for memory management.
    John mentioned that the project started in 2023.
    Sarah is working on the embedding model integration.
    """


@pytest.fixture
def sample_entity():
    """Create a sample entity for testing."""
    from src.core.entity_extractor import Entity
    from datetime import datetime

    return Entity(
        id="test-entity-1",
        name="Cursor",
        type="project",
        properties={"description": "AI code editor"},
        source_text="Sample source text",
        confidence=0.95,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_relationship():
    """Create a sample relationship for testing."""
    from src.core.entity_extractor import Relationship
    from datetime import datetime

    return Relationship(
        id="test-rel-1",
        source_id="test-entity-1",
        target_id="test-entity-2",
        type="depends_on",
        properties={},
        confidence=0.9,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_embedding():
    """Create a sample embedding vector."""
    import numpy as np

    return np.random.rand(768).tolist()


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.chat = AsyncMock(return_value="Test response")
    provider.generate = AsyncMock(return_value="Test generated text")
    provider.embed = AsyncMock(return_value=[[0.1] * 768])
    provider.test_connection = AsyncMock(return_value=True)
    return provider


@pytest.fixture
def sample_conversation_data():
    """Sample conversation data for parser testing."""
    return {
        "title": "Test Conversation",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing great, thank you!"},
        ],
        "create_time": 1704067200,
    }


# ============================================
# Community Detection Fixtures
# ============================================


@pytest.fixture
def sample_igraph():
    """Create a sample igraph for testing."""
    import igraph as ig

    # Create a small graph with clear community structure
    # Two cliques connected by a single edge
    edges = [
        (0, 1),
        (0, 2),
        (1, 2),  # Clique 1
        (3, 4),
        (3, 5),
        (4, 5),  # Clique 2
        (2, 3),  # Bridge edge
    ]
    g = ig.Graph(n=6, edges=edges, directed=False)
    g.vs["id"] = [f"entity-{i}" for i in range(6)]
    g.vs["name"] = [f"Entity-{i}" for i in range(6)]
    g.vs["type"] = ["person"] * 6
    return g


@pytest.fixture
def mock_graph_store():
    """Create a mock GraphStore with entity and relationship data."""
    from src.core.graph_store import GraphStore
    from src.core.graph_store import GraphEntity, GraphRelationship

    store = MagicMock(spec=GraphStore)

    # Mock entity query results
    entities = [
        {"id": "entity-0", "name": "Alice", "type": "person"},
        {"id": "entity-1", "name": "Bob", "type": "person"},
        {"id": "entity-2", "name": "Charlie", "type": "person"},
        {"id": "entity-3", "name": "David", "type": "person"},
        {"id": "entity-4", "name": "Eve", "type": "person"},
        {"id": "entity-5", "name": "Frank", "type": "person"},
    ]

    # Mock relationship query results
    relationships = [
        {"source_id": "entity-0", "target_id": "entity-1", "type": "RELATES"},
        {"source_id": "entity-0", "target_id": "entity-2", "type": "RELATES"},
        {"source_id": "entity-1", "target_id": "entity-2", "type": "RELATES"},
        {"source_id": "entity-3", "target_id": "entity-4", "type": "RELATES"},
        {"source_id": "entity-3", "target_id": "entity-5", "type": "RELATES"},
        {"source_id": "entity-4", "target_id": "entity-5", "type": "RELATES"},
        {"source_id": "entity-2", "target_id": "entity-3", "type": "RELATES"},  # Bridge
    ]

    store.query_entities = AsyncMock(
        return_value=[
            GraphEntity(
                id=entity["id"],
                name=entity["name"],
                type=entity["type"],
            )
            for entity in entities
        ]
    )
    store.query_relationships_between_entities = AsyncMock(
        return_value=[
            GraphRelationship(
                id=f"rel-{idx}",
                source_id=relationship["source_id"],
                target_id=relationship["target_id"],
                type=relationship["type"],
            )
            for idx, relationship in enumerate(relationships)
        ]
    )
    store.close = AsyncMock()

    return store


@pytest.fixture
def mock_empty_graph_store():
    """Create a mock GraphStore with empty data."""
    from src.core.graph_store import GraphStore

    store = MagicMock(spec=GraphStore)
    store.query_entities = AsyncMock(return_value=[])
    store.query_relationships_between_entities = AsyncMock(return_value=[])
    store.close = AsyncMock()

    return store
