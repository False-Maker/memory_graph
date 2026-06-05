"""Flow facade for the generic sync service."""

from __future__ import annotations

from typing import Any, Callable

from src.core.sync.service_delete_ops import SyncServiceDeleteOps
from src.core.sync.service_upsert_ops import SyncServiceUpsertOps


class SyncServiceFlowOps:
    """Compose the heavy sync upsert/delete/conflict flows for SyncService."""

    def __init__(
        self,
        *,
        source_system: str,
        builders: Any,
        graph_evidence: Any,
        now_iso: Callable[[], str],
        maybe_await: Callable[[Any], Any],
        get_graph_store: Callable[[], Any],
        get_vector_store: Callable[[], Any],
        get_llm_manager: Callable[[], Any],
        extractor_cls: type,
    ) -> None:
        self._delete_ops = SyncServiceDeleteOps(
            source_system=source_system,
            builders=builders,
            now_iso=now_iso,
            maybe_await=maybe_await,
            get_graph_store=get_graph_store,
        )
        self._upsert_ops = SyncServiceUpsertOps(
            source_system=source_system,
            builders=builders,
            graph_evidence=graph_evidence,
            now_iso=now_iso,
            get_vector_store=get_vector_store,
            get_llm_manager=get_llm_manager,
            extractor_cls=extractor_cls,
            mark_community_dirty=self._delete_ops.mark_community_dirty,
        )

    async def process_upsert_record(self, **kwargs):
        """Delegate one upsert flow."""
        return await self._upsert_ops.process_upsert_record(**kwargs)

    async def tombstone_existing_record(self, **kwargs):
        """Delegate one tombstone/delete flow."""
        return await self._delete_ops.tombstone_existing_record(**kwargs)
