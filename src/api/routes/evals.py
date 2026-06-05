"""API routes for retrieval evaluation endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.core.graphrag_retriever import GraphRAGRetriever
from src.core.graphrag_retriever_eval import (
    DEFAULT_REPRESENTATIVE_CASES,
    compare_against_baseline,
    evaluate_against_expectations,
    evaluate_graphrag_retrieval,
    build_fixture_retriever,
    load_eval_cases,
    load_eval_expectations,
    summary_from_dict,
    summary_to_dict,
)
from src.core.graph_store import get_graph_store
from src.core.llm_manager import get_llm_manager
from src.core.vector_store import get_vector_store
from src.api.security import resolve_allowed_path


router = APIRouter(prefix="/api/v1/evals", tags=["evals"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASELINE_PATH = PROJECT_ROOT / "docs" / "graphrag_retrieval_baseline.json"
DEFAULT_EXPECTATIONS_PATH = PROJECT_ROOT / "docs" / "graphrag_retrieval_expectations.json"


def _resolve_optional_path(raw: str | None) -> Path | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    return resolve_allowed_path(value, allowed_roots=[str(PROJECT_ROOT / "docs")])


def _normalize_strategies(raw: str | None) -> list[str]:
    if raw is None:
        return ["local", "global", "hybrid"]
    normalized = []
    for item in raw.split(","):
        token = item.strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return normalized or ["local", "global", "hybrid"]


def _build_runtime_retriever(*, live: bool) -> Any:
    if live:
        return GraphRAGRetriever(get_llm_manager(), get_vector_store(), get_graph_store())
    return build_fixture_retriever()


@router.get("/retrieval")
async def run_retrieval_eval(
    strict: bool = Query(default=False),
    live: bool = Query(default=False),
    top_k: int = Query(default=5, ge=1, le=50),
    strategies: str | None = Query(default=None, description="Comma-separated strategies. Example: local,global,hybrid"),
    cases_path: str | None = Query(default=None),
    baseline_path: str | None = Query(default=None),
    expectations_path: str | None = Query(default=None),
    recall_drop_tolerance: float = Query(default=0.05, ge=0.0),
    empty_rate_increase_tolerance: float = Query(default=0.10, ge=0.0),
    latency_ratio_tolerance: float = Query(default=1.50, gt=0.0),
):
    """Evaluate retrieval quality and return regression evidence in a stable API response."""
    try:
        resolved_cases_path = _resolve_optional_path(cases_path)
        resolved_baseline_path = _resolve_optional_path(baseline_path) or DEFAULT_BASELINE_PATH
        resolved_expectations_path = _resolve_optional_path(expectations_path) or DEFAULT_EXPECTATIONS_PATH
        strategy_list = _normalize_strategies(strategies)
        warnings: list[str] = []

        if live and resolved_cases_path is None:
            raise HTTPException(status_code=400, detail="live=true requires cases_path with expected_memory_ids")

        if resolved_cases_path is not None:
            if not resolved_cases_path.exists():
                raise HTTPException(status_code=400, detail=f"cases_path not found: {resolved_cases_path}")
            cases = load_eval_cases(resolved_cases_path)
        else:
            cases = list(DEFAULT_REPRESENTATIVE_CASES)

        retriever = _build_runtime_retriever(live=live)
        summary = await evaluate_graphrag_retrieval(
            retriever=retriever,
            cases=cases,
            strategies=strategy_list,
            top_k=top_k,
        )

        regressions: list[str] = []
        baseline_used: str | None = None
        if resolved_baseline_path.exists():
            baseline_payload = json.loads(resolved_baseline_path.read_text(encoding="utf-8"))
            regressions = compare_against_baseline(
                current=summary,
                baseline=summary_from_dict(baseline_payload),
                recall_drop_tolerance=recall_drop_tolerance,
                empty_rate_increase_tolerance=empty_rate_increase_tolerance,
                latency_ratio_tolerance=latency_ratio_tolerance,
            )
            baseline_used = str(resolved_baseline_path)
        else:
            warnings.append(f"baseline file not found, skip regression compare: {resolved_baseline_path}")

        expectation_passes: list[str] = []
        expectation_failures: list[str] = []
        expectations_used: str | None = None
        if resolved_expectations_path.exists():
            expectations, default_expectation = load_eval_expectations(resolved_expectations_path)
            expectation_passes, expectation_failures = evaluate_against_expectations(
                summary=summary,
                expectations=expectations,
                default_expectation=default_expectation,
            )
            expectations_used = str(resolved_expectations_path)
        else:
            warnings.append(
                f"expectations file not found, skip absolute checks: {resolved_expectations_path}"
            )

        strict_passed = not regressions and not expectation_failures
        return {
            "success": True,
            "summary": summary_to_dict(summary),
            "regressions": regressions,
            "expectation_passes": expectation_passes,
            "expectation_failures": expectation_failures,
            "baseline_path": baseline_used,
            "expectations_path": expectations_used,
            "strict_passed": strict_passed,
            "warnings": warnings,
            "strict_requested": strict,
            "cases_path": str(resolved_cases_path) if resolved_cases_path else None,
            "live": live,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
