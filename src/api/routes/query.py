"""
API Routes - Query
"""

from datetime import datetime
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Response

from src.api.schemas.query import (
    QueryRequest,
    QueryResponse,
    Source,
    CommunityContext,
    QueryRunTraceListResponse,
    QueryRunTraceResponse,
    QueryRunTraceSummary,
)
from src.core.llm_manager import get_llm_manager
from src.core.memory_contract import (
    metadata_contract_view,
    metadata_matches_filters,
    normalize_string_list,
    resolve_memory_summary,
)
from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store
from src.core.retrieval_facade import RetrievalFacade
from src.core.query_trace import get_query_trace_store


router = APIRouter(prefix="/api/v1/query", tags=["query"])

PROVENANCE_FIELDS = (
    "source",
    "workspace_id",
    "external_id",
    "source_path",
    "record_type",
    "title",
    "timestamp",
)
SOURCE_METADATA_FIELDS = (
    "source",
    "workspace_id",
    "external_id",
    "source_path",
    "record_type",
    "title",
    "timestamp",
    "scope",
    "scope_id",
    "visibility",
    "owner",
    "session_id",
    "thread_id",
    "task_id",
    "artifact_id",
    "summary",
    "confidence",
    "freshness",
    "pinned",
    "expires_at",
)


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _metadata_as_dict(source: Any) -> Dict[str, Any]:
    metadata = getattr(source, "metadata", None)
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    if hasattr(metadata, "model_dump"):
        return metadata.model_dump()
    if hasattr(metadata, "dict"):
        return metadata.dict()
    if hasattr(metadata, "__dict__"):
        return vars(metadata)
    return {}


def _normalize_timestamp(raw_value: Any) -> Any:
    if isinstance(raw_value, datetime):
        return raw_value.isoformat()
    return raw_value


def _resolve_public_strategy(request: QueryRequest) -> str:
    if request.strategy == "graphrag":
        return request.retrieval_mode or "graphrag"
    return request.strategy


def _resolve_llm_identity(llm: Any) -> tuple[str | None, str | None]:
    settings = getattr(llm, "settings", None)
    llm_settings = getattr(settings, "llm", None)
    provider = getattr(llm_settings, "provider", None)
    if not isinstance(provider, str) or not provider.strip():
        return None, None

    normalized_provider = provider.strip().lower()
    model = None
    provider_settings = getattr(llm_settings, normalized_provider, None)
    if provider_settings is not None:
        model = getattr(provider_settings, "model", None)
    if model is not None and not isinstance(model, str):
        model = str(model)

    return normalized_provider, model


def _trace_to_summary(trace: Any) -> QueryRunTraceSummary:
    return QueryRunTraceSummary(
        run_id=trace.run_id,
        session_id=trace.session_id,
        question=trace.question or "",
        strategy=trace.strategy or "unknown",
        retrieval_mode=trace.retrieval_mode,
        status=trace.status,
        llm_provider=trace.llm_provider,
        llm_model=trace.llm_model,
        llm_duration_ms=trace.llm_duration_ms,
        processing_time_ms=trace.processing_time_ms,
        layer_requested=getattr(trace, "layer_requested", None),
        layer_used=getattr(trace, "layer_used", None),
        layer_fallback_chain=list(getattr(trace, "layer_fallback_chain", []) or []),
        context_token_estimate=int(getattr(trace, "context_token_estimate", 0) or 0),
        layer_build_duration_ms=int(getattr(trace, "layer_build_duration_ms", 0) or 0),
        source_count=trace.source_hit_count,
        community_count=trace.community_hit_count,
        started_at=trace.created_at,
        completed_at=trace.completed_at,
        failure_reason=trace.failure_reason,
    )


def _trace_to_detail(trace: Any) -> QueryRunTraceResponse:
    return QueryRunTraceResponse(
        **_trace_to_summary(trace).model_dump(),
        top_k=trace.top_k,
        include_sources=trace.include_sources,
        entities_count=trace.entities_count,
    )


def _trace_matches_filters(
    trace: Any,
    *,
    status: str | None,
    strategy: str | None,
    layer_used: str | None,
    session_id: str | None,
) -> bool:
    if status and str(getattr(trace, "status", "") or "").strip().lower() != status.strip().lower():
        return False
    if strategy and str(getattr(trace, "strategy", "") or "").strip().lower() != strategy.strip().lower():
        return False
    if layer_used and str(getattr(trace, "layer_used", "") or "").strip().lower() != layer_used.strip().lower():
        return False
    if session_id and str(getattr(trace, "session_id", "") or "").strip() != session_id.strip():
        return False
    return True


