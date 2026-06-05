"""Tests for Vector Store module."""

import logging
import pytest
import numpy as np
import faiss
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from src.core.vector_store import (
    MemoryDocument,
    SearchResult,
    VectorStore,
    get_vector_store,
)


class TestMemoryDocument:
    """Test MemoryDocument class."""

    def test_creation(self):
        """Test creating a MemoryDocument."""
        doc = MemoryDocument(
            id="test-1",
            content="Test content",
            metadata={"source": "test"},
            embedding=[0.1, 0.2, 0.3]
        )
        assert doc.id == "test-1"
        assert doc.content == "Test content"
        assert doc.metadata == {"source": "test"}

    def test_creation_with_uuid(self):
        """Test document creation generates UUID."""
        import uuid as uuid_module
        # Test that id parameter works when provided
        doc = MemoryDocument(
            id="custom-id-123",
            content="Test content",
            metadata={}
        )
        assert doc.id == "custom-id-123"


class TestSearchResult:
    """Test SearchResult class."""

    def test_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            id="test-1",
            content="Test content",
            metadata={},
            distance=0.5
        )
        assert result.id == "test-1"
        assert result.distance == 0.5

    def test_relevance_calculation(self):
        """Test relevance score calculation."""
        result = SearchResult(
            id="test-1",
            content="Test content",
            metadata={},
            distance=0.3
        )
        assert result.relevance == 0.7

    def test_relevance_perfect_match(self):
        """Test relevance for perfect match."""
        result = SearchResult(
            id="test-1",
            content="Test",
            metadata={},
            distance=0.0
        )
        assert result.relevance == 1.0


