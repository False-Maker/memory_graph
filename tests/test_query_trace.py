"""Focused tests for the lightweight query trace store."""

import pytest

from src.core.query_trace import (
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    QueryTraceStore,
    get_query_trace_store,
    reset_query_trace_store,
)


class TestQueryTraceStore:
    def test_simplified_public_api_aliases_cover_query_lifecycle(self):
        store = QueryTraceStore()

        started = store.start_run(
            run_id="run-alias-success",
            question="What changed?",
            top_k=8,
            include_sources=False,
            session_id="session-1",
            strategy="hybrid",
            retrieval_mode="graphrag",
            layer_requested="auto",
        )
        completed = store.complete_success(
            "run-alias-success",
            llm_provider="openai",
            llm_model="gpt-4.1-mini",
            llm_duration_ms=18,
            processing_time_ms=42,
            layer_used="l2",
            layer_fallback_chain=["l2", "l3"],
            context_token_estimate=128,
            layer_build_duration_ms=7,
            entities_count=2,
            source_hit_count=3,
            community_hit_count=1,
        )

        assert started.run_id == "run-alias-success"
        assert started.question == "What changed?"
        assert started.top_k == 8
        assert started.include_sources is False
        assert completed.status == STATUS_SUCCEEDED
        assert completed.llm_duration_ms == 18
        assert completed.processing_time_ms == 42
        assert completed.layer_requested == "auto"
        assert completed.layer_used == "l2"
        assert completed.layer_fallback_chain == ["l2", "l3"]
        assert completed.context_token_estimate == 128
        assert completed.layer_build_duration_ms == 7
        assert completed.entities_count == 2
        assert store.get("run-alias-success") == completed
        assert [run.run_id for run in store.list_recent(limit=1)] == ["run-alias-success"]

        store.start_run(run_id="run-alias-failure")
        failed = store.complete_failure("run-alias-failure", failure_reason="upstream error")
        assert failed.status == STATUS_FAILED
        assert failed.failure_reason == "upstream error"

    def test_create_run_records_initial_metadata(self):
        store = QueryTraceStore()

        trace = store.create_run(
            run_id="run-1",
            question=" Explain Memory Graph ",
            top_k=5,
            include_sources=False,
            session_id=" session-1 ",
            strategy=" hybrid ",
            retrieval_mode=" graphrag ",
            layer_requested=" auto ",
        )

        assert trace.run_id == "run-1"
        assert trace.status == STATUS_RUNNING
        assert trace.question == "Explain Memory Graph"
        assert trace.top_k == 5
        assert trace.include_sources is False
        assert trace.session_id == "session-1"
        assert trace.strategy == "hybrid"
        assert trace.retrieval_mode == "graphrag"
        assert trace.llm_provider is None
        assert trace.llm_model is None
        assert trace.llm_duration_ms == 0
        assert trace.processing_time_ms == 0
        assert trace.layer_requested == "auto"
        assert trace.layer_used is None
        assert trace.layer_fallback_chain is None
        assert trace.context_token_estimate == 0
        assert trace.layer_build_duration_ms == 0
        assert trace.entities_count == 0
        assert trace.source_hit_count == 0
        assert trace.community_hit_count == 0
        assert trace.failure_reason is None
        assert trace.created_at
        assert trace.updated_at == trace.created_at
        assert trace.completed_at is None

        stored = store.get_run("run-1")
        assert stored == trace

    def test_mark_succeeded_updates_run_fields(self):
        store = QueryTraceStore()
        store.create_run(run_id="run-success")

        trace = store.mark_succeeded(
            "run-success",
            question="Who owns launch?",
            top_k=7,
            include_sources=True,
            session_id="session-42",
            strategy="hybrid",
            retrieval_mode="graphrag",
            llm_provider="openai",
            llm_model="gpt-4.1",
            llm_duration_ms=24,
            processing_time_ms=63,
            layer_requested="auto",
            layer_used="l3",
            layer_fallback_chain=["l2", "l3"],
            context_token_estimate=256,
            layer_build_duration_ms=12,
            entities_count=3,
            source_hit_count=4,
            community_hit_count=2,
        )

        assert trace.status == STATUS_SUCCEEDED
        assert trace.question == "Who owns launch?"
        assert trace.top_k == 7
        assert trace.include_sources is True
        assert trace.session_id == "session-42"
        assert trace.strategy == "hybrid"
        assert trace.retrieval_mode == "graphrag"
        assert trace.llm_provider == "openai"
        assert trace.llm_model == "gpt-4.1"
        assert trace.llm_duration_ms == 24
        assert trace.processing_time_ms == 63
        assert trace.layer_requested == "auto"
        assert trace.layer_used == "l3"
        assert trace.layer_fallback_chain == ["l2", "l3"]
        assert trace.context_token_estimate == 256
        assert trace.layer_build_duration_ms == 12
        assert trace.entities_count == 3
        assert trace.source_hit_count == 4
        assert trace.community_hit_count == 2
        assert trace.failure_reason is None
        assert trace.completed_at
        assert trace.updated_at == trace.completed_at

    def test_mark_failed_records_failure_reason(self):
        store = QueryTraceStore()
        store.create_run(
            run_id="run-failed",
            question="Why did sync fail?",
            top_k=4,
            include_sources=True,
            session_id="session-0",
            strategy="local",
            retrieval_mode="legacy",
        )

        trace = store.mark_failed(
            "run-failed",
            llm_provider="anthropic",
            llm_model="claude-3-7-sonnet",
            llm_duration_ms=55,
            processing_time_ms=81,
            layer_requested="l3",
            layer_used="l3",
            layer_fallback_chain=["l3"],
            context_token_estimate=64,
            layer_build_duration_ms=5,
            entities_count=1,
            source_hit_count=1,
            community_hit_count=0,
            failure_reason=" llm timeout ",
        )

        assert trace.status == STATUS_FAILED
        assert trace.question == "Why did sync fail?"
        assert trace.top_k == 4
        assert trace.include_sources is True
        assert trace.session_id == "session-0"
        assert trace.strategy == "local"
        assert trace.retrieval_mode == "legacy"
        assert trace.llm_provider == "anthropic"
        assert trace.llm_model == "claude-3-7-sonnet"
        assert trace.llm_duration_ms == 55
        assert trace.processing_time_ms == 81
        assert trace.layer_requested == "l3"
        assert trace.layer_used == "l3"
        assert trace.layer_fallback_chain == ["l3"]
        assert trace.context_token_estimate == 64
        assert trace.layer_build_duration_ms == 5
        assert trace.entities_count == 1
        assert trace.source_hit_count == 1
        assert trace.community_hit_count == 0
        assert trace.failure_reason == "llm timeout"
        assert trace.completed_at

    def test_list_recent_runs_is_newest_first_and_bounded(self):
        store = QueryTraceStore(max_runs=2)

        store.create_run(run_id="run-1")
        store.create_run(run_id="run-2")
        store.create_run(run_id="run-3")

        runs = store.list_recent_runs(limit=10)

        assert [run.run_id for run in runs] == ["run-3", "run-2"]
        assert store.get_run("run-1") is None

    def test_marking_unknown_run_raises_key_error(self):
        store = QueryTraceStore()

        with pytest.raises(KeyError, match="Unknown query run: missing"):
            store.mark_succeeded("missing")

        with pytest.raises(KeyError, match="Query run id is required"):
            store.mark_failed("   ")

    def test_singleton_helpers_return_shared_store(self):
        reset_query_trace_store()
        try:
            store = get_query_trace_store()
            assert store is get_query_trace_store()

            store.create_run(run_id="singleton-run")
            assert get_query_trace_store().get_run("singleton-run") is not None
        finally:
            reset_query_trace_store()

        replacement = get_query_trace_store()
        try:
            assert replacement.get_run("singleton-run") is None
        finally:
            reset_query_trace_store()

    def test_sqlite_backing_persists_runs_across_store_reopen(self, tmp_path):
        db_path = tmp_path / "query-trace.db"

        store = QueryTraceStore(db_path=db_path)
        try:
            started = store.start_run(
                run_id="run-persisted",
                question="Persist this run",
                top_k=3,
                include_sources=True,
                session_id="session-persisted",
                strategy="hybrid",
                layer_requested="auto",
            )
            completed = store.complete_success(
                "run-persisted",
                llm_provider="openai",
                llm_model="gpt-4.1-mini",
                processing_time_ms=17,
                layer_used="l2",
                layer_fallback_chain=["l2"],
                context_token_estimate=77,
                layer_build_duration_ms=4,
                source_hit_count=2,
                community_hit_count=1,
            )
            assert started.run_id == completed.run_id
        finally:
            store.close()

        reopened = QueryTraceStore(db_path=db_path)
        try:
            trace = reopened.get("run-persisted")
            assert trace is not None
            assert trace.status == STATUS_SUCCEEDED
            assert trace.question == "Persist this run"
            assert trace.llm_model == "gpt-4.1-mini"
            assert trace.layer_requested == "auto"
            assert trace.layer_used == "l2"
            assert trace.layer_fallback_chain == ["l2"]
            assert trace.context_token_estimate == 77
            assert [run.run_id for run in reopened.list_recent(limit=5)] == ["run-persisted"]
        finally:
            reopened.close()
