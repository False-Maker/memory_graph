"""Regression tests for src.core lazy public exports."""

import pytest

import src.core as core
from src.core.graph_store import GraphStore
from src.core.llm_manager import LLMManager, get_llm_manager
from src.core.vector_store import MemoryDocument, SearchResult, VectorStore, get_vector_store


class TestCoreExports:
    """Guard the stable facade exports used across the app."""

    def test_lazy_exports_resolve_expected_public_symbols(self):
        assert core.LLMManager is LLMManager
        assert core.get_llm_manager is get_llm_manager
        assert core.GraphStore is GraphStore
        assert core.VectorStore is VectorStore
        assert core.get_vector_store is get_vector_store
        assert core.MemoryDocument is MemoryDocument
        assert core.SearchResult is SearchResult

    def test_dir_lists_lazy_exports_and_missing_attr_raises(self):
        exported = dir(core)

        assert "LLMManager" in exported
        assert "VectorStore" in exported
        assert "get_vector_store" in exported

        with pytest.raises(AttributeError):
            core.__getattr__("MissingExport")
