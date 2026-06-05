"""Lightweight GraphRAG retrieval evaluation and regression baseline helpers."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Sequence

from src.core.entity_extractor import Entity, ExtractionResult
from src.core.graphrag_retriever import GraphRAGRetriever


DEFAULT_STRATEGIES: tuple[str, ...] = ("local", "global", "hybrid")


@dataclass
class RetrievalEvalCase:
    """One representative retrieval query with expected memory IDs."""

    query: str
    expected_memory_ids: list[str] = field(default_factory=list)


@dataclass
class QueryEvalEvidence:
    """Per-query retrieval evidence."""

    query: str
    expected_memory_ids: list[str] = field(default_factory=list)
    returned_memory_ids: list[str] = field(default_factory=list)
    hit_memory_ids: list[str] = field(default_factory=list)
    recall: float = 0.0
    is_empty: bool = False
    latency_ms: int = 0


@dataclass
class StrategyEvalSummary:
    """Aggregated summary for one retrieval strategy."""

    strategy: str
    query_count: int = 0
    recall_at_k: float = 0.0
    empty_result_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: int = 0
    evidences: list[QueryEvalEvidence] = field(default_factory=list)


@dataclass
class GraphRAGEvalSummary:
    """Full strategy comparison report."""

    generated_at: str
    top_k: int
    strategies: dict[str, StrategyEvalSummary] = field(default_factory=dict)


@dataclass
class StrategyExpectations:
    """Absolute expectation thresholds for one retrieval strategy."""

    min_recall_at_k: float | None = None
    max_empty_result_rate: float | None = None
    max_avg_latency_ms: float | None = None
    max_p95_latency_ms: int | None = None


DEFAULT_REPRESENTATIVE_CASES: tuple[RetrievalEvalCase, ...] = (
    RetrievalEvalCase(
        query="Why did we choose Python for ETL?",
        expected_memory_ids=["mem_py_decision"],
    ),
    RetrievalEvalCase(
        query="How do we rollback after a failed deploy?",
        expected_memory_ids=["mem_rollback_runbook"],
    ),
    RetrievalEvalCase(
        query="How does hybrid GraphRAG retrieval work?",
        expected_memory_ids=["mem_hybrid_notes"],
    ),
)


def _keyword_embedding(text: str) -> list[float]:
    """Deterministic keyword embedding for fixture evaluation."""
    tokens = (
        "python",
        "etl",
        "rollback",
        "deploy",
        "backup",
        "hybrid",
        "graphrag",
        "community",
        "knowledge",
        "search",
    )
    normalized = text.lower()
    return [float(normalized.count(token)) for token in tokens]


class _FixtureLLM:
    """Minimal deterministic LLM facade for retrieval-only eval."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [_keyword_embedding(text) for text in texts]

    async def generate_answer(self, context: str, question: str) -> str:
        return f"fixture-answer: {question}"


