"""Lazy exports for the core package.

The sync client imports ``src.core.sync.*`` modules directly. Keep package
initialization lightweight so those CLI paths do not eagerly pull in every
optional runtime dependency.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "get_settings": ("src.core.config", "get_settings"),
    "reload_settings": ("src.core.config", "reload_settings"),
    "get_llm_manager": ("src.core.llm_manager", "get_llm_manager"),
    "LLMManager": ("src.core.llm_manager", "LLMManager"),
    "EntityExtractor": ("src.core.entity_extractor", "EntityExtractor"),
    "Entity": ("src.core.entity_extractor", "Entity"),
    "Relationship": ("src.core.entity_extractor", "Relationship"),
    "ExtractionResult": ("src.core.entity_extractor", "ExtractionResult"),
    "get_graph_store": ("src.core.graph_store", "get_graph_store"),
    "GraphStore": ("src.core.graph_store", "GraphStore"),
    "GraphEntity": ("src.core.graph_store", "GraphEntity"),
    "GraphRelationship": ("src.core.graph_store", "GraphRelationship"),
    "GraphStats": ("src.core.graph_store", "GraphStats"),
    "get_memory_service": ("src.core.memory_service", "get_memory_service"),
    "MemoryService": ("src.core.memory_service", "MemoryService"),
    "MemoryIngestResult": ("src.core.memory_service", "MemoryIngestResult"),
    "MemoryDeleteResult": ("src.core.memory_service", "MemoryDeleteResult"),
    "get_vector_store": ("src.core.vector_store", "get_vector_store"),
    "VectorStore": ("src.core.vector_store", "VectorStore"),
    "MemoryDocument": ("src.core.vector_store", "MemoryDocument"),
    "SearchResult": ("src.core.vector_store", "SearchResult"),
    "Retriever": ("src.core.retriever", "Retriever"),
    "RetrievalFacade": ("src.core.retrieval_facade", "RetrievalFacade"),
    "RetrievalResult": ("src.core.retrieval_facade", "RetrievalResult"),
    "resolve_retrieval_strategy": ("src.core.retrieval_facade", "resolve_retrieval_strategy"),
    "get_query_trace_store": ("src.core.query_trace", "get_query_trace_store"),
    "reset_query_trace_store": ("src.core.query_trace", "reset_query_trace_store"),
    "QueryTraceStore": ("src.core.query_trace", "QueryTraceStore"),
    "QueryRunTrace": ("src.core.query_trace", "QueryRunTrace"),
    "get_temporal_kg": ("src.core.temporal_kg", "get_temporal_kg"),
    "TemporalKnowledgeGraph": ("src.core.temporal_kg", "TemporalKnowledgeGraph"),
    "TemporalTriple": ("src.core.temporal_kg", "TemporalTriple"),
    "TemporalStats": ("src.core.temporal_kg", "TemporalStats"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve exported symbols lazily on first access."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__():
    """Expose lazy exports to interactive tooling."""
    return sorted(set(globals()) | set(__all__))