def _build_provenance_payload(flat_provenance: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": _first_non_empty(
            flat_provenance.get("record_type"),
            flat_provenance.get("source"),
        ),
        "time": flat_provenance.get("timestamp"),
        "imported_from": _first_non_empty(
            flat_provenance.get("source_path"),
            flat_provenance.get("external_id"),
            flat_provenance.get("workspace_id"),
        ),
    }


def _request_has_structured_filters(request: QueryRequest) -> bool:
    return any(
        [
            bool(request.scopes),
            bool(request.scope_ids),
            bool(request.types),
            bool(request.visibility),
            bool(request.tags),
            bool(request.workspace_id),
            bool(request.task_id),
            bool(request.thread_id),
            bool(request.user_id),
            bool(request.cursor),
            request.include_expired,
        ]
    )


def _parse_cursor(value: Optional[str]) -> int:
    if value is None:
        return 0
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid query cursor: {value}")


def _source_matches_request(source: Source, request: QueryRequest) -> bool:
    metadata = {
        "workspace_id": source.workspace_id,
        "record_type": source.record_type,
        "scope": source.scope,
        "scope_id": source.scope_id,
        "visibility": source.visibility,
        "owner": source.owner,
        "session_id": source.session_id,
        "thread_id": source.thread_id,
        "task_id": source.task_id,
        "tags": list(source.tags or []),
        "summary": source.summary,
        "confidence": source.confidence,
        "freshness": source.freshness,
        "pinned": source.pinned,
        "expires_at": source.expires_at,
    }
    return metadata_matches_filters(
        metadata,
        scopes=request.scopes,
        scope_ids=request.scope_ids,
        types=request.types,
        visibility=request.visibility,
        tags=request.tags,
        workspace_id=request.workspace_id,
        session_id=request.session_id,
        task_id=request.task_id,
        thread_id=request.thread_id,
        owner=request.user_id,
        include_expired=request.include_expired,
    )


def _build_query_diagnostics(
    *,
    request: QueryRequest,
    server_side_filtered: bool,
    truncated: bool,
    candidate_window: Optional[int],
    warnings: list[str],
) -> dict[str, Any]:
    applied_filters = {
        key: value
        for key, value in {
            "scopes": list(request.scopes),
            "scope_ids": list(request.scope_ids),
            "types": list(request.types),
            "visibility": request.visibility,
            "tags": list(request.tags),
            "workspace_id": request.workspace_id,
            "session_id": request.session_id,
            "task_id": request.task_id,
            "thread_id": request.thread_id,
            "user_id": request.user_id,
            "include_expired": request.include_expired if request.include_expired else None,
            "cursor": request.cursor,
        }.items()
        if value not in (None, [], "")
    }
    return {
        "applied_filters": applied_filters,
        "server_side_filtered": server_side_filtered,
        "truncated": truncated,
        "candidate_window": candidate_window,
        "warnings": warnings,
    }


async def _generate_answer_from_sources(llm: Any, *, question: str, sources: list[Source]) -> str:
    if not sources:
        return "No relevant memories found."

    context = "\n\n".join(
        f"[Source {index + 1}]: {source.content}"
        for index, source in enumerate(sources)
    )
    return await llm.generate_answer(context, question)