class _FixtureGraphStore:
    """In-memory graph store tailored for representative retrieval cases."""

    def __init__(self) -> None:
        self._community_rows = {
            "comm-python": {
                "id": "comm-python",
                "level": 0,
                "parent_id": None,
                "entity_ids": ["entity-python"],
                "summary": "Python ETL decisions and knowledge search implementation details.",
                "title": "Python ETL",
                "rank": 0.92,
            },
            "comm-rollback": {
                "id": "comm-rollback",
                "level": 0,
                "parent_id": None,
                "entity_ids": ["entity-rollback"],
                "summary": "Rollback checklist, backup manifest, and failed deploy recovery.",
                "title": "Rollback Recovery",
                "rank": 0.95,
            },
            "comm-graphrag": {
                "id": "comm-graphrag",
                "level": 0,
                "parent_id": None,
                "entity_ids": ["entity-graphrag"],
                "summary": "GraphRAG local global hybrid retrieval strategy comparison guidance.",
                "title": "GraphRAG Retrieval",
                "rank": 0.9,
            },
        }

        self._community_entities = {
            "comm-python": [
                SimpleNamespace(
                    id="mem_py_decision",
                    name="Python Decision",
                    source_text="We chose Python as the ETL implementation language.",
                ),
                SimpleNamespace(
                    id="mem_fastapi_stack",
                    name="FastAPI Stack",
                    source_text="FastAPI is used for search APIs in our Python stack.",
                ),
            ],
            "comm-rollback": [
                SimpleNamespace(
                    id="mem_rollback_runbook",
                    name="Rollback Runbook",
                    source_text="Rollback relies on backup manifest verification before restore.",
                ),
                SimpleNamespace(
                    id="mem_backup_manifest",
                    name="Backup Manifest",
                    source_text="Backup artifacts include manifest, requirements snapshot, and env backup.",
                ),
            ],
            "comm-graphrag": [
                SimpleNamespace(
                    id="mem_hybrid_notes",
                    name="Hybrid Retrieval Notes",
                    source_text="Hybrid retrieval combines local entity matches and global community context.",
                ),
                SimpleNamespace(
                    id="mem_local_global_modes",
                    name="Local Global Modes",
                    source_text="Local mode is entity-driven while global mode searches summaries.",
                ),
            ],
        }

        self._entity_to_communities = {
            "entity-python": ["comm-python"],
            "entity-rollback": ["comm-rollback"],
            "entity-graphrag": ["comm-graphrag"],
        }

        self._entities = {
            "entity-python": SimpleNamespace(id="entity-python", name="Python", type="technology"),
            "entity-rollback": SimpleNamespace(id="entity-rollback", name="Rollback", type="concept"),
            "entity-graphrag": SimpleNamespace(id="entity-graphrag", name="GraphRAG", type="technology"),
        }

    async def get_entity(self, entity_id: str):
        return self._entities.get(entity_id)

    async def find_entities_by_name(self, name: str, limit: int = 10):
        normalized = (name or "").strip().lower()
        matches = [
            entity
            for entity in self._entities.values()
            if entity.name.strip().lower() == normalized
        ]
        return matches[:limit]

    async def get_entity_memory_ids(self, entity_id: str, limit: int = 20):
        return [entity_id][:limit]

    async def get_entity_communities(self, entity_id: str) -> list[str]:
        return list(self._entity_to_communities.get(entity_id, []))

    async def get_community(
        self,
        community_id: str,
        include_entity_ids: bool = True,
    ) -> dict[str, Any] | None:
        return self._community_rows.get(community_id)

    async def get_community_neighbors(self, community_id: str) -> list[str]:
        return []

    async def list_communities(
        self,
        require_summary: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(self._community_rows.values())
        if require_summary:
            rows = [row for row in rows if row.get("summary")]
        if limit is not None:
            rows = rows[:limit]
        return rows

    async def get_community_entities(self, community_id: str, limit: int = 5):
        entities = self._community_entities.get(community_id, [])
        return entities[:limit]


class _StaticEntityExtractor:
    """Deterministic extractor aligned with representative queries."""

    def __init__(self, query_to_entities: dict[str, list[Entity]]) -> None:
        self._query_to_entities = query_to_entities

    async def extract(self, text: str) -> ExtractionResult:
        normalized = text.lower()
        entities: list[Entity] = []
        for keyword, mapped_entities in self._query_to_entities.items():
            if keyword in normalized:
                entities.extend(mapped_entities)
        return ExtractionResult(entities=entities, relationships=[], facts=[], summary="")


class _FixtureVectorStore:
    """Minimal vector-store facade for fixture retrieval flows."""

    async def get_memory(self, memory_id: str):
        return None


class _FixtureGraphRAGRetriever(GraphRAGRetriever):
    """GraphRAG retriever wired to deterministic fixture dependencies."""

    def __init__(self) -> None:
        llm = _FixtureLLM()
        graph_store = _FixtureGraphStore()
        super().__init__(llm_manager=llm, vector_store=_FixtureVectorStore(), graph_store=graph_store)
        self._query_to_entities = {
            "python": [Entity(id="entity-python", name="Python", type="topic")],
            "rollback": [Entity(id="entity-rollback", name="Rollback", type="topic")],
            "hybrid": [Entity(id="entity-graphrag", name="GraphRAG", type="topic")],
            "graphrag": [Entity(id="entity-graphrag", name="GraphRAG", type="topic")],
        }

    def _create_entity_extractor(self) -> _StaticEntityExtractor:
        return _StaticEntityExtractor(self._query_to_entities)


def build_fixture_retriever() -> GraphRAGRetriever:
    """Build a deterministic GraphRAG retriever for repeatable local/global/hybrid evals."""
    return _FixtureGraphRAGRetriever()


def _normalize_cases(cases: Iterable[RetrievalEvalCase]) -> list[RetrievalEvalCase]:
    normalized: list[RetrievalEvalCase] = []
    for case in cases:
        if not case.query.strip():
            continue
        normalized.append(
            RetrievalEvalCase(
                query=case.query.strip(),
                expected_memory_ids=[item.strip() for item in case.expected_memory_ids if item.strip()],
            )
        )
    return normalized


def _p95_latency_ms(latencies: list[int]) -> int:
    if not latencies:
        return 0
    ordered = sorted(latencies)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


async def evaluate_graphrag_retrieval(
    *,
    retriever: Any,
    cases: Sequence[RetrievalEvalCase],
    strategies: Sequence[str] = DEFAULT_STRATEGIES,
    top_k: int = 5,
) -> GraphRAGEvalSummary:
    """Evaluate GraphRAG retrieval quality for local/global/hybrid strategies."""
    normalized_cases = _normalize_cases(cases)
    if not normalized_cases:
        raise ValueError("No valid evaluation cases supplied.")

    normalized_strategies = []
    for strategy in strategies:
        normalized = strategy.strip().lower()
        if normalized and normalized not in normalized_strategies:
            normalized_strategies.append(normalized)
    if not normalized_strategies:
        raise ValueError("No retrieval strategies supplied.")

    strategy_reports: dict[str, StrategyEvalSummary] = {}

    for strategy in normalized_strategies:
        evidences: list[QueryEvalEvidence] = []
        latencies: list[int] = []
        empty_count = 0
        recall_sum = 0.0
        recall_cases = 0

        for case in normalized_cases:
            start = time.perf_counter()
            result = await retriever.retrieve(
                case.query,
                strategy=strategy,
                top_k=top_k,
                include_sources=True,
            )
            observed_latency = int((time.perf_counter() - start) * 1000)
            latency_ms = max(int(getattr(result, "processing_time_ms", 0)), observed_latency, 1)
            latencies.append(latency_ms)

            returned_memory_ids = []
            for source in getattr(result, "sources", []):
                memory_id = getattr(source, "memory_id", None)
                if isinstance(memory_id, str) and memory_id and memory_id not in returned_memory_ids:
                    returned_memory_ids.append(memory_id)

            expected_set = set(case.expected_memory_ids)
            hit_memory_ids = [memory_id for memory_id in returned_memory_ids if memory_id in expected_set]
            is_empty = len(returned_memory_ids) == 0
            if is_empty:
                empty_count += 1

            if case.expected_memory_ids:
                recall_cases += 1
                recall_sum += len(set(hit_memory_ids)) / len(expected_set)

            evidences.append(
                QueryEvalEvidence(
                    query=case.query,
                    expected_memory_ids=list(case.expected_memory_ids),
                    returned_memory_ids=returned_memory_ids,
                    hit_memory_ids=hit_memory_ids,
                    recall=(len(set(hit_memory_ids)) / len(expected_set)) if expected_set else 0.0,
                    is_empty=is_empty,
                    latency_ms=latency_ms,
                )
            )

        strategy_reports[strategy] = StrategyEvalSummary(
            strategy=strategy,
            query_count=len(normalized_cases),
            recall_at_k=(recall_sum / recall_cases) if recall_cases else 0.0,
            empty_result_rate=empty_count / len(normalized_cases),
            avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
            p95_latency_ms=_p95_latency_ms(latencies),
            evidences=evidences,
        )

    return GraphRAGEvalSummary(
        generated_at=datetime.now(timezone.utc).isoformat(),
        top_k=top_k,
        strategies=strategy_reports,
    )


def compare_against_baseline(
    *,
    current: GraphRAGEvalSummary,
    baseline: GraphRAGEvalSummary,
    recall_drop_tolerance: float = 0.05,
    empty_rate_increase_tolerance: float = 0.1,
    latency_ratio_tolerance: float = 1.5,
) -> list[str]:
    """Compare current metrics to baseline and return regression notes."""
    regressions: list[str] = []

    for strategy, current_summary in current.strategies.items():
        baseline_summary = baseline.strategies.get(strategy)
        if baseline_summary is None:
            continue

        recall_delta = baseline_summary.recall_at_k - current_summary.recall_at_k
        if recall_delta > recall_drop_tolerance:
            regressions.append(
                f"[{strategy}] recall_at_k dropped by {recall_delta:.3f} "
                f"(baseline={baseline_summary.recall_at_k:.3f}, current={current_summary.recall_at_k:.3f})"
            )

        empty_delta = current_summary.empty_result_rate - baseline_summary.empty_result_rate
        if empty_delta > empty_rate_increase_tolerance:
            regressions.append(
                f"[{strategy}] empty_result_rate increased by {empty_delta:.3f} "
                f"(baseline={baseline_summary.empty_result_rate:.3f}, current={current_summary.empty_result_rate:.3f})"
            )

        baseline_avg_latency = baseline_summary.avg_latency_ms
        if baseline_avg_latency > 0:
            latency_ratio = current_summary.avg_latency_ms / baseline_avg_latency
            if latency_ratio > latency_ratio_tolerance:
                regressions.append(
                    f"[{strategy}] avg_latency_ms ratio={latency_ratio:.2f} exceeds tolerance "
                    f"{latency_ratio_tolerance:.2f} (baseline={baseline_avg_latency:.1f}, "
                    f"current={current_summary.avg_latency_ms:.1f})"
                )

    return regressions


def _expectation_from_payload(payload: Any) -> StrategyExpectations:
    """Build expectation thresholds from a JSON mapping."""
    if not isinstance(payload, dict):
        raise ValueError("Expectation payload must be a mapping.")

    def as_optional_float(name: str) -> float | None:
        value = payload.get(name)
        if value is None:
            return None
        return float(value)

    def as_optional_int(name: str) -> int | None:
        value = payload.get(name)
        if value is None:
            return None
        return int(value)

    return StrategyExpectations(
        min_recall_at_k=as_optional_float("min_recall_at_k"),
        max_empty_result_rate=as_optional_float("max_empty_result_rate"),
        max_avg_latency_ms=as_optional_float("max_avg_latency_ms"),
        max_p95_latency_ms=as_optional_int("max_p95_latency_ms"),
    )


def load_eval_expectations(path: Path) -> tuple[dict[str, StrategyExpectations], StrategyExpectations | None]:
    """Load absolute expectation thresholds from JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(
            "Expectations file must be a JSON object. "
            "Use {'strategies': {...}, 'default': {...}} or {'local': {...}}."
        )

    default_expectation: StrategyExpectations | None = None
    if payload.get("default") is not None:
        default_expectation = _expectation_from_payload(payload["default"])

    if "strategies" in payload:
        strategy_payloads = payload.get("strategies")
        if not isinstance(strategy_payloads, dict):
            raise ValueError("'strategies' must be a mapping.")
    else:
        strategy_payloads = {
            key: value
            for key, value in payload.items()
            if key != "default"
        }

    expectations: dict[str, StrategyExpectations] = {}
    for strategy, config in strategy_payloads.items():
        normalized_strategy = str(strategy).strip().lower()
        if not normalized_strategy:
            continue
        expectations[normalized_strategy] = _expectation_from_payload(config)

    return expectations, default_expectation


def evaluate_against_expectations(
    *,
    summary: GraphRAGEvalSummary,
    expectations: dict[str, StrategyExpectations],
    default_expectation: StrategyExpectations | None = None,
) -> tuple[list[str], list[str]]:
    """Evaluate summary against absolute thresholds and return pass/fail evidence."""
    passes: list[str] = []
    failures: list[str] = []

    def push_result(passed: bool, message: str) -> None:
        if passed:
            passes.append(message)
        else:
            failures.append(message)

    for strategy, metrics in summary.strategies.items():
        threshold = expectations.get(strategy) or default_expectation
        if threshold is None:
            continue

        if threshold.min_recall_at_k is not None:
            push_result(
                metrics.recall_at_k >= threshold.min_recall_at_k,
                f"[{strategy}] recall_at_k={metrics.recall_at_k:.3f} >= {threshold.min_recall_at_k:.3f}",
            )

        if threshold.max_empty_result_rate is not None:
            push_result(
                metrics.empty_result_rate <= threshold.max_empty_result_rate,
                f"[{strategy}] empty_result_rate={metrics.empty_result_rate:.3f} <= {threshold.max_empty_result_rate:.3f}",
            )

        if threshold.max_avg_latency_ms is not None:
            push_result(
                metrics.avg_latency_ms <= threshold.max_avg_latency_ms,
                f"[{strategy}] avg_latency_ms={metrics.avg_latency_ms:.1f} <= {threshold.max_avg_latency_ms:.1f}",
            )

        if threshold.max_p95_latency_ms is not None:
            push_result(
                metrics.p95_latency_ms <= threshold.max_p95_latency_ms,
                f"[{strategy}] p95_latency_ms={metrics.p95_latency_ms} <= {threshold.max_p95_latency_ms}",
            )

    return passes, failures


def summary_to_dict(summary: GraphRAGEvalSummary) -> dict[str, Any]:
    """Serialize evaluation summary as a JSON-safe mapping."""
    return asdict(summary)


def summary_from_dict(payload: dict[str, Any]) -> GraphRAGEvalSummary:
    """Deserialize summary mapping into dataclasses."""
    strategy_payloads = payload.get("strategies", {})
    strategies: dict[str, StrategyEvalSummary] = {}
    for name, item in strategy_payloads.items():
        evidences = [QueryEvalEvidence(**evidence) for evidence in item.get("evidences", [])]
        strategies[name] = StrategyEvalSummary(
            strategy=item.get("strategy", name),
            query_count=int(item.get("query_count", 0)),
            recall_at_k=float(item.get("recall_at_k", 0.0)),
            empty_result_rate=float(item.get("empty_result_rate", 0.0)),
            avg_latency_ms=float(item.get("avg_latency_ms", 0.0)),
            p95_latency_ms=int(item.get("p95_latency_ms", 0)),
            evidences=evidences,
        )

    return GraphRAGEvalSummary(
        generated_at=str(payload.get("generated_at")),
        top_k=int(payload.get("top_k", 0)),
        strategies=strategies,
    )


def load_eval_cases(path: Path) -> list[RetrievalEvalCase]:
    """Load evaluation cases from JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list):
        raise ValueError("Cases file must be a JSON list or {'cases': [...]} mapping.")

    cases: list[RetrievalEvalCase] = []
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query", "")).strip()
        expected = item.get("expected_memory_ids", [])
        if isinstance(expected, str):
            expected = [expected]
        expected_ids = [str(entry).strip() for entry in expected if str(entry).strip()]
        if query:
            cases.append(RetrievalEvalCase(query=query, expected_memory_ids=expected_ids))
    return cases


