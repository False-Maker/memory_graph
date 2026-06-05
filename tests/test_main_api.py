"""Focused tests for API entrypoint and health endpoints."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.responses import HTMLResponse


class TestHealthEndpoint:
    """Test health and root endpoints."""

    @pytest.mark.asyncio
    async def test_api_endpoints_require_bearer_token(self):
        from src.api.main import app

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as unauthenticated_client:
            response = await unauthenticated_client.get("/api/v1/config")

        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert response.headers["www-authenticate"] == "Bearer"

    @pytest.mark.asyncio
    async def test_health_remains_public_without_bearer_token(self):
        from src.api.main import app

        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 0})

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as unauthenticated_client:
            with patch("src.api.main.get_settings", return_value=mock_settings):
                with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                    with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                        with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                            response = await unauthenticated_client.get("/health")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cors_preflight_remains_available_without_bearer_token(self):
        from src.api.main import app

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as unauthenticated_client:
            response = await unauthenticated_client.options(
                "/api/v1/config",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)

        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(
            return_value={
                "configured_dimension": 1024,
                "loaded_index_dimension": 1024,
                "active_index_dimension": 1024,
                "dimension_mismatch": False,
                "indexed_documents": 2,
                "stored_documents": 2,
            }
        )

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "Memory Graph API"
        assert response.json()["version"] == "1.0.0"
        assert response.json()["checks"]["config"]["ok"] is True
        assert response.json()["checks"]["sqlite"]["ok"] is True
        assert response.json()["checks"]["vector_store"]["ok"] is True

    @pytest.mark.asyncio
    async def test_health_check_returns_503_when_dependency_fails(self, client):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=False)

        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 0})

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                        response = await client.get("/health")

        assert response.status_code == 503
        assert response.json()["status"] == "unhealthy"
        assert response.json()["checks"]["sqlite"]["ok"] is False

    @pytest.mark.asyncio
    async def test_health_check_returns_503_when_config_file_is_missing(self, client):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)

        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 0})

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch(
                "src.api.main.get_config_path",
                side_effect=FileNotFoundError("Config file not found"),
            ):
                with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                        response = await client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["config"]["ok"] is False
        assert "Config file not found" in body["checks"]["config"]["error"]

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        with patch(
            "src.api.main.serve_frontend_index",
            return_value=HTMLResponse("<html></html>"),
        ):
            response = await client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    @pytest.mark.asyncio
    async def test_sidecar_health_proxy_returns_502_when_upstream_is_unreachable(self, client):
        request = httpx.Request("GET", "http://127.0.0.1:3001/health")
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("sidecar offline", request=request))

        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.main.httpx.AsyncClient", return_value=mock_async_client):
            response = await client.get("/sidecar/health")

        assert response.status_code == 502
        assert response.json()["status"] == "DOWN"
        assert response.json()["message"] == "Failed to reach sidecar"
        assert response.json()["upstream"].endswith("/health")
        assert "sidecar offline" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_runtime_diagnostics_includes_provider_result_and_recent_failures(self, client):
        import src.api.main as main_module

        main_module._recent_failures.clear()
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_llm = MagicMock()
        mock_llm.test_connection = AsyncMock(
            return_value={
                "openai": False,
                "openai_error": "openai auth failed",
                "ollama": True,
            }
        )
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 3})

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                with patch("src.api.main.get_llm_manager", return_value=mock_llm):
                    with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                        with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                            with patch("src.api.main._run_sidecar_check", new=AsyncMock(return_value={"ok": True})):
                                with patch("src.api.main._build_collectors_summary", return_value={"ok": True}):
                                    response = await client.get("/api/v1/diagnostics/runtime")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["provider"]["ok"] is False
        assert body["checks"]["provider"]["current_provider"] == "openai"
        assert body["checks"]["provider"]["provider_errors"]["openai"] == "openai auth failed"
        assert any(item["component"] == "provider" for item in body["recent_failures"])

    @pytest.mark.asyncio
    async def test_runtime_diagnostics_reports_task_chain_not_configured(self, client, tmp_path):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_llm = MagicMock()
        mock_llm.test_connection = AsyncMock(return_value={"openai": True})
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 3})

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                with patch("src.api.main.get_llm_manager", return_value=mock_llm):
                    with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                        with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                            with patch(
                                "src.api.main._get_diagnostics_sync_source_settings_path",
                                return_value=tmp_path / "missing-sync-sources.json",
                            ):
                                with patch("src.api.main._run_sidecar_check", new=AsyncMock(return_value={"ok": True})):
                                    with patch("src.api.main._build_collectors_summary", return_value={"ok": True}):
                                        response = await client.get("/api/v1/diagnostics/runtime")

        assert response.status_code == 200
        body = response.json()
        assert body["task_chain"] == {
            "status": "not_configured",
            "configured_sources": 0,
            "sources": [],
            "detail": "No sync sources configured",
        }

    @pytest.mark.asyncio
    async def test_runtime_diagnostics_reports_task_chain_source_state(self, client, tmp_path):
        import src.api.main as main_module

        main_module._recent_failures.clear()
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            """
{
  "version": 1,
  "sources": [
    {
      "source_id": "src-1",
      "label": "Workspace Notes",
      "source_system": "notes",
      "workspace_id": "workspace-main",
      "workspace_root": "/tmp/workspace-main",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-02T10:00:00+00:00"
    }
  ]
}
            """.strip(),
            encoding="utf-8",
        )
        state_path = tmp_path / "memory-graph-sync.json"
        state_path.write_text(
            """
{
  "workspace_id": "workspace-main",
  "last_pulled_seq": 12,
  "records": {
    "ext-1": {
      "external_id": "ext-1",
      "source_path": "notes/a.md",
      "last_checksum": "sha256:a",
      "sync_status": "synced"
    },
    "ext-2": {
      "external_id": "ext-2",
      "source_path": "notes/b.md",
      "last_checksum": "sha256:b",
      "sync_status": "conflict"
    },
    "ext-3": {
      "external_id": "ext-3",
      "source_path": "notes/c.md",
      "last_checksum": "sha256:c",
      "sync_status": "deleted"
    }
  },
  "recent_mutation_ids": []
}
            """.strip(),
            encoding="utf-8",
        )

        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_llm = MagicMock()
        mock_llm.test_connection = AsyncMock(return_value={"openai": True})
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 3})

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                with patch("src.api.main.get_llm_manager", return_value=mock_llm):
                    with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                        with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                            with patch(
                                "src.api.main._get_diagnostics_sync_source_settings_path",
                                return_value=settings_path,
                            ):
                                with patch(
                                    "src.api.main._resolve_task_chain_state_path",
                                    return_value=state_path,
                                ):
                                    with patch("src.api.main._run_sidecar_check", new=AsyncMock(return_value={"ok": True})):
                                        with patch("src.api.main._build_collectors_summary", return_value={"ok": True}):
                                            response = await client.get("/api/v1/diagnostics/runtime")

        assert response.status_code == 200
        body = response.json()
        assert body["task_chain"]["status"] == "degraded"
        assert body["task_chain"]["configured_sources"] == 1
        assert body["task_chain"]["detail"] == "1 sync source(s) need attention"
        assert body["task_chain"]["sources"] == [
            {
                "source_id": "src-1",
                "label": "Workspace Notes",
                "source_system": "notes",
                "workspace_id": "workspace-main",
                "workspace_root": "/tmp/workspace-main",
                "state_status": "degraded",
                "record_count": 3,
                "conflicts": 1,
                "deleted_records": 1,
                "last_pulled_seq": 12,
                "detail": "1 conflicted records require attention",
            }
        ]
        assert any(item["component"] == "task_chain" for item in body["recent_failures"])

    @pytest.mark.asyncio
    async def test_runtime_diagnostics_includes_sidecar_collectors_and_failure_taxonomy(self, client):
        import src.api.main as main_module

        main_module._recent_failures.clear()
        main_module._record_recent_failure("provider", "openai auth failed", source="/test")

        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))
        mock_llm = MagicMock()
        mock_llm.test_connection = AsyncMock(return_value={"openai": False, "openai_error": "openai auth failed"})
        mock_graph_store = MagicMock()
        mock_graph_store._db_path = "data/faiss/graph.db"
        mock_graph_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 1})

        with patch("src.api.main.get_settings", return_value=mock_settings):
            with patch("src.api.main.get_config_path", return_value=Path("config/settings.yaml")):
                with patch("src.api.main.get_llm_manager", return_value=mock_llm):
                    with patch("src.api.main.get_graph_store", return_value=mock_graph_store):
                        with patch("src.api.main.get_vector_store", return_value=mock_vector_store):
                            with patch("src.api.main._run_sidecar_check", new=AsyncMock(return_value={"ok": False, "detail": "sidecar offline"})):
                                with patch("src.api.main._build_collectors_summary", return_value={"ok": True, "running": False, "total_collectors": 0}):
                                    response = await client.get("/api/v1/diagnostics/runtime")

        assert response.status_code == 200
        body = response.json()
        assert body["sidecar"]["ok"] is False
        assert body["collectors"]["ok"] is True
        assert body["recent_failures"][0]["category"] == "provider_auth"
        assert body["recent_failures"][0]["severity"] == "error"
        assert body["recent_failures"][0]["suggested_action"]

    @pytest.mark.asyncio
    async def test_operator_summary_aggregates_runtime_query_sync_and_mcp(self, client):
        runtime_payload = {
            "status": "unhealthy",
            "generated_at": "2026-04-20T00:00:00+00:00",
            "task_chain": {"status": "degraded", "configured_sources": 2, "sources": [{"state_status": "healthy"}, {"state_status": "degraded"}]},
            "recent_failures": [{"component": "provider"}],
            "collectors": {"running": True, "official_collectors": 3, "running_official_collectors": 2},
        }
        mock_trace_store = MagicMock()
        mock_trace_store.list_recent = MagicMock(
            return_value=[
                SimpleNamespace(status="succeeded"),
                SimpleNamespace(status="failed"),
                SimpleNamespace(status="running"),
            ]
        )

        with patch("src.api.main.runtime_diagnostics", new=AsyncMock(return_value=SimpleNamespace(body=json.dumps(runtime_payload).encode("utf-8")))):
            with patch("src.api.main._run_mcp_status_check", new=AsyncMock(return_value={"transport": "streamable-http", "reachable": True, "tools_count": 10, "auth_enabled": True})):
                with patch("src.api.main.get_query_trace_store", return_value=mock_trace_store):
                    response = await client.get("/api/v1/diagnostics/operator-summary")

        assert response.status_code == 200
        body = response.json()
        assert body["runtime"]["status"] == "unhealthy"
        assert body["query_runs"] == {
            "total_recent": 3,
            "succeeded": 1,
            "failed": 1,
            "running": 1,
        }
        assert body["sync_sources"]["attention"] == 1
        assert body["mcp"]["reachable"] is True
        assert body["collectors"]["running_official_collectors"] == 2

    @pytest.mark.asyncio
    async def test_mcp_status_returns_streamable_http_probe_payload(self, client):
        with patch("src.api.main._run_mcp_status_check", new=AsyncMock(return_value={
            "configured": True,
            "transport": "streamable-http",
            "reachable": True,
            "auth_enabled": False,
            "tools_count": 12,
            "core_tools": ["answer_question"],
            "missing_core_tools": [],
            "detail": None,
            "base_url": "http://127.0.0.1:8001/mcp",
        })):
            response = await client.get("/api/v1/mcp/status")

        assert response.status_code == 200
        assert response.json()["transport"] == "streamable-http"
        assert response.json()["reachable"] is True