async def _load_source_metadata(
    *,
    vector_store: Any,
    source: Any,
    metadata_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    memory_id = getattr(source, "memory_id", None)
    if not isinstance(memory_id, str) or not memory_id:
        return metadata_contract_view(_metadata_as_dict(source))

    if memory_id not in metadata_cache:
        doc = await vector_store.get_memory(memory_id)
        metadata_cache[memory_id] = metadata_contract_view(_metadata_as_dict(doc) if doc is not None else {})

    hydrated = dict(metadata_cache[memory_id])
    hydrated.update(
        {
            key: value
            for key, value in metadata_contract_view(_metadata_as_dict(source)).items()
            if value not in (None, [], "")
        }
    )
    return hydrated


async def _map_source(
    *,
    vector_store: Any,
    source: Any,
    metadata_cache: Dict[str, Dict[str, Any]],
) -> Source:
    metadata = await _load_source_metadata(
        vector_store=vector_store,
        source=source,
        metadata_cache=metadata_cache,
    )

    flat_provenance: Dict[str, Any] = {}
    for field_name in SOURCE_METADATA_FIELDS:
        value = metadata.get(field_name)
        if value is None:
            value = getattr(source, field_name, None)
        if field_name == "timestamp":
            value = _normalize_timestamp(value)
        flat_provenance[field_name] = value

    flat_provenance["tags"] = normalize_string_list(metadata.get("tags"))
    flat_provenance["summary"] = _first_non_empty(
        getattr(source, "summary", None),
        resolve_memory_summary(metadata),
    )

    provenance = _build_provenance_payload(flat_provenance)

    return Source(
        memory_id=source.memory_id,
        content=source.content,
        relevance=source.relevance,
        entities=getattr(source, "entities", []),
        provenance=provenance,
        community_id=getattr(source, "community_id", None),
        community_summary=getattr(source, "community_summary", None),
        **flat_provenance,
    )


@router.get("/runs", response_model=QueryRunTraceListResponse)
async def list_query_runs(
    limit: int = Query(default=10, ge=1, le=100),
    status: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    layer_used: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
):
    """List recent query runs for lightweight trace inspection."""
    runs = get_query_trace_store().list_recent(limit=200)
    runs = [
        run for run in runs
        if _trace_matches_filters(
            run,
            status=status,
            strategy=strategy,
            layer_used=layer_used,
            session_id=session_id,
        )
    ]
    return QueryRunTraceListResponse(
        runs=[_trace_to_summary(item) for item in runs[:limit]],
        total=len(runs),
    )


@router.get("/runs/{run_id}", response_model=QueryRunTraceResponse)
async def get_query_run(run_id: str):
    """Get one query run trace by id."""
    trace = get_query_trace_store().get(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Query run not found: {run_id}")
    return _trace_to_detail(trace)


@router.post("", response_model=QueryResponse)
async def query_memories(request: QueryRequest, response: Response):
    """Query memories with question answering"""
    public_strategy = _resolve_public_strategy(request)
    llm = get_llm_manager()
    llm_provider, llm_model = _resolve_llm_identity(llm)
    trace_store = get_query_trace_store()
    trace = trace_store.start_run(
        question=request.question,
        top_k=request.top_k,
        include_sources=request.include_sources,
        session_id=request.session_id,
        strategy=public_strategy,
        retrieval_mode=request.retrieval_mode if request.strategy == "graphrag" else None,
        layer_requested=request.layer,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    response.headers["X-Query-Run-Id"] = trace.run_id
    if trace.session_id:
        response.headers["X-Query-Session-Id"] = trace.session_id

    llm_duration_ms = 0
    original_generate_answer = getattr(llm, "generate_answer", None)

    async def _traced_generate_answer(context: str, question: str) -> str:
        nonlocal llm_duration_ms
        started_at = time.perf_counter()
        try:
            return await original_generate_answer(context, question)
        finally:
            llm_duration_ms += int((time.perf_counter() - started_at) * 1000)

    if callable(original_generate_answer):
        llm.generate_answer = _traced_generate_answer

    try:
        vector_store = get_vector_store()
        graph_store = get_graph_store()
        retriever = RetrievalFacade(llm, vector_store, graph_store)
        if _request_has_structured_filters(request):
            started_at = time.perf_counter()
            candidate_window = max(request.top_k * 10, request.top_k, 50)
            result = await retriever.search(
                query=request.question,
                strategy=public_strategy,
                top_k=candidate_window,
                include_sources=True,
                layer=request.layer or "auto",
                layer_budget_override=request.layer_budget_override,
            )
            metadata_cache: Dict[str, Dict[str, Any]] = {}
            mapped_sources = [
                await _map_source(
                    vector_store=vector_store,
                    source=s,
                    metadata_cache=metadata_cache,
                )
                for s in list(getattr(result, "sources", []) or [])
            ]
            filtered_sources = [source for source in mapped_sources if _source_matches_request(source, request)]
            start_index = _parse_cursor(request.cursor)
            selected_sources = filtered_sources[start_index : start_index + request.top_k]
            response_sources = selected_sources if request.include_sources else []
            selected_source_count = len(selected_sources)
            answer = await _generate_answer_from_sources(llm, question=request.question, sources=selected_sources)
            selected_entities = sorted(
                {
                    entity
                    for source in selected_sources
                    for entity in source.entities
                }
            )
            selected_community_ids = {
                source.community_id
                for source in selected_sources
                if source.community_id
            }
            communities = [
                CommunityContext(
                    community_id=c.community_id,
                    title=c.title,
                    summary=c.summary,
                    level=c.level,
                    entities=c.entities,
                    relevance=c.relevance,
                )
                for c in list(getattr(result, "communities", []) or [])
                if c.community_id in selected_community_ids
            ]
            processing_time_ms = int((time.perf_counter() - started_at) * 1000)
            next_index = start_index + len(selected_sources)
            next_cursor = str(next_index) if next_index < len(filtered_sources) else None
            truncated = next_cursor is not None
            warnings: list[str] = []
            if len(mapped_sources) >= candidate_window:
                warnings.append(
                    "results may be truncated by the current candidate window before filtering"
                )
            diagnostics = _build_query_diagnostics(
                request=request,
                server_side_filtered=True,
                truncated=truncated,
                candidate_window=candidate_window,
                warnings=warnings,
            )
        else:
            result = await retriever.answer(
                question=request.question,
                strategy=public_strategy,
                top_k=request.top_k,
                include_sources=request.include_sources,
                layer=request.layer or "auto",
                layer_budget_override=request.layer_budget_override,
            )
            result_sources = list(getattr(result, "sources", []) or [])
            result_entities = list(getattr(result, "entities", []) or [])
            result_communities = list(getattr(result, "communities", []) or [])
            processing_time_ms = int(getattr(result, "processing_time_ms", 0) or 0)

            metadata_cache = {}
            response_sources = [
                await _map_source(
                    vector_store=vector_store,
                    source=s,
                    metadata_cache=metadata_cache,
                )
                for s in result_sources
            ]
            selected_source_count = len(result_sources)
            selected_entities = result_entities
            communities = [
                CommunityContext(
                    community_id=c.community_id,
                    title=c.title,
                    summary=c.summary,
                    level=c.level,
                    entities=c.entities,
                    relevance=c.relevance,
                )
                for c in result_communities
            ]
            answer = result.answer
            next_cursor = None
            diagnostics = _build_query_diagnostics(
                request=request,
                server_side_filtered=False,
                truncated=False,
                candidate_window=None,
                warnings=[],
            )
        trace_store.complete_success(
            trace.run_id,
            question=request.question,
            top_k=request.top_k,
            include_sources=request.include_sources,
            session_id=request.session_id,
            strategy=public_strategy,
            retrieval_mode=request.retrieval_mode if request.strategy == "graphrag" else None,
            layer_requested=getattr(result, "layer_requested", request.layer),
            layer_used=getattr(result, "layer_used", None),
            layer_fallback_chain=list(getattr(result, "layer_fallback_chain", []) or []),
            context_token_estimate=int(getattr(result, "context_token_estimate", 0) or 0),
            layer_build_duration_ms=int(getattr(result, "layer_build_duration_ms", 0) or 0),
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_duration_ms=llm_duration_ms,
            processing_time_ms=processing_time_ms,
            entities_count=len(selected_entities),
            source_hit_count=selected_source_count,
            community_hit_count=len(communities),
        )
        return QueryResponse(
            answer=answer,
            sources=response_sources,
            entities=selected_entities,
            communities=communities,
            processing_time_ms=processing_time_ms,
            next_cursor=next_cursor,
            diagnostics=diagnostics,
            layer_used=getattr(result, "layer_used", None),
            layer_fallback_chain=list(getattr(result, "layer_fallback_chain", []) or []),
            context_token_estimate=int(getattr(result, "context_token_estimate", 0) or 0),
        )

    except Exception as e:
        trace_store.complete_failure(
            trace.run_id,
            question=request.question,
            top_k=request.top_k,
            include_sources=request.include_sources,
            session_id=request.session_id,
            strategy=public_strategy,
            retrieval_mode=request.retrieval_mode if request.strategy == "graphrag" else None,
            layer_requested=request.layer,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_duration_ms=llm_duration_ms,
            failure_reason=str(e),
        )
        headers = {"X-Query-Run-Id": trace.run_id}
        if trace.session_id:
            headers["X-Query-Session-Id"] = trace.session_id
        raise HTTPException(status_code=500, detail=str(e), headers=headers)
    finally:
        if callable(original_generate_answer):
            llm.generate_answer = original_generate_answer
