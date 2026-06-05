"""Guards canonical retrieval eval baseline/expectation files."""

import json
from pathlib import Path

import pytest

from src.core.graphrag_retriever_eval import (
    DEFAULT_REPRESENTATIVE_CASES,
    build_fixture_retriever,
    compare_against_baseline,
    evaluate_against_expectations,
    evaluate_graphrag_retrieval,
    load_eval_expectations,
    summary_from_dict,
)


BASELINE_PATH = Path("docs/graphrag_retrieval_baseline.json")
EXPECTATIONS_PATH = Path("docs/graphrag_retrieval_expectations.json")
REQUIRED_STRATEGIES = {"local", "global", "hybrid"}


def test_canonical_eval_files_exist_with_required_strategies():
    assert BASELINE_PATH.exists()
    assert EXPECTATIONS_PATH.exists()

    baseline_payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_strategies = set((baseline_payload.get("strategies") or {}).keys())
    assert REQUIRED_STRATEGIES.issubset(baseline_strategies)

    expectations_payload = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
    expectation_strategies = set((expectations_payload.get("strategies") or {}).keys())
    assert REQUIRED_STRATEGIES.issubset(expectation_strategies)


@pytest.mark.asyncio
async def test_deterministic_eval_passes_canonical_strict_guards():
    baseline_payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline = summary_from_dict(baseline_payload)
    expectations, default_expectation = load_eval_expectations(EXPECTATIONS_PATH)

    current = await evaluate_graphrag_retrieval(
        retriever=build_fixture_retriever(),
        cases=list(DEFAULT_REPRESENTATIVE_CASES),
        strategies=sorted(REQUIRED_STRATEGIES),
        top_k=baseline.top_k,
    )

    regressions = compare_against_baseline(current=current, baseline=baseline)
    expectation_passes, expectation_failures = evaluate_against_expectations(
        summary=current,
        expectations=expectations,
        default_expectation=default_expectation,
    )

    assert regressions == []
    assert expectation_failures == []
    assert expectation_passes
