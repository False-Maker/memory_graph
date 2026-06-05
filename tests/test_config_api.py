"""Focused tests for /api/v1/config endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.core.config import Settings
from src.core.secret_store import SecretStoreUnavailableError


AVAILABLE_SECRET_STORAGE = {
    "available": True,
    "storage_type": "system_keyring",
    "backend": "keyring.backends.SecretService.Keyring",
    "message": "API keys will be stored in the system keyring and kept out of config/settings.yaml.",
    "fallback_env_vars": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
}
UNAVAILABLE_SECRET_STORAGE = {
    "available": False,
    "storage_type": "environment_only",
    "backend": None,
    "message": (
        "No usable system keyring backend is available. "
        "The Settings page can save non-secret fields only; provide API keys via "
        "OPENAI_API_KEY / ANTHROPIC_API_KEY or configure a supported system keyring."
    ),
    "fallback_env_vars": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
}


class TestConfigEndpoint:
    """Test /api/v1/config endpoints."""

    @pytest.mark.asyncio
    async def test_get_config_returns_current_architecture_fields(self, client):
        with patch("src.api.routes.config.get_secret_storage_status", return_value=AVAILABLE_SECRET_STORAGE):
            response = await client.get("/api/v1/config")

        assert response.status_code == 200
        data = response.json()
        assert data["graph_backend"] == "NetworkX + SQLite"
        assert "neo4j_uri" not in data
        assert "openai_base_url" in data
        assert "openai_model" in data
        assert "ollama_url" in data
        assert data["secret_storage"] == AVAILABLE_SECRET_STORAGE

    @pytest.mark.asyncio
    async def test_get_config_exposes_secret_storage_status(self, client):
        with patch("src.api.routes.config.get_secret_storage_status", return_value=UNAVAILABLE_SECRET_STORAGE):
            response = await client.get("/api/v1/config")

        assert response.status_code == 200
        payload = response.json()
        assert payload["secret_storage"] == UNAVAILABLE_SECRET_STORAGE
        assert payload["secret_storage"]["storage_type"] == "environment_only"
        assert payload["secret_storage"]["fallback_env_vars"] == ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_get_config_reflects_secret_store_disabled_by_env(self, client, monkeypatch):
        monkeypatch.setenv("MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE", "1")

        response = await client.get("/api/v1/config")

        assert response.status_code == 200
        payload = response.json()
        assert payload["secret_storage"]["available"] is False
        assert payload["secret_storage"]["storage_type"] == "environment_only"
        assert payload["secret_storage"]["backend"] == "disabled_by_env:MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE"

    @pytest.mark.asyncio
    async def test_update_config_persists_changes(self, client, tmp_path):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "llm": {
                        "provider": "openai",
                        "openai": {
                            "api_key": "",
                            "base_url": "https://api.openai.com/v1",
                            "model": "gpt-4o",
                        },
                        "anthropic": {
                            "api_key": "",
                            "base_url": "https://api.anthropic.com",
                            "model": "claude-sonnet-4-20250514",
                        },
                        "ollama": {
                            "url": "http://localhost:11434",
                            "model": "qwen2.5:14b",
                        },
                    },
                    "embedding": {"model": "Qwen/Qwen3-Embedding-0.6B"},
                    "database": {"vector": {"type": "faiss"}},
                    "app": {"host": "127.0.0.1", "port": 8000},
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        with patch("src.api.routes.config.get_config_path", return_value=config_path):
            with patch("src.core.config.get_config_path", return_value=config_path):
                with patch("src.api.routes.config.store_api_key") as mock_store_api_key:
                    with patch("src.api.routes.config.get_secret_storage_status", return_value=AVAILABLE_SECRET_STORAGE):
                        with patch(
                            "src.api.routes.config.has_configured_api_key",
                            side_effect=lambda _settings, provider: provider == "openai",
                        ):
                            response = await client.put(
                                "/api/v1/config",
                                json={
                                    "llm_provider": "ollama",
                                    "openai_api_key": "sk-test",
                                    "openai_base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
                                    "openai_model": "gpt-4o-mini",
                                    "anthropic_base_url": "https://api.penguinsaichat.dpdns.org",
                                    "anthropic_model": "claude-3-5-sonnet-20241022",
                                    "ollama_url": "http://127.0.0.1:11434",
                                    "ollama_model": "qwen2.5:14b-instruct",
                                },
                            )

                            follow_up = await client.get("/api/v1/config")

        assert response.status_code == 200
        assert response.json()["success"] is True

        saved_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert saved_config["llm"]["provider"] == "ollama"
        assert saved_config["llm"]["openai"]["api_key"] == ""
        assert saved_config["llm"]["openai"]["base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert saved_config["llm"]["openai"]["model"] == "gpt-4o-mini"
        assert saved_config["llm"]["anthropic"]["base_url"] == "https://api.penguinsaichat.dpdns.org"
        assert saved_config["llm"]["anthropic"]["model"] == "claude-3-5-sonnet-20241022"
        assert saved_config["llm"]["ollama"]["url"] == "http://127.0.0.1:11434"
        assert saved_config["llm"]["ollama"]["model"] == "qwen2.5:14b-instruct"
        mock_store_api_key.assert_called_once_with("openai", "sk-test")

        assert follow_up.status_code == 200
        assert follow_up.json()["llm_provider"] == "ollama"
        assert follow_up.json()["openai_base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert follow_up.json()["openai_api_key_configured"] is True
        assert "neo4j_uri" not in follow_up.json()

    @pytest.mark.asyncio
    async def test_update_config_trims_values_and_ignores_blank_overwrites(self, client, tmp_path):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "llm": {
                        "provider": "anthropic",
                        "openai": {
                            "api_key": "",
                            "base_url": "https://api.openai.com/v1",
                            "model": "gpt-4o",
                        },
                        "anthropic": {
                            "api_key": "",
                            "base_url": "https://api.anthropic.com",
                            "model": "claude-sonnet-4-20250514",
                        },
                        "ollama": {
                            "url": "http://localhost:11434",
                            "model": "qwen2.5:14b",
                        },
                    },
                    "embedding": {"model": "Qwen/Qwen3-Embedding-0.6B"},
                    "database": {"vector": {"type": "faiss"}},
                    "app": {"host": "127.0.0.1", "port": 8000},
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        with patch("src.api.routes.config.get_config_path", return_value=config_path):
            with patch("src.core.config.get_config_path", return_value=config_path):
                response = await client.put(
                    "/api/v1/config",
                    json={
                        "llm_provider": "  OLLAMA  ",
                        "openai_base_url": "  https://open.bigmodel.cn/api/coding/paas/v4  ",
                        "openai_model": "  glm-4.7  ",
                        "anthropic_base_url": "   ",
                        "anthropic_model": "   ",
                        "ollama_url": "  http://127.0.0.1:11434  ",
                        "ollama_model": "  qwen2.5:32b  ",
                    },
                )

                follow_up = await client.get("/api/v1/config")

        assert response.status_code == 200
        assert response.json()["success"] is True

        saved_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert saved_config["llm"]["provider"] == "ollama"
        assert saved_config["llm"]["openai"]["base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert saved_config["llm"]["openai"]["model"] == "glm-4.7"
        assert saved_config["llm"]["anthropic"]["base_url"] == "https://api.anthropic.com"
        assert saved_config["llm"]["anthropic"]["model"] == "claude-sonnet-4-20250514"
        assert saved_config["llm"]["ollama"]["url"] == "http://127.0.0.1:11434"
        assert saved_config["llm"]["ollama"]["model"] == "qwen2.5:32b"

        assert follow_up.status_code == 200
        assert follow_up.json()["llm_provider"] == "ollama"
        assert follow_up.json()["openai_base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert follow_up.json()["openai_model"] == "glm-4.7"
        assert follow_up.json()["anthropic_base_url"] == "https://api.anthropic.com"
        assert follow_up.json()["anthropic_model"] == "claude-sonnet-4-20250514"
        assert follow_up.json()["ollama_url"] == "http://127.0.0.1:11434"
        assert follow_up.json()["ollama_model"] == "qwen2.5:32b"

    @pytest.mark.asyncio
    async def test_update_config_rejects_unknown_provider(self, client, tmp_path):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "llm": {
                        "provider": "openai",
                        "openai": {
                            "api_key": "",
                            "base_url": "https://api.openai.com/v1",
                            "model": "gpt-4o",
                        },
                    },
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        with patch("src.api.routes.config.get_config_path", return_value=config_path):
            with patch("src.core.config.get_config_path", return_value=config_path):
                response = await client.put(
                    "/api/v1/config",
                    json={"llm_provider": "custom-provider"},
                )

        assert response.status_code == 422
        assert "llm_provider" in response.text

    @pytest.mark.asyncio
    async def test_update_config_returns_503_when_secure_secret_store_is_unavailable(self, client, tmp_path):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "llm": {
                        "provider": "openai",
                        "openai": {
                            "api_key": "",
                            "base_url": "https://api.openai.com/v1",
                            "model": "gpt-4o",
                        },
                    },
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        with patch("src.api.routes.config.get_config_path", return_value=config_path):
            with patch("src.core.config.get_config_path", return_value=config_path):
                with patch(
                    "src.api.routes.config.store_api_key",
                    side_effect=SecretStoreUnavailableError("Secure secret storage backend is unavailable"),
                ):
                    with patch("src.api.routes.config.get_secret_storage_status", return_value=UNAVAILABLE_SECRET_STORAGE):
                        with patch("src.api.routes.config.save_yaml_config") as mock_save:
                            response = await client.put(
                                "/api/v1/config",
                                json={"openai_api_key": "sk-test"},
                            )

        assert response.status_code == 503
        assert response.json() == {
            "success": False,
            "code": "secure_secret_store_unavailable",
            "message": (
                "Secure secret storage is unavailable in this environment. "
                "API keys were not saved. Use OPENAI_API_KEY / ANTHROPIC_API_KEY environment variables "
                "or configure a supported system keyring."
            ),
            "providers": ["openai"],
            "fallback_env_vars": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
            "secret_storage": UNAVAILABLE_SECRET_STORAGE,
        }
        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_config_returns_503_when_secret_store_disabled_by_env(self, client, tmp_path, monkeypatch):
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "llm": {
                        "provider": "openai",
                        "openai": {
                            "api_key": "",
                            "base_url": "https://api.openai.com/v1",
                            "model": "gpt-4o",
                        },
                    },
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE", "1")

        with patch("src.api.routes.config.get_config_path", return_value=config_path):
            with patch("src.core.config.get_config_path", return_value=config_path):
                with patch("src.api.routes.config.save_yaml_config") as mock_save:
                    response = await client.put(
                        "/api/v1/config",
                        json={"openai_api_key": "sk-test"},
                    )

        assert response.status_code == 503
        assert response.json()["code"] == "secure_secret_store_unavailable"
        assert "MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE" in response.json()["message"]
        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_config_skips_unchanged_payload(self, client):
        current_settings = Settings(
            llm={
                "provider": "openai",
                "openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
                "anthropic": {"api_key": "", "model": "claude-sonnet-4-20250514"},
                "ollama": {"url": "http://localhost:11434", "model": "qwen2.5:14b"},
            },
            embedding={"model": "Qwen/Qwen3-Embedding-0.6B"},
            database={"vector": {"type": "faiss"}},
            app={"host": "127.0.0.1", "port": 8000},
        )

        with patch("src.api.routes.config.get_settings", return_value=current_settings):
            with patch("src.api.routes.config.load_raw_yaml_config") as mock_load:
                with patch("src.api.routes.config.save_yaml_config") as mock_save:
                    with patch("src.api.routes.config._reload_runtime_state") as mock_reload:
                        response = await client.put(
                            "/api/v1/config",
                            json={
                                "llm_provider": "openai",
                                "openai_base_url": "https://api.openai.com/v1",
                                "openai_model": "gpt-4o",
                            },
                        )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Configuration unchanged",
        }
        mock_load.assert_not_called()
        mock_save.assert_not_called()
        mock_reload.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_config_saves_before_reloading_runtime_state(self, client):
        current_settings = Settings(
            llm={
                "provider": "openai",
                "openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
                "anthropic": {
                    "api_key": "",
                    "base_url": "https://api.anthropic.com",
                    "model": "claude-sonnet-4-20250514",
                },
                "ollama": {"url": "http://localhost:11434", "model": "qwen2.5:14b"},
            },
            embedding={"model": "Qwen/Qwen3-Embedding-0.6B"},
            database={"vector": {"type": "faiss"}},
            app={"host": "127.0.0.1", "port": 8000},
        )
        call_order = []

        def record_save(*_args, **_kwargs):
            call_order.append("save")

        def record_reload():
            call_order.append("reload")

        with patch("src.api.routes.config.get_settings", return_value=current_settings):
            with patch("src.api.routes.config.get_config_path", return_value=Path("config/settings.yaml")):
                with patch(
                    "src.api.routes.config.load_raw_yaml_config",
                    return_value=current_settings.model_dump(),
                ):
                    with patch("src.api.routes.config.save_yaml_config", side_effect=record_save) as mock_save:
                        with patch(
                            "src.api.routes.config._reload_runtime_state",
                            side_effect=record_reload,
                        ) as mock_reload:
                            response = await client.put(
                                "/api/v1/config",
                                json={
                                    "llm_provider": "ollama",
                                    "ollama_url": "http://127.0.0.1:11434",
                                },
                            )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Configuration saved to settings.yaml",
        }
        assert call_order == ["save", "reload"]
        saved_payload = mock_save.call_args.args[1]
        assert saved_payload["llm"]["provider"] == "ollama"
        assert saved_payload["llm"]["ollama"]["url"] == "http://127.0.0.1:11434"
        mock_reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_returns_runtime_specific_fields(self, client):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))

        mock_llm_manager = MagicMock()
        mock_llm_manager.test_connection = AsyncMock(
            return_value={"openai": True, "anthropic": False, "ollama": False}
        )

        mock_graph_store = MagicMock()
        mock_graph_store.test_connection = AsyncMock(return_value=True)

        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)

        with patch("src.api.routes.config.get_settings", return_value=mock_settings):
            with patch("src.api.routes.config.get_llm_manager", return_value=mock_llm_manager):
                with patch("src.api.routes.config.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.routes.config.get_vector_store", return_value=mock_vector_store):
                        response = await client.post("/api/v1/config/test-connection")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "providers": {"openai": True, "anthropic": False, "ollama": False},
            "provider_errors": {},
            "graph_store": True,
            "vector_store": True,
            "current_error": None,
            "error": None,
        }

    @pytest.mark.asyncio
    async def test_test_connection_uses_override_payload_without_saving(self, client):
        saved_settings = Settings(
            llm={
                "provider": "openai",
                "openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
                "anthropic": {"api_key": "sk-ant-test", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-20250514"},
                "ollama": {"url": "http://localhost:11434", "model": "qwen2.5:14b"},
            },
            embedding={"model": "Qwen/Qwen3-Embedding-0.6B"},
            database={"vector": {"type": "faiss"}},
            app={"host": "127.0.0.1", "port": 8000},
        )
        captured = {}

        class FakeLLMManager:
            def __init__(self, settings=None):
                captured["settings"] = settings

            async def test_connection(self):
                return {"anthropic": True, "openai": False, "ollama": False}

            async def close(self):
                captured["closed"] = True

        mock_graph_store = MagicMock()
        mock_graph_store.test_connection = AsyncMock(return_value=True)
        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)

        with patch("src.api.routes.config.get_settings", return_value=saved_settings):
            with patch("src.api.routes.config.LLMManager", FakeLLMManager):
                with patch("src.api.routes.config.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.routes.config.get_vector_store", return_value=mock_vector_store):
                        response = await client.post(
                            "/api/v1/config/test-connection",
                            json={
                                "llm_provider": "anthropic",
                                "anthropic_base_url": "https://api.penguinsaichat.dpdns.org",
                                "anthropic_model": "claude-3-5-sonnet-20241022",
                            },
                        )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "providers": {"anthropic": True, "openai": False, "ollama": False},
            "provider_errors": {},
            "graph_store": True,
            "vector_store": True,
            "current_error": None,
            "error": None,
        }
        assert captured["settings"].llm.provider == "anthropic"
        assert captured["settings"].llm.anthropic.base_url == "https://api.penguinsaichat.dpdns.org"
        assert captured["settings"].llm.anthropic.model == "claude-3-5-sonnet-20241022"
        assert saved_settings.llm.provider == "openai"
        assert saved_settings.llm.anthropic.base_url == "https://api.anthropic.com"
        assert saved_settings.llm.anthropic.model == "claude-sonnet-4-20250514"
        assert captured["closed"] is True

    @pytest.mark.asyncio
    async def test_test_connection_surfaces_current_provider_error(self, client):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="openai"))

        mock_llm_manager = MagicMock()
        mock_llm_manager.test_connection = AsyncMock(
            return_value={
                "current": False,
                "current_error": "openai auth failed",
                "openai": False,
                "openai_error": "openai auth failed",
                "ollama": True,
            }
        )

        mock_graph_store = MagicMock()
        mock_graph_store.test_connection = AsyncMock(return_value=True)

        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)

        with patch("src.api.routes.config.get_settings", return_value=mock_settings):
            with patch("src.api.routes.config.get_llm_manager", return_value=mock_llm_manager):
                with patch("src.api.routes.config.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.routes.config.get_vector_store", return_value=mock_vector_store):
                        response = await client.post("/api/v1/config/test-connection")

        assert response.status_code == 200
        assert response.json() == {
            "success": False,
            "providers": {"current": False, "openai": False, "ollama": True},
            "provider_errors": {
                "current": "openai auth failed",
                "openai": "openai auth failed",
            },
            "graph_store": True,
            "vector_store": True,
            "current_error": "openai auth failed",
            "error": None,
        }

    @pytest.mark.asyncio
    async def test_test_connection_prefers_current_result_for_override_provider(self, client):
        mock_settings = SimpleNamespace(llm=SimpleNamespace(provider="anthropic"))

        mock_llm_manager = MagicMock()
        mock_llm_manager.test_connection = AsyncMock(
            return_value={
                "current": False,
                "current_error": "Anthropic API key is not configured",
                "ollama": True,
            }
        )

        mock_graph_store = MagicMock()
        mock_graph_store.test_connection = AsyncMock(return_value=True)

        mock_vector_store = MagicMock()
        mock_vector_store.test_connection = AsyncMock(return_value=True)

        with patch("src.api.routes.config.get_settings", return_value=mock_settings):
            with patch("src.api.routes.config.get_llm_manager", return_value=mock_llm_manager):
                with patch("src.api.routes.config.get_graph_store", return_value=mock_graph_store):
                    with patch("src.api.routes.config.get_vector_store", return_value=mock_vector_store):
                        response = await client.post("/api/v1/config/test-connection")

        assert response.status_code == 200
        assert response.json() == {
            "success": False,
            "providers": {"current": False, "ollama": True},
            "provider_errors": {
                "current": "Anthropic API key is not configured",
            },
            "graph_store": True,
            "vector_store": True,
            "current_error": "Anthropic API key is not configured",
            "error": None,
        }

    @pytest.mark.asyncio
    async def test_get_config_marks_keyring_backed_secret_as_configured(self, client):
        settings = Settings(
            llm={
                "provider": "openai",
                "openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
                "anthropic": {"api_key": "", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-20250514"},
                "ollama": {"url": "http://localhost:11434", "model": "qwen2.5:14b"},
            },
            embedding={"model": "Qwen/Qwen3-Embedding-0.6B"},
            database={"vector": {"type": "faiss"}},
            app={"host": "127.0.0.1", "port": 8000},
        )

        with patch("src.api.routes.config.get_settings", return_value=settings):
            with patch("src.api.routes.config.get_secret_storage_status", return_value=AVAILABLE_SECRET_STORAGE):
                with patch("src.api.routes.config.has_configured_api_key", side_effect=lambda _settings, provider: provider == "openai"):
                    response = await client.get("/api/v1/config")

        assert response.status_code == 200
        payload = response.json()
        assert payload["openai_api_key_configured"] is True
        assert payload["anthropic_api_key_configured"] is False
        assert payload["secret_storage"] == AVAILABLE_SECRET_STORAGE
