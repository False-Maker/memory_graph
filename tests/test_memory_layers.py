"""Focused tests for memory layer contracts."""

from src.core.memory_layers import (
    MemoryLayerRequest,
    append_layer_fallback,
    finalize_memory_layer,
    resolve_memory_layer,
)
from src.core.retrieval_facade import resolve_retrieval_strategy


def test_resolve_memory_layer_defaults_to_l2_for_legacy_search():
    result = resolve_memory_layer(
        MemoryLayerRequest(
            requested_layer="auto",
            strategy_plan=resolve_retrieval_strategy("hybrid"),
        )
    )

    assert result.requested_layer == "auto"
    assert result.resolved_layer == "l2"
    assert result.fallback_chain == ["l2"]
    assert result.token_budget.max_tokens > 0


def test_resolve_memory_layer_prefers_l3_for_graphrag_or_explicit_request():
    graphrag_result = resolve_memory_layer(
        MemoryLayerRequest(
            requested_layer="auto",
            strategy_plan=resolve_retrieval_strategy("graphrag"),
        )
    )
    explicit_result = resolve_memory_layer(
        MemoryLayerRequest(
            requested_layer="l3",
            strategy_plan=resolve_retrieval_strategy("hybrid"),
            budget_override=2048,
        )
    )

    assert graphrag_result.resolved_layer == "l3"
    assert graphrag_result.fallback_chain == ["l3"]
    assert explicit_result.resolved_layer == "l3"
    assert explicit_result.token_budget.max_tokens == 2048
    assert explicit_result.token_budget.override_used is True


def test_resolve_memory_layer_keeps_explicit_l1():
    result = resolve_memory_layer(
        MemoryLayerRequest(
            requested_layer="l1",
            strategy_plan=resolve_retrieval_strategy("hybrid"),
        )
    )

    assert result.requested_layer == "l1"
    assert result.resolved_layer == "l1"
    assert result.fallback_chain == ["l1"]
    assert result.diagnostics.fallback_triggered is False
    assert result.diagnostics.warnings == []


def test_finalize_memory_layer_estimates_context_tokens_and_fallback_chain():
    result = resolve_memory_layer(
        MemoryLayerRequest(
            requested_layer="auto",
            strategy_plan=resolve_retrieval_strategy("hybrid"),
        )
    )
    append_layer_fallback(result, "l3")
    finalized = finalize_memory_layer(
        result,
        sources=[type("Source", (), {"memory_id": "mem-1", "content": "Hello world", "community_id": None})()],
        communities=[type("Community", (), {"community_id": "comm-1", "summary": "Shared context", "title": "Cluster"})()],
    )

    assert finalized.resolved_layer == "l3"
    assert finalized.fallback_chain == ["l2", "l3"]
    assert finalized.token_estimate > 0
    assert finalized.diagnostics.item_count == 2
