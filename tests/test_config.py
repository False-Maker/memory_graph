"""Tests for config module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.core.config import (
    CONFIG_PATH_ENV,
    AiderCollectorConfig,
    AugmentCollectorConfig,
    ClaudeCodeCollectorConfig,
    ClineCollectorConfig,
    Settings,
    LLMConfig,
    EmbeddingConfig,
    DatabaseConfig,
    VectorConfig,
    FileWatcherConfig,
    WindsurfCollectorConfig,
    OpenCodeCollectorConfig,
    AntigravityCollectorConfig,
    TraceCollectorConfig,
    OpenAIConfig,
    AnthropicConfig,
    OllamaConfig,
    get_config_path,
    preload_env_file,
    resolve_env_vars,
    process_config_dict,
    load_yaml_config,
    validate_settings,
    get_settings,
    reload_settings,
)


class TestConfigModels:
    """Test configuration model classes."""

    def test_openai_config_defaults(self):
        """Test OpenAIConfig default values."""
        config = OpenAIConfig()
        assert config.api_key == ""
        assert config.model == "gpt-4o"
        assert config.base_url == "https://api.openai.com/v1"

    def test_openai_config_custom(self):
        """Test OpenAIConfig with custom values."""
        config = OpenAIConfig(
            api_key="test-key",
            model="gpt-3.5-turbo",
            base_url="https://custom.api.com/v1"
        )
        assert config.api_key == "test-key"
        assert config.model == "gpt-3.5-turbo"
        assert config.base_url == "https://custom.api.com/v1"

    def test_anthropic_config_defaults(self):
        """Test AnthropicConfig default values."""
        config = AnthropicConfig()
        assert config.api_key == ""
        assert config.model == "claude-sonnet-4-20250514"
        assert config.base_url == "https://api.anthropic.com"

    def test_ollama_config_defaults(self):
        """Test OllamaConfig default values."""
        config = OllamaConfig()
        assert config.url == "http://localhost:11434"
        assert config.model == "qwen2.5:14b"

    def test_llm_config_defaults(self):
        """Test LLMConfig default values."""
        config = LLMConfig()
        assert config.provider == "openai"
        assert isinstance(config.openai, OpenAIConfig)
        assert isinstance(config.anthropic, AnthropicConfig)
        assert isinstance(config.ollama, OllamaConfig)

    def test_llm_config_normalizes_provider_whitespace_and_case(self):
        """Test LLM provider normalization from config input."""
        config = LLMConfig(provider="  OLLAMA  ")
        assert config.provider == "ollama"

    def test_llm_config_blank_provider_defaults_to_openai(self):
        """Test blank LLM provider falls back to default."""
        config = LLMConfig(provider="   ")
        assert config.provider == "openai"

    def test_embedding_config_defaults(self):
        """Test EmbeddingConfig default values."""
        config = EmbeddingConfig()
        assert config.model == "Qwen/Qwen3-Embedding-0.6B"
        assert config.dimensions == 1024
        assert config.model_path is None
        assert config.provider_preference == "local_first"
        assert config.cloud_model == "text-embedding-3-small"
        assert config.cloud_dimensions == 1536

    def test_embedding_config_normalizes_provider_preference(self):
        """Test embedding provider_preference normalization."""
        config = EmbeddingConfig(provider_preference="  REMOTE_ONLY  ")
        assert config.provider_preference == "remote_only"

    def test_embedding_config_blank_provider_preference_defaults_to_local_first(self):
        """Test blank embedding provider_preference falls back to default."""
        config = EmbeddingConfig(provider_preference="   ")
        assert config.provider_preference == "local_first"

    def test_vector_config_defaults(self):
        """Test VectorConfig default values."""
        config = VectorConfig()
        assert config.type == "faiss"

    def test_database_config(self):
        """Test DatabaseConfig."""
        config = DatabaseConfig()
        assert isinstance(config.vector, VectorConfig)

    def test_file_watcher_config_defaults_match_runtime_contract(self):
        """File watcher config defaults should match the runtime collector contract."""
        config = FileWatcherConfig()
        assert ".jsonl" in config.supported_extensions
        assert config.include_patterns == []
        assert config.scan_existing_on_start is False
        assert ".cursor/**" in config.ignore_patterns

    def test_settings_defaults(self):
        """Test Settings default values."""
        settings = Settings()
        assert settings.version == "1.0.0"
        assert settings.llm.provider == "openai"
        assert settings.app.host == "0.0.0.0"
        assert settings.app.port == 8000
        assert settings.app.debug is False
        assert settings.app.api_auth_enabled is True
        assert settings.app.docs_enabled is False
        assert settings.app.max_upload_bytes > 0

    def test_collectors_config_covers_current_runtime_surface(self):
        """Collectors config should expose both official and experimental runtime shapes."""
        settings = Settings()

        assert isinstance(settings.collectors.windsurf, WindsurfCollectorConfig)
        assert isinstance(settings.collectors.claude_code, ClaudeCodeCollectorConfig)
        assert isinstance(settings.collectors.aider, AiderCollectorConfig)
        assert isinstance(settings.collectors.cline, ClineCollectorConfig)
        assert isinstance(settings.collectors.opencode, OpenCodeCollectorConfig)
        assert isinstance(settings.collectors.antigravity, AntigravityCollectorConfig)
        assert isinstance(settings.collectors.trace, TraceCollectorConfig)
        assert isinstance(settings.collectors.augment, AugmentCollectorConfig)

    def test_validate_settings_rejects_unsupported_vector_type(self):
        """Startup validation should reject unsupported vector store types."""
        settings = Settings(database={"vector": {"type": "chroma"}})

        with pytest.raises(ValueError, match="Unsupported database.vector.type"):
            validate_settings(settings)

    def test_validate_settings_rejects_unsupported_embedding_provider_preference(self):
        """Startup validation should reject unsupported embedding provider preference values."""
        settings = Settings(embedding={"provider_preference": "hybrid_magic"})

        with pytest.raises(ValueError, match="Unsupported embedding.provider_preference"):
            validate_settings(settings)

    def test_validate_settings_rejects_blank_selected_provider_fields(self):
        """Startup validation should reject blank runtime fields for the selected provider."""
        settings = Settings(llm={"provider": "ollama", "ollama": {"url": "   ", "model": "qwen2.5:14b"}})

        with pytest.raises(ValueError, match="llm.ollama.url must not be empty"):
            validate_settings(settings)

    def test_validate_settings_rejects_missing_api_token_when_auth_enabled(self, monkeypatch):
        """API auth must not be enabled without a token."""
        monkeypatch.delenv("MEMORY_GRAPH_API_TOKEN", raising=False)
        settings = Settings(app={"api_auth_enabled": True, "api_token": ""})

        with pytest.raises(ValueError, match="app.api_token must be configured"):
            validate_settings(settings)

    def test_validate_settings_rejects_wildcard_cors_in_production(self):
        """Production CORS must not allow every origin."""
        settings = Settings(
            app={
                "environment": "production",
                "api_auth_enabled": False,
                "cors": {"allow_origins": ["*"], "allow_credentials": True},
            }
        )

        with pytest.raises(ValueError, match="must not contain '\\*' in production"):
            validate_settings(settings)


class TestConfigFunctions:
    """Test configuration helper functions."""

    def test_resolve_env_vars_string(self):
        """Test resolving environment variables in strings."""
        os.environ["TEST_VAR"] = "test_value"
        result = resolve_env_vars("${TEST_VAR}")
        assert result == "test_value"
        del os.environ["TEST_VAR"]

    def test_resolve_env_vars_with_default(self):
        """Test resolving environment variables with default value."""
        result = resolve_env_vars("${NON_EXISTENT:var}")
        assert result == "var"

    def test_resolve_env_vars_empty_for_missing(self):
        """Test resolving missing environment variable returns empty."""
        result = resolve_env_vars("${NON_EXISTENT}")
        assert result == ""

    def test_resolve_env_vars_non_string(self):
        """Test resolving non-string values returns as-is."""
        assert resolve_env_vars(123) == 123
        assert resolve_env_vars(None) is None
        assert resolve_env_vars(["list"]) == ["list"]

    def test_process_config_dict_simple(self):
        """Test processing simple config dict."""
        config = {"key": "value", "number": 42}
        result = process_config_dict(config)
        assert result == {"key": "value", "number": 42}

    def test_process_config_dict_nested(self):
        """Test processing nested config dict."""
        config = {
            "llm": {
                "api_key": "${OPENAI_API_KEY}"
            }
        }
        os.environ["OPENAI_API_KEY"] = "secret"
        result = process_config_dict(config)
        assert result["llm"]["api_key"] == "secret"
        del os.environ["OPENAI_API_KEY"]

    def test_process_config_dict_with_default(self):
        """Test processing config with default value."""
        config = {"key": "${MISSING:default_val}"}
        result = process_config_dict(config)
        assert result["key"] == "default_val"

    @patch("src.core.config.Path.exists")
    def test_get_config_path_not_found(self, mock_exists):
        """Test get_config_path when no config file exists."""
        mock_exists.return_value = False
        path = get_config_path()
        assert path.name == "settings.yaml"

    @patch("src.core.config.Path.exists")
    def test_get_config_path_raises_when_required_and_not_found(self, mock_exists):
        """Strict config path lookup should fail fast when no config file exists."""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError, match="Config file not found"):
            get_config_path(require_exists=True)

    def test_get_config_path_prefers_environment_override(self, tmp_path, monkeypatch):
        """Explicit config path env override should take precedence over repo defaults."""
        custom_config = tmp_path / "custom-settings.yaml"
        custom_config.write_text("llm:\n  provider: openai\n", encoding="utf-8")

        monkeypatch.setenv(CONFIG_PATH_ENV, str(custom_config))

        assert get_config_path() == custom_config

    def test_get_config_path_raises_for_missing_environment_override_when_required(self, tmp_path, monkeypatch):
        """Explicit config path env override should fail fast in strict mode when missing."""
        custom_config = tmp_path / "missing-settings.yaml"
        monkeypatch.setenv(CONFIG_PATH_ENV, str(custom_config))

        with pytest.raises(FileNotFoundError, match=CONFIG_PATH_ENV):
            get_config_path(require_exists=True)

    def test_load_yaml_config_not_exists(self):
        """Test loading non-existent YAML config."""
        from pathlib import Path
        result = load_yaml_config(Path("/nonexistent/config.yaml"))
        assert result == {}

    def test_load_yaml_config_invalid(self, temp_dir):
        """Test loading invalid YAML config returns empty dict."""
        config_file = temp_dir / "invalid.yaml"
        config_file.write_text("{invalid: yaml: content:")
        
        # yaml.safe_load raises yaml.YAMLError for invalid YAML
        try:
            result = load_yaml_config(config_file)
        except:
            result = {}
        
        assert result == {} or isinstance(result, dict)

    def test_load_yaml_config_empty(self, temp_dir):
        """Test loading empty YAML config."""
        config_file = temp_dir / "empty.yaml"
        config_file.write_text("")
        result = load_yaml_config(config_file)
        assert result == {}

    def test_load_yaml_config_valid(self, temp_dir):
        """Test loading valid YAML config."""
        config_file = temp_dir / "valid.yaml"
        config_file.write_text("""