def format_summary_table(summary: GraphRAGEvalSummary) -> str:
    """Build a compact human-readable metrics table."""
    lines = [
        "strategy | recall@k | empty_rate | avg_latency_ms | p95_latency_ms | queries",
        "-------- | -------- | ---------- | -------------- | -------------- | -------",
    ]
    for strategy in sorted(summary.strategies):
        item = summary.strategies[strategy]
        lines.append(
            f"{strategy} | {item.recall_at_k:.3f} | {item.empty_result_rate:.3f} | "
            f"{item.avg_latency_ms:.1f} | {item.p95_latency_ms} | {item.query_count}"
        )
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate GraphRAG local/global/hybrid retrieval quality.")
    parser.add_argument("--cases", type=Path, help="Path to JSON query cases.")
    parser.add_argument("--baseline", type=Path, help="Path to baseline JSON summary.")
    parser.add_argument(
        "--expectations",
        type=Path,
        help="Path to absolute expectation thresholds JSON.",
    )
    parser.add_argument("--write-baseline", type=Path, help="Write current summary JSON to this path.")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k retrieval cutoff.")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(DEFAULT_STRATEGIES),
        help="Strategies to evaluate. Default: local global hybrid.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live runtime dependencies instead of deterministic fixture retriever.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary instead of table.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when regressions or expectation failures are detected.",
    )
    parser.add_argument("--recall-drop-tolerance", type=float, default=0.05)
    parser.add_argument("--empty-rate-increase-tolerance", type=float, default=0.10)
    parser.add_argument("--latency-ratio-tolerance", type=float, default=1.50)
    return parser


