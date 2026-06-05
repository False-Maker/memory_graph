"""Shared memory-layer contracts and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from src.core.retrieval_facade import RetrievalPlan


MemoryLayerName = Literal["auto", "l0", "l1", "l2", "l3"]
ResolvedMemoryLayerName = Literal["l0", "l1", "l2", "l3"]
DEFAULT_LAYER_BUDGETS: dict[ResolvedMemoryLayerName, int] = {
    "l0": 120,
    "l1": 700,
    "l2": 400,
    "l3": 1200,
}


@dataclass
class MemoryLayerBudget:
    """Token budget for a resolved memory layer."""

    max_tokens: int
    override_used: bool = False


@dataclass
class MemoryLayerContextItem:
    """One context fragment that contributed to the memory layer."""

    item_type: str
    identifier: str | None
    preview: str
    token_estimate: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryLayerDiagnostics:
    """Diagnostics for one resolved memory layer."""

    fallback_triggered: bool = False
    item_count: int = 0
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class MemoryLayerRequest:
    """Input contract for resolving one memory layer."""

    requested_layer: MemoryLayerName = "auto"
    strategy_plan: "RetrievalPlan | None" = None
    budget_override: int | None = None


@dataclass
class MemoryLayerResult:
    """Resolved layer contract used by retrieval and tracing."""

    requested_layer: MemoryLayerName = "auto"
    resolved_layer: ResolvedMemoryLayerName = "l2"
    fallback_chain: list[str] = field(default_factory=list)
    token_budget: MemoryLayerBudget = field(default_factory=lambda: MemoryLayerBudget(max_tokens=DEFAULT_LAYER_BUDGETS["l2"]))
    token_estimate: int = 0
    context_items: list[MemoryLayerContextItem] = field(default_factory=list)
    diagnostics: MemoryLayerDiagnostics = field(default_factory=MemoryLayerDiagnostics)


def _normalize_layer(value: Any) -> MemoryLayerName:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"auto", "l0", "l1", "l2", "l3"}:
        return normalized  # type: ignore[return-value]
    return "auto"


def _coerce_budget_override(value: Any) -> int | None:
    if value is None:
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if normalized <= 0:
        return None
    return normalized


def _read_layer_budget(settings: Any, layer_name: ResolvedMemoryLayerName) -> int:
    memory_layers = getattr(settings, "memory_layers", None)
    layer_settings = getattr(memory_layers, layer_name, None) if memory_layers is not None else None
    max_tokens = getattr(layer_settings, "max_tokens", None)
    if isinstance(max_tokens, int) and max_tokens > 0:
        return max_tokens
    return DEFAULT_LAYER_BUDGETS[layer_name]


def estimate_text_tokens(text: str | None) -> int:
    """Approximate token count without a tokenizer dependency."""
    if not text:
        return 0
    return max(1, (len(text.strip()) + 3) // 4)


def resolve_memory_layer(
    request: MemoryLayerRequest,
    *,
    settings: Any = None,
) -> MemoryLayerResult:
    """Resolve one requested layer onto the current runtime capabilities."""

    requested_layer = _normalize_layer(request.requested_layer)
    strategy_plan = request.strategy_plan
    resolved_layer: ResolvedMemoryLayerName
    fallback_chain: list[str]
    warnings: list[str] = []

    if requested_layer == "l3":
        resolved_layer = "l3"
        fallback_chain = ["l3"]
    elif requested_layer == "l0":
        resolved_layer = "l0"
        fallback_chain = ["l0"]
    elif requested_layer == "l1":
        resolved_layer = "l1"
        fallback_chain = ["l1"]
    elif strategy_plan is not None and strategy_plan.backend == "graphrag":
        resolved_layer = "l3"
        fallback_chain = ["l3"]
    else:
        resolved_layer = "l2"
        fallback_chain = ["l2"]

    configured_budget = _read_layer_budget(settings, resolved_layer) if settings is not None else DEFAULT_LAYER_BUDGETS[resolved_layer]
    budget_override = _coerce_budget_override(request.budget_override)
    token_budget = MemoryLayerBudget(
        max_tokens=budget_override if budget_override is not None else configured_budget,
        override_used=budget_override is not None,
    )
    diagnostics = MemoryLayerDiagnostics(
        fallback_triggered=len(fallback_chain) > 1,
        warnings=warnings,
    )
    return MemoryLayerResult(
        requested_layer=requested_layer,
        resolved_layer=resolved_layer,
        fallback_chain=fallback_chain,
        token_budget=token_budget,
        diagnostics=diagnostics,
    )


def append_layer_fallback(
    result: MemoryLayerResult,
    fallback_layer: ResolvedMemoryLayerName,
) -> MemoryLayerResult:
    """Record one additional fallback hop."""

    if not result.fallback_chain or result.fallback_chain[-1] != fallback_layer:
        result.fallback_chain.append(fallback_layer)
    result.resolved_layer = fallback_layer
    result.diagnostics.fallback_triggered = True
    return result


def build_context_item(
    *,
    item_type: str,
    identifier: str | None,
    preview: str,
    metadata: dict[str, Any] | None = None,
) -> MemoryLayerContextItem:
    normalized_preview = preview.strip()
    if len(normalized_preview) > 160:
        normalized_preview = f"{normalized_preview[:157]}..."
    return MemoryLayerContextItem(
        item_type=item_type,
        identifier=identifier,
        preview=normalized_preview,
        token_estimate=estimate_text_tokens(normalized_preview),
        metadata=dict(metadata or {}),
    )


def finalize_memory_layer(
    result: MemoryLayerResult,
    *,
    sources: list[Any] | None = None,
    communities: list[Any] | None = None,
) -> MemoryLayerResult:
    """Finalize token estimate and context items from retrieval outputs."""

    context_items: list[MemoryLayerContextItem] = []

    for source in list(sources or []):
        context_items.append(
            build_context_item(
                item_type="source",
                identifier=getattr(source, "memory_id", None),
                preview=str(getattr(source, "content", "") or ""),
                metadata={"community_id": getattr(source, "community_id", None)},
            )
        )

    for community in list(communities or []):
        summary = str(getattr(community, "summary", "") or "")
        if not summary:
            continue
        context_items.append(
            build_context_item(
                item_type="community",
                identifier=getattr(community, "community_id", None),
                preview=summary,
                metadata={"title": getattr(community, "title", None)},
            )
        )

    result.context_items = context_items
    result.token_estimate = sum(item.token_estimate for item in context_items)
    result.diagnostics.item_count = len(context_items)
    result.diagnostics.truncated = result.token_estimate > result.token_budget.max_tokens
    if result.diagnostics.truncated:
        result.diagnostics.warnings.append("context token estimate exceeds the configured layer budget")
    return result