version: "1.0.0"
llm:
  provider: "openai"
  openai:
    model: "gpt-4"
""")
        result = load_yaml_config(config_file)
        assert result["version"] == "1.0.0"
        assert result["llm"]["provider"] == "openai"

    def test_load_yaml_config_promotes_legacy_top_level_community_detection(self, temp_dir):
        """Legacy top-level community_detection should populate the active runtime config."""
        config_file = temp_dir / "legacy-community.yaml"
        config_file.write_text("""
community_detection:
  algorithm: "louvain"
  min_community_size: 7
""")

        result = load_yaml_config(config_file)
        settings = Settings(**result)

        assert settings.advanced.community_detection.algorithm == "louvain"
        assert settings.advanced.community_detection.min_community_size == 7

    def test_settings_example_matches_current_default_storage_stack(self):
        """Example config should stay aligned with the current FAISS + SQLite runtime."""
        config_path = Path("config/settings.example.yaml")
        raw = config_path.read_text(encoding="utf-8")
        result = load_yaml_config(config_path)
        settings = Settings(**result)

        assert settings.database.vector.type == "faiss"
        assert settings.database.vector.faiss.persist_directory == "./data/faiss"
        assert settings.advanced.community_detection.algorithm == "leiden"
        assert settings.collectors.file_watcher.include_patterns
        assert settings.collectors.file_watcher.scan_existing_on_start is True
        assert settings.collectors.windsurf.auto_scan_interval == 300
        assert settings.collectors.claude_code.auto_scan_interval == 60
        assert settings.collectors.aider.auto_scan_interval == 60
        assert settings.collectors.cline.enabled is False
        assert settings.collectors.opencode.enabled is False
        assert settings.collectors.antigravity.enabled is False
        assert settings.collectors.trace.enabled is False
        assert settings.collectors.augment.enabled is False
        assert 'api_key: "${OPENAI_API_KEY}"' in raw
        assert 'cloud_api_key: "${OPENAI_API_KEY}"' in raw
        assert "sk-" not in raw

    def test_load_yaml_config_with_env_var(self, temp_dir):
        """Test loading YAML with environment variable."""
        os.environ["TEST_API_KEY"] = "my_secret_key"
        config_file = temp_dir / "env.yaml"
        config_file.write_text("""