async def _run_eval_from_cli(args: argparse.Namespace) -> int:
    if args.cases:
        cases = load_eval_cases(args.cases)
    else:
        cases = list(DEFAULT_REPRESENTATIVE_CASES)

    if args.live:
        if not args.cases:
            raise ValueError("--live requires --cases with real expected_memory_ids.")
        from src.core.graph_store import get_graph_store
        from src.core.llm_manager import get_llm_manager
        from src.core.vector_store import get_vector_store

        retriever = GraphRAGRetriever(get_llm_manager(), get_vector_store(), get_graph_store())
    else:
        retriever = build_fixture_retriever()

    summary = await evaluate_graphrag_retrieval(
        retriever=retriever,
        cases=cases,
        strategies=args.strategies,
        top_k=args.top_k,
    )

    if args.json:
        print(json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2))
    else:
        print(format_summary_table(summary))

    regressions: list[str] = []
    if args.baseline:
        baseline_payload = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline = summary_from_dict(baseline_payload)
        regressions = compare_against_baseline(
            current=summary,
            baseline=baseline,
            recall_drop_tolerance=args.recall_drop_tolerance,
            empty_rate_increase_tolerance=args.empty_rate_increase_tolerance,
            latency_ratio_tolerance=args.latency_ratio_tolerance,
        )
        if regressions:
            print("\nRegressions:")
            for item in regressions:
                print(f"- {item}")
        else:
            print("\nNo regressions detected against baseline.")

    expectation_failures: list[str] = []
    if args.expectations:
        expectations, default_expectation = load_eval_expectations(args.expectations)
        expectation_passes, expectation_failures = evaluate_against_expectations(
            summary=summary,
            expectations=expectations,
            default_expectation=default_expectation,
        )
        if expectation_passes or expectation_failures:
            print("\nExpectation checks:")
            for item in expectation_passes:
                print(f"- PASS {item}")
            for item in expectation_failures:
                print(f"- FAIL {item}")
        else:
            print("\nNo applicable expectation checks for evaluated strategies.")

    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if (regressions or expectation_failures) and args.strict:
        return 1
    return 0


def main() -> None:
    """CLI entrypoint for GraphRAG retrieval evaluation."""
    parser = _build_arg_parser()
    args = parser.parse_args()
    exit_code = asyncio.run(_run_eval_from_cli(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
