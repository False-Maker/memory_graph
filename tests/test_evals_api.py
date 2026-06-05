"""Focused tests for /api/v1/evals retrieval endpoint."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.core.graphrag_retriever_eval import GraphRAGEvalSummary, StrategyEvalSummary, summary_to_dict


def _sample_summary() -> GraphRAGEvalSummary:
    return GraphRAGEvalSummary(
        generated_at="2026-04-02T00:00:00+00:00",
        top_k=5,
        strategies={
            "local": StrategyEvalSummary(
                strategy="local",
                query_count=3,
                recall_at_k=0.8,
                empty_result_rate=0.0,
                avg_latency_ms=10.0,
                p95_latency_ms=15,
            ),
            "global": StrategyEvalSummary(
                strategy="global",
                query_count=3,
                recall_at_k=0.8,
                empty_result_rate=0.0,
                avg_latency_ms=12.0,
                p95_latency_ms=18,
            ),
            "hybrid": StrategyEvalSummary(
                strategy="hybrid",
                query_count=3,
                recall_at_k=1.0,
                empty_result_rate=0.0,
                avg_latency_ms=14.0,
                p95_latency_ms=20,
            ),
        },
    )


class TestEvalsEndpoint:
    """Test /api/v1/evals retrieval endpoint behavior."""

    @pytest.mark.asyncio
    async def test_retrieval_eval_falls_back_when_baseline_and_expectations_missing(self, client, tmp_path):
        missing_baseline = tmp_path / "missing-baseline.json"
        missing_expectations = tmp_path / "missing-expectations.json"
        summary = _sample_summary()

        with patch("src.api.routes.evals.DEFAULT_BASELINE_PATH", missing_baseline):
            with patch("src.api.routes.evals.DEFAULT_EXPECTATIONS_PATH", missing_expectations):
                with patch("src.api.routes.evals.build_fixture_retriever", return_value=object()):
                    with patch(
                        "src.api.routes.evals.evaluate_graphrag_retrieval",
                        new=AsyncMock(return_value=summary),
                    ):
                        response = await client.get("/api/v1/evals/retrieval")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["summary"] == summary_to_dict(summary)
        assert body["regressions"] == []
        assert body["expectation_passes"] == []
        assert body["expectation_failures"] == []
        assert body["baseline_path"] is None
        assert body["expectations_path"] is None
        assert body["strict_passed"] is True
        assert len(body["warnings"]) == 2
        assert "baseline file not found" in body["warnings"][0]
        assert "expectations file not found" in body["warnings"][1]

    @pytest.mark.asyncio
    async def test_retrieval_eval_uses_baseline_and_expectations_when_present(self, client, tmp_path):
        summary = _sample_summary()
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps(summary_to_dict(summary)), encoding="utf-8")
        expectations_path = tmp_path / "expectations.json"
        expectations_path.write_text(
            json.dumps(
                {
                    "default": {
                        "min_recall_at_k": 0.5,
                        "max_empty_result_rate": 0.5,
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("src.api.routes.evals.DEFAULT_BASELINE_PATH", baseline_path):
            with patch("src.api.routes.evals.DEFAULT_EXPECTATIONS_PATH", expectations_path):
                with patch("src.api.routes.evals.build_fixture_retriever", return_value=object()):
                    with patch(
                        "src.api.routes.evals.evaluate_graphrag_retrieval",
                        new=AsyncMock(return_value=summary),
                    ):
                        response = await client.get("/api/v1/evals/retrieval")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["baseline_path"] == str(baseline_path)
        assert body["expectations_path"] == str(expectations_path)
        assert body["strict_passed"] is True
        assert body["warnings"] == []

    @pytest.mark.asyncio
    async def test_retrieval_eval_marks_strict_failed_when_regressions_or_expectation_failures(self, client, tmp_path):
        summary = _sample_summary()
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps(summary_to_dict(summary)), encoding="utf-8")
        expectations_path = tmp_path / "expectations.json"
        expectations_path.write_text(json.dumps({"default": {"min_recall_at_k": 0.1}}), encoding="utf-8")

        with patch("src.api.routes.evals.DEFAULT_BASELINE_PATH", baseline_path):
            with patch("src.api.routes.evals.DEFAULT_EXPECTATIONS_PATH", expectations_path):
                with patch("src.api.routes.evals.build_fixture_retriever", return_value=object()):
                    with patch(
                        "src.api.routes.evals.evaluate_graphrag_retrieval",
                        new=AsyncMock(return_value=summary),
                    ):
                        with patch(
                            "src.api.routes.evals.compare_against_baseline",
                            return_value=["[hybrid] recall_at_k dropped"],
                        ):
                            with patch(
                                "src.api.routes.evals.evaluate_against_expectations",
                                return_value=(
                                    ["[local] recall_at_k=0.800 >= 0.100"],
                                    ["[hybrid] empty_result_rate=0.500 <= 0.200"],
                                ),
                            ):
                                response = await client.get("/api/v1/evals/retrieval?strict=true")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["strict_requested"] is True
        assert body["strict_passed"] is False
        assert body["regressions"] == ["[hybrid] recall_at_k dropped"]
        assert body["expectation_failures"] == ["[hybrid] empty_result_rate=0.500 <= 0.200"]

    @pytest.mark.asyncio
    async def test_retrieval_eval_live_requires_cases_path(self, client):
        response = await client.get("/api/v1/evals/retrieval?live=true")
        assert response.status_code == 400
        assert response.json() == {"detail": "live=true requires cases_path with expected_memory_ids"}

    @pytest.mark.asyncio
    async def test_retrieval_eval_rejects_missing_cases_path(self, client, tmp_path):
        missing_cases = Path(tmp_path) / "missing-cases.json"
        response = await client.get(f"/api/v1/evals/retrieval?cases_path={missing_cases}")
        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}

    @pytest.mark.asyncio
    async def test_retrieval_eval_rejects_paths_outside_docs(self, client):
        response = await client.get("/api/v1/evals/retrieval?cases_path=/etc/passwd")
        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}