class TestVectorStore:
    """Test VectorStore class."""

    @patch("src.core.vector_store.get_settings")
    def test_init(self, mock_get_settings):
        """Test VectorStore initialization."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {
            "type": "faiss",
            "persist_directory": "./data/faiss"
        }
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=768)
        assert store.dimension == 768

    @patch("src.core.vector_store.get_settings")
    def test_init_with_default_dimension(self, mock_get_settings):
        """Test VectorStore with default dimension."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        assert store.dimension == 768

    @patch("src.core.vector_store.get_settings")
    def test_init_uses_remote_cloud_dimensions_when_remote_first(self, mock_get_settings):
        """Remote-first embedding config should drive the vector dimension."""
        mock_settings = MagicMock()
        mock_settings.embedding.provider_preference = "remote_first"
        mock_settings.embedding.dimensions = 1024
        mock_settings.embedding.cloud_dimensions = 2048
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        assert store.dimension == 2048

    @patch("src.core.vector_store.get_settings")
    def test_init_normalizes_remote_preference_whitespace_and_case(self, mock_get_settings):
        """Whitespace and case in provider_preference should still select remote dimensions."""
        mock_settings = MagicMock()
        mock_settings.embedding.provider_preference = "  REMOTE_ONLY  "
        mock_settings.embedding.dimensions = 1024
        mock_settings.embedding.cloud_dimensions = 2048
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        assert store.dimension == 2048

    @patch("src.core.vector_store.get_settings")
    def test_init_invalid_preference_falls_back_to_local_dimensions(self, mock_get_settings):
        """Invalid provider_preference should fall back to local dimensions."""
        mock_settings = MagicMock()
        mock_settings.embedding.provider_preference = "unsupported"
        mock_settings.embedding.dimensions = 1024
        mock_settings.embedding.cloud_dimensions = 2048
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        assert store.dimension == 1024

    @patch("src.core.vector_store.get_settings")
    def test_init_ignores_boolean_cloud_dimensions(self, mock_get_settings):
        """Boolean cloud_dimensions should not override the configured vector dimension."""
        mock_settings = MagicMock()
        mock_settings.embedding.provider_preference = "remote_first"
        mock_settings.embedding.dimensions = 1024
        mock_settings.embedding.cloud_dimensions = True
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        assert store.dimension == 1024

    @patch("src.core.vector_store.get_settings")
    def test_init_ignores_boolean_explicit_dimension(self, mock_get_settings):
        """Boolean explicit dimension should not override embedding configuration."""
        mock_settings = MagicMock()
        mock_settings.embedding.provider_preference = "local_first"
        mock_settings.embedding.dimensions = 1024
        mock_settings.embedding.cloud_dimensions = 2048
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=True)
        assert store.dimension == 1024

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_add_memory(self, mock_get_settings):
        """Test adding a memory."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {
            "type": "faiss",
            "persist_directory": "./data/faiss"
        }
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        store._index = MagicMock()
        store._index.ntotal = 0
        store._save_index = MagicMock()

        result = await store.add_memory(
            memory_id="test-1",
            content="Test content",
            embedding=[0.1, 0.2, 0.3],
            metadata={"source": "test"}
        )

        assert result == "test-1"

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_get_memory(self, mock_get_settings):
        """Test getting a memory."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        doc = MemoryDocument(
            id="test-1",
            content="Test content",
            metadata={}
        )
        store._documents["test-1"] = doc

        result = await store.get_memory("test-1")
        assert result is not None
        assert result.content == "Test content"

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_get_memory_not_found(self, mock_get_settings):
        """Test getting non-existent memory."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        result = await store.get_memory("non-existent")
        assert result is None

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_update_memory(self, mock_get_settings):
        """Test updating a memory."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        doc = MemoryDocument(
            id="test-1",
            content="Original",
            metadata={}
        )
        store._documents["test-1"] = doc
        store._save_index = MagicMock()

        result = await store.update_memory(
            "test-1",
            content="Updated content"
        )
        
        assert result is True
        assert store._documents["test-1"].content == "Updated content"

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_delete_memory(self, mock_get_settings):
        """Test deleting a memory."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        store._documents["test-1"] = MagicMock()
        store._id_to_idx["test-1"] = 0
        store._idx_to_id[0] = "test-1"
        store._save_index = MagicMock()

        result = await store.delete_memory("test-1")
        
        assert result is True
        assert "test-1" not in store._documents

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_search_empty_index(self, mock_get_settings):
        """Test searching with empty index."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        store._index = MagicMock()
        store._index.ntotal = 0

        results = await store.search([0.1, 0.2, 0.3], top_k=5)
        
        assert results == []

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_get_count(self, mock_get_settings):
        """Test getting memory count."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore()
        store._documents = {
            "test-1": MagicMock(),
            "test-2": MagicMock(),
            "test-3": MagicMock()
        }

        count = await store.get_count()
        assert count == 3

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_clear_all(self, mock_get_settings):
        """Test clearing all memories."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        store._documents = {"test-1": MagicMock()}
        store._save_index = MagicMock()

        result = await store.clear_all()
        
        assert result is True
        assert len(store._documents) == 0

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_reembed_all(self, mock_get_settings):
        """Reembedding should refresh document vectors and rebuild the index."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        store._documents = {
            "test-1": MemoryDocument(id="test-1", content="A", metadata={}, embedding=[0.1, 0.2, 0.3]),
            "test-2": MemoryDocument(id="test-2", content="B", metadata={}, embedding=[0.4, 0.5, 0.6]),
        }
        store._save_index = MagicMock()

        async def embed_texts(texts):
            return [[0.9, 0.8, 0.7] for _ in texts]

        result = await store.reembed_all(embed_texts, batch_size=1)

        assert result["documents"] == 2
        assert result["reembedded"] == 2
        assert result["indexed"] == 2
        assert store._documents["test-1"].embedding == [0.9, 0.8, 0.7]
        assert store._documents["test-2"].embedding == [0.9, 0.8, 0.7]

    @pytest.mark.asyncio
    @patch("src.core.vector_store.get_settings")
    async def test_reembed_all_loads_persisted_documents_before_reembedding(self, mock_get_settings):
        """Reembedding should lazy-load persisted documents before counting them."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {"type": "faiss"}
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        persisted = MemoryDocument(id="persisted", content="A", metadata={}, embedding=[0.1, 0.2, 0.3])
        store._documents = {}
        store._save_index = MagicMock()

        def fake_get_index():
            store._documents = {"persisted": persisted}
            fake_index = MagicMock()
            fake_index.ntotal = 1
            fake_index.d = 3
            return fake_index

        store._get_index = fake_get_index

        async def embed_texts(texts):
            return [[0.9, 0.8, 0.7] for _ in texts]

        result = await store.reembed_all(embed_texts)

        assert result["documents"] == 1
        assert store._documents["persisted"].embedding == [0.9, 0.8, 0.7]

    @patch("src.core.vector_store.get_settings")
    def test_save_index_preserves_existing_files_when_atomic_write_fails(self, mock_get_settings, tmp_path):
        """Atomic persistence should not replace existing files on partial write failure."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {
            "type": "faiss",
            "persist_directory": str(tmp_path),
        }
        mock_get_settings.return_value = mock_settings

        store = VectorStore(dimension=3)
        store._index = MagicMock()
        store._index_path = tmp_path / "index.faiss"
        store._docs_path = tmp_path / "documents.pkl"
        store._documents = {
            "test-1": MemoryDocument(
                id="test-1",
                content="Test content",
                metadata={"source": "test"},
                embedding=[0.1, 0.2, 0.3],
            )
        }
        store._id_to_idx = {"test-1": 1}
        store._idx_to_id = {1: "test-1"}
        store._next_vector_id = 2

        store._index_path.write_bytes(b"old-index")
        store._docs_path.write_bytes(b"old-documents")

        def fake_write_index(_index, path):
            Path(path).write_bytes(b"new-index")

        with patch("src.core.vector_store.faiss.write_index", side_effect=fake_write_index):
            with patch.object(
                store,
                "_save_documents_payload",
                side_effect=RuntimeError("metadata write failed"),
            ):
                with pytest.raises(RuntimeError, match="metadata write failed"):
                    store._save_index()

        assert store._index_path.read_bytes() == b"old-index"
        assert store._docs_path.read_bytes() == b"old-documents"
        assert list(tmp_path.glob("*.tmp")) == []

    @patch("src.core.vector_store.get_settings")
    def test_load_index_logs_warning_when_documents_are_corrupted(self, mock_get_settings, tmp_path, caplog):
        """Corrupted metadata should emit a warning instead of failing silently."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {
            "type": "faiss",
            "persist_directory": str(tmp_path),
        }
        mock_get_settings.return_value = mock_settings

        docs_path = tmp_path / "documents.pkl"
        docs_path.write_bytes(b"not-a-pickle")

        store = VectorStore(dimension=3)

        with caplog.at_level(logging.WARNING):
            store._load_index()

        assert "Failed to load vector store documents" in caplog.text
        assert store._documents == {}
        assert store._id_to_idx == {}
        assert store._idx_to_id == {}
        assert store._get_index().ntotal == 0

    @patch("src.core.vector_store.get_settings")
    def test_load_index_repairs_partially_replaced_index_from_documents(self, mock_get_settings, tmp_path, caplog):
        """If only the FAISS file was replaced, reload should rebuild from committed document metadata."""
        mock_settings = MagicMock()
        mock_settings.database.vector = {
            "type": "faiss",
            "persist_directory": str(tmp_path),
        }
        mock_get_settings.return_value = mock_settings

        committed = VectorStore(dimension=3)
        committed._index_path = tmp_path / "index.faiss"
        committed._docs_path = tmp_path / "documents.pkl"
        committed._index = committed._create_index()
        committed._documents = {
            "stable": MemoryDocument(
                id="stable",
                content="Committed content",
                metadata={"source": "committed"},
                embedding=[0.1, 0.2, 0.3],
            )
        }
        committed._id_to_idx = {"stable": 1}
        committed._idx_to_id = {1: "stable"}
        committed._next_vector_id = 2
        vector = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        faiss.normalize_L2(vector)
        committed._index.add_with_ids(vector, np.array([1], dtype=np.int64))
        committed._save_index()

        partial_index = committed._create_index()
        partial_vectors = np.array(
            [
                [0.1, 0.2, 0.3],
                [0.3, 0.2, 0.1],
            ],
            dtype=np.float32,
        )
        faiss.normalize_L2(partial_vectors)
        partial_index.add_with_ids(partial_vectors, np.array([1, 2], dtype=np.int64))
        faiss.write_index(partial_index, str(committed._index_path))

        recovered = VectorStore(dimension=3)
        with caplog.at_level(logging.WARNING):
            recovered._load_index()

        assert "metadata mismatch detected" in caplog.text
        assert recovered._documents.keys() == {"stable"}
        assert recovered._id_to_idx == {"stable": 1}
        assert recovered._idx_to_id == {1: "stable"}
        assert recovered._index is not None
        assert recovered._index.ntotal == 1
        assert faiss.read_index(str(committed._index_path)).ntotal == 1


class TestVectorStoreSingleton:
    """Test VectorStore singleton."""

    def test_get_vector_store_singleton(self):
        """Test get_vector_store returns singleton."""
        import src.core.vector_store as vector_module
        vector_module._vector_store = None
        
        with patch("src.core.vector_store.get_settings"):
            store1 = get_vector_store()
            store2 = get_vector_store()
            assert store1 is store2
        
        vector_module._vector_store = None