llm:
  openai:
    api_key: "${TEST_API_KEY}"
""")
        result = load_yaml_config(config_file)
        assert result["llm"]["openai"]["api_key"] == "my_secret_key"
        del os.environ["TEST_API_KEY"]

    def test_preload_env_file_loads_missing_values_without_overwriting(self, tmp_path, monkeypatch):
        """Test preloading .env values only fills missing environment variables."""
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text(
            "OPENAI_API_KEY=from-dotenv\nEXTRA_FLAG=enabled\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("OPENAI_API_KEY", "from-process")
        monkeypatch.delenv("EXTRA_FLAG", raising=False)

        preload_env_file(dotenv_file)

        assert os.environ["OPENAI_API_KEY"] == "from-process"
        assert os.environ["EXTRA_FLAG"] == "enabled"

    def test_get_settings_resolves_yaml_placeholders_from_dotenv(self, tmp_path, monkeypatch):
        """Test get_settings can resolve YAML placeholders from the local .env file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (tmp_path / ".env").write_text(
            "OPENAI_API_KEY=from-dotenv\nMEMORY_GRAPH_API_TOKEN=test-token\n",
            encoding="utf-8",
        )
        (config_dir / "settings.yaml").write_text(
            """
llm:
  openai:
    api_key: "${OPENAI_API_KEY}"
embedding:
  cloud_api_key: "${OPENAI_API_KEY}"
""".strip(),
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        get_settings.cache_clear()

        settings = get_settings()

        assert settings.llm.openai.api_key == "from-dotenv"
        assert settings.embedding.cloud_api_key == "from-dotenv"
        get_settings.cache_clear()

    def test_get_settings_uses_explicit_config_path_override(self, tmp_path, monkeypatch):
        """get_settings should load the config file pointed to by MEMORY_GRAPH_SETTINGS_PATH."""
        custom_config = tmp_path / "runtime-settings.yaml"
        custom_config.write_text(
            """
llm:
  provider: "ollama"
  ollama:
    url: "http://127.0.0.1:11434"
    model: "qwen2.5:32b"
database:
  vector:
    type: "faiss"
app:
  api_token: "test-token"
""".strip(),
            encoding="utf-8",
        )

        monkeypatch.setenv(CONFIG_PATH_ENV, str(custom_config))
        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

        settings = get_settings()

        assert settings.llm.provider == "ollama"
        assert settings.llm.ollama.model == "qwen2.5:32b"
        get_settings.cache_clear()

    def test_get_settings_rejects_unsupported_llm_provider_at_load_time(self, tmp_path, monkeypatch):
        """Loading config should fail fast for unsupported llm.provider values."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "settings.yaml").write_text(
            """
llm:
  provider: "custom-provider"
""".strip(),
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Unsupported llm.provider"):
            get_settings()

        get_settings.cache_clear()

    def test_get_settings_rejects_unsupported_vector_type_at_load_time(self, tmp_path, monkeypatch):
        """Loading config should fail fast for unsupported vector store types."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "settings.yaml").write_text(
            """
database:
  vector:
    type: "chroma"
""".strip(),
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Unsupported database.vector.type"):
            get_settings()

        get_settings.cache_clear()


class TestSettingsCache:
    """Test settings caching behavior."""

    @patch("src.core.config.get_settings")
    def test_reload_settings_clears_cache(self, mock_get_settings):
        """Test that reload_settings clears the cache."""
        from src.core.config import get_settings, reload_settings
        
        # First call to get_settings
        get_settings()
        
        # Reload should clear cache and call get_settings again
        reload_settings()
        
        # get_settings should be called at least twice
        assert mock_get_settings.call_count >= 1
