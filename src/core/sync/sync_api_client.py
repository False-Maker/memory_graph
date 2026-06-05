"""HTTP client for external source sync APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised via CLI smoke fallback
    httpx = None  # type: ignore[assignment]

from src.core.sync.source_models import SyncSourceConfig


class SyncApiClient:
    """Thin async wrapper around the Memory Graph sync endpoints."""

    def __init__(
        self,
        config: SyncSourceConfig,
        async_client: Optional[Any] = None,
    ):
        self.config = config
        self._external_client = async_client
        self._client: Optional[Any] = async_client

    async def __aenter__(self) -> "SyncApiClient":
        if self._client is None:
            if httpx is None:
                raise RuntimeError(
                    "httpx is required for live sync requests; install dependencies before running push/pull"
                )
            headers = {}
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            self._client = httpx.AsyncClient(
                base_url=self.config.api_url.rstrip("/"),
                timeout=self.config.timeout_seconds,
                headers=headers,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client is not None and self._external_client is None:
            await self._client.aclose()
        self._client = self._external_client

    @property
    def client(self):
        """Return the configured async client."""
        if self._client is None:
            raise RuntimeError("SyncApiClient must be used inside an async context manager")
        return self._client

    async def batch_upsert(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call batch-upsert for one batch of records."""
        response = await self.client.post(
            "/api/v1/sync/sources/memories:batch-upsert",
            json={
                "source_system": self.config.source_system,
                "workspace_id": self.config.workspace_id,
                "client_id": f"{self.config.source_system}-sync",
                "records": records,
            },
        )
        response.raise_for_status()
        return response.json()

    async def delete_record(
        self,
        external_id: str,
        base_server_version: int,
        client_mutation_id: str,
        external_revision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete one remote record."""
        response = await self.client.request(
            "DELETE",
            f"/api/v1/sync/sources/{self.config.source_system}/memories/{self.config.workspace_id}/{external_id}",
            json={
                "base_server_version": base_server_version,
                "external_revision": external_revision,
                "client_mutation_id": client_mutation_id,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_changes(self, cursor: int, limit: int = 100) -> Dict[str, Any]:
        """Fetch remote changes since one cursor."""
        response = await self.client.get(
            f"/api/v1/sync/sources/{self.config.source_system}/changes",
            params={
                "workspace_id": self.config.workspace_id,
                "cursor": cursor,
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()

    async def reconcile(
        self,
        seen_external_ids: List[str],
        scan_id: str,
        delete_missing: bool = True,
    ) -> Dict[str, Any]:
        """Reconcile the current scan against the server registry."""
        response = await self.client.post(
            f"/api/v1/sync/sources/{self.config.source_system}/reconcile",
            json={
                "workspace_id": self.config.workspace_id,
                "scan_id": scan_id,
                "seen_external_ids": seen_external_ids,
                "delete_missing": delete_missing,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_state(self) -> Dict[str, Any]:
        """Fetch aggregate remote sync state."""
        response = await self.client.get(
            f"/api/v1/sync/sources/{self.config.source_system}/state",
            params={"workspace_id": self.config.workspace_id},
        )
        response.raise_for_status()
        return response.json()


MemoryGraphSyncClient = SyncApiClient
