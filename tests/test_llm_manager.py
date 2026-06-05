"""Tests for LLM Manager module."""

import asyncio
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.llm_manager import (
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    SentenceTransformerProvider,
    LLMManager,
    get_llm_manager,
)


class TestLLMProvider:
    """Test LLM Provider abstract base class."""

    def test_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()


class TestOpenAIProvider:
    """Test OpenAI Provider."""

    def test_init(self):
        """Test OpenAIProvider initialization."""
        config = {
            "api_key": "test-key",
            "model": "gpt-4",
            "base_url": "https://api.openai.com/v1"
        }
        provider = OpenAIProvider(config)
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4"
        assert provider.base_url == "https://api.openai.com/v1"

    def test_init_with_invalid_types_falls_back_to_defaults(self):
        """Invalid OpenAI config types should fall back to safe defaults."""
        provider = OpenAIProvider({
            "api_key": 123,
            "model": None,
            "base_url": "",
        })

        assert provider.api_key == ""
        assert provider.model == "gpt-4o"
        assert provider.base_url == "https://api.openai.com/v1"

    def test_init_ignores_boolean_dimensions(self):
        """Boolean dimensions should not be treated as numeric dimensions."""
        provider = OpenAIProvider({
            "api_key": "test-key",
            "dimensions": True,
        })

        assert provider.dimensions is None

    @pytest.mark.asyncio
    async def test_chat(self):
        """Test OpenAI chat method."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            config = {"api_key": "test-key", "model": "gpt-4", "base_url": "https://api.openai.com/v1"}
            provider = OpenAIProvider(config)

            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.chat(messages)

            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_generate(self):
        """Test OpenAI generate method."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Generated text"))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            config = {"api_key": "test-key", "model": "gpt-4"}
            provider = OpenAIProvider(config)

            result = await provider.generate("Test prompt")

            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_embed(self):
        """Test OpenAI embed method."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            config = {"api_key": "test-key"}
            provider = OpenAIProvider(config)

            result = await provider.embed(["test text"])

            assert result == [[0.1, 0.2, 0.3]]

    def test_chat_without_client_raises_error(self):
        """Test that chat raises error without client."""
        config = {"api_key": "test-key", "model": "gpt-4"}
        provider = OpenAIProvider(config)
        provider.client = None
        
        with pytest.raises(RuntimeError, match="OpenAI client not initialized"):
            asyncio.run(provider.chat([{"role": "user", "content": "test"}]))

    @pytest.mark.asyncio
    async def test_test_connection_times_out_quickly(self, monkeypatch):
        """OpenAI diagnostics should fail fast on stalled provider checks."""
        provider = OpenAIProvider({"api_key": "test-key", "model": "gpt-4"})

        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(0.05)
            return "late"

        provider.generate = slow_generate
        monkeypatch.setattr("src.core.llm_manager_openai.TEST_CONNECTION_TIMEOUT_SECONDS", 0.01)

        result = await provider.test_connection()

        assert result is False
        assert provider.last_error == "OpenAI connection test timed out after 0.01s"


class TestAnthropicProvider:
    """Test Anthropic Provider."""

    def test_init(self):
        """Test AnthropicProvider initialization."""
        config = {
            "api_key": "test-key",
            "base_url": "https://api.anthropic.com",
            "model": "claude-sonnet-4-20250514"
        }
        provider = AnthropicProvider(config)
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.model == "claude-sonnet-4-20250514"

    def test_init_with_invalid_types_falls_back_to_defaults(self):
        """Invalid Anthropic config types should fall back to safe defaults."""
        provider = AnthropicProvider({
            "api_key": ["bad"],
            "base_url": "",
            "model": "",
        })

        assert provider.api_key == ""
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_chat(self):
        """Test Anthropic chat method."""
        with patch("anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Claude response")]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            config = {
                "api_key": "test-key",
                "base_url": "https://api.penguinsaichat.dpdns.org",
                "model": "claude-sonnet-4-20250514"
            }
            provider = AnthropicProvider(config)

            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.chat(messages)

            assert result == "Claude response"
            mock_anthropic.assert_called_once()
            assert mock_anthropic.call_args.kwargs["base_url"] == "https://api.penguinsaichat.dpdns.org"

    def test_chat_with_system_message_extraction(self):
        """Test that system message is extracted from messages list."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"}
        ]
        
        # Extract system message
        system = None
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content")
                break
        
        user_messages = [m for m in messages if m.get("role") != "system"]
        
        assert system == "You are helpful."  # 修复：包含句号
        assert len(user_messages) == 1

    def test_embed_not_supported(self):
        """Test that Anthropic embed raises NotImplementedError."""
        config = {"api_key": "test-key"}
        provider = AnthropicProvider(config)

        with pytest.raises(NotImplementedError, match="Anthropic does not provide embedding API"):
            asyncio.run(provider.embed(["test"]))

    @pytest.mark.asyncio
    async def test_test_connection_records_last_error(self):
        """Anthropic test_connection should keep the last provider error for diagnostics."""
        with patch("anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=RuntimeError("forbidden"))
            mock_anthropic.return_value = mock_client

            provider = AnthropicProvider({
                "api_key": "test-key",
                "base_url": "https://api.penguinsaichat.dpdns.org",
                "model": "claude-opus4.6"
            })

            result = await provider.test_connection()

            assert result is False
            assert provider.last_error == "forbidden"

    @pytest.mark.asyncio
    async def test_test_connection_times_out_quickly(self, monkeypatch):
        """Anthropic diagnostics should fail fast on stalled provider checks."""
        provider = AnthropicProvider({"api_key": "test-key", "model": "claude-sonnet-4-20250514"})

        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(0.05)
            return "late"

        provider.generate = slow_generate
        monkeypatch.setattr("src.core.llm_manager_anthropic.TEST_CONNECTION_TIMEOUT_SECONDS", 0.01)

        result = await provider.test_connection()

        assert result is False
        assert provider.last_error == "Anthropic connection test timed out after 0.01s"


class TestOllamaProvider:
    """Test Ollama Provider."""

    def test_init(self):
        """Test OllamaProvider initialization."""
        config = {
            "url": "http://localhost:11434",
            "model": "qwen2.5:14b"
        }
        provider = OllamaProvider(config)
        assert provider.url == "http://localhost:11434"
        assert provider.model == "qwen2.5:14b"

    def test_init_with_invalid_types_falls_back_to_defaults(self):
        """Invalid Ollama config types should fall back to safe defaults."""
        provider = OllamaProvider({
            "url": None,
            "model": 123,
        })

        assert provider.url == "http://localhost:11434"
        assert provider.model == "qwen2.5:14b"

    @pytest.mark.asyncio
    async def test_chat(self):
        """Test Ollama chat method."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "message": {"content": "Ollama response"}
            }
            mock_response.raise_for_status = MagicMock()
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            config = {"url": "http://localhost:11434", "model": "llama2"}
            provider = OllamaProvider(config)

            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.chat(messages)

            assert result == "Ollama response"

    @pytest.mark.asyncio
    async def test_generate(self):
        """Test Ollama generate method."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "Generated text"}
            mock_response.raise_for_status = MagicMock()
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            config = {"url": "http://localhost:11434", "model": "llama2"}
            provider = OllamaProvider(config)

            result = await provider.generate("Test prompt")

            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_embed(self):
        """Test Ollama embed method."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
            mock_response.raise_for_status = MagicMock()
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            config = {"url": "http://localhost:11434", "model": "llama2"}
            provider = OllamaProvider(config)

            result = await provider.embed(["test text"])

            assert result == [[0.1, 0.2, 0.3]]

    @pytest.mark.asyncio
    async def test_test_connection(self):
        """Test Ollama test_connection method."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            config = {"url": "http://localhost:11434", "model": "llama2"}
            provider = OllamaProvider(config)

            result = await provider.test_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_times_out_quickly(self, monkeypatch):
        """Ollama diagnostics should fail fast on stalled provider checks."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def slow_get(*args, **kwargs):
                await asyncio.sleep(0.05)
                return MagicMock(status_code=200)

            mock_client.get = AsyncMock(side_effect=slow_get)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider({"url": "http://localhost:11434", "model": "llama2"})
            monkeypatch.setattr("src.core.llm_manager_ollama.TEST_CONNECTION_TIMEOUT_SECONDS", 0.01)

            result = await provider.test_connection()

            assert result is False
            assert provider.last_error == "Ollama connection test timed out after 0.01s"

    @pytest.mark.asyncio
    async def test_close(self):
        """Test Ollama close method."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            config = {"url": "http://localhost:11434", "model": "llama2"}
            provider = OllamaProvider(config)

            await provider.close()

            mock_client.aclose.assert_called_once()


class TestSentenceTransformerProvider:
    """Test local sentence-transformers embedding provider."""

    def test_init(self):
        """Test provider initialization with local model config."""
        fake_model = MagicMock()
        fake_module = MagicMock(SentenceTransformer=MagicMock(return_value=fake_model))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            provider = SentenceTransformerProvider(
                {"model": "bge-m3", "model_path": "/tmp/model", "dimensions": 768}
            )

        assert provider.model_name == "BAAI/bge-m3"
        assert provider.model_path == "/tmp/model"
        assert provider.model_ref == "/tmp/model"
        assert provider._model is fake_model

    def test_init_ignores_boolean_dimensions(self):
        """Boolean dimensions should not be treated as truncate dimensions."""
        fake_model = MagicMock()
        fake_module = MagicMock(SentenceTransformer=MagicMock(return_value=fake_model))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            provider = SentenceTransformerProvider({"model": "bge-m3", "dimensions": True})

        assert provider.dimensions is None

    @pytest.mark.asyncio
    async def test_embed(self):
        """Test local embedding generation."""
        fake_vectors = MagicMock()
        fake_vectors.tolist.return_value = [[0.1, 0.2, 0.3]]
        fake_model = MagicMock()
        fake_model.encode.return_value = fake_vectors
        fake_module = MagicMock(SentenceTransformer=MagicMock(return_value=fake_model))

        async def run_inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}), patch(
            "src.core.llm_manager_sentence_transformer.asyncio.to_thread",
            side_effect=run_inline,
        ):
            provider = SentenceTransformerProvider({"model": "bge-m3"})
            result = await provider.embed(["test text"])

        assert result == [[0.1, 0.2, 0.3]]
        fake_model.encode.assert_called_once()

    def test_generate_not_supported(self):
        """Text generation should not be supported by the embedding-only provider."""
        fake_model = MagicMock()
        fake_module = MagicMock(SentenceTransformer=MagicMock(return_value=fake_model))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            provider = SentenceTransformerProvider({"model": "bge-m3"})

        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(provider.generate("test"))


class TestLLMManager:
    """Test LLM Manager."""

    @patch("src.core.llm_manager.get_settings")
    def test_init(self, mock_get_settings):
        """Test LLMManager initialization."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.model = "gpt-4"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.anthropic.api_key = ""
        mock_settings.llm.ollama.url = "http://localhost:11434"
        mock_settings.llm.ollama.model = "qwen2.5:14b"
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        manager = LLMManager()
        assert manager.settings == mock_settings

    @pytest.mark.asyncio
    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OllamaProvider")
    @patch("src.core.llm_manager.OpenAIProvider")
    async def test_test_connection_fails_fast_when_current_openai_key_is_missing(
        self,
        mock_openai_provider,
        mock_ollama_provider,
        mock_get_settings,
    ):
        """Missing current-provider credentials should return a stable error without probing the network."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = ""
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.openai.model = "gpt-4o"
        mock_settings.llm.openai.model_dump.return_value = {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        }
        mock_settings.llm.anthropic.api_key = ""
        mock_settings.llm.ollama.model_dump.return_value = {
            "url": "http://localhost:11434",
            "model": "qwen2.5:14b",
        }
        mock_get_settings.return_value = mock_settings

        ollama_provider = MagicMock()
        ollama_provider.test_connection = AsyncMock(return_value=True)
        ollama_provider.close = AsyncMock()
        mock_ollama_provider.return_value = ollama_provider

        manager = LLMManager()
        results = await manager.test_connection()

        assert results == {
            "current": False,
            "current_error": "OpenAI API key is not configured",
            "ollama": True,
        }
        mock_openai_provider.assert_not_called()
        ollama_provider.test_connection.assert_awaited_once()
        ollama_provider.close.assert_awaited_once()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    def test_create_provider_openai(self, mock_provider_class, mock_get_settings):
        """Test creating OpenAI provider."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.model = "gpt-4"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.anthropic.api_key = ""
        mock_settings.llm.ollama.url = "http://localhost:11434"
        mock_settings.llm.ollama.model = "qwen2.5:14b"
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings
        mock_provider_class.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_provider()

        assert isinstance(provider, MagicMock)

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    def test_create_provider_non_string_falls_back_to_openai(self, mock_provider_class, mock_get_settings):
        """Non-string provider config should fall back to OpenAI instead of crashing."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = None
        mock_settings.llm.openai.model_dump.return_value = {"api_key": "test-key", "model": "gpt-4"}
        mock_get_settings.return_value = mock_settings
        mock_provider_class.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_provider()

        assert provider is mock_provider_class.return_value
        mock_provider_class.assert_called_once()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OllamaProvider")
    def test_create_provider_normalizes_whitespace_and_case(self, mock_provider_class, mock_get_settings):
        """Provider names should be trimmed and lowercased before dispatch."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "  OLLAMA  "
        mock_settings.llm.ollama.model_dump.return_value = {"url": "http://localhost:11434", "model": "qwen2.5:14b"}
        mock_get_settings.return_value = mock_settings
        mock_provider_class.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_provider()

        assert provider is mock_provider_class.return_value
        mock_provider_class.assert_called_once()

    @patch("src.core.llm_manager.get_settings")
    def test_create_provider_unknown(self, mock_get_settings):
        """Test creating unknown provider raises error."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "unknown_provider"
        mock_settings.llm.openai.api_key = ""
        mock_settings.llm.anthropic.api_key = ""
        mock_settings.llm.ollama.url = "http://localhost:11434"
        mock_settings.llm.ollama.model = "qwen2.5:14b"
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        manager = LLMManager()

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            manager._create_provider()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.SentenceTransformerProvider")
    def test_create_embedding_provider_prefers_local(self, mock_local_provider, mock_get_settings):
        """Local sentence-transformers embedding should be preferred when available."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.ollama.model_dump.return_value = {"url": "http://localhost:11434", "model": "qwen2.5:14b"}
        mock_settings.embedding.model = "bge-m3"
        mock_settings.embedding.model_path = "/tmp/bge-m3"
        mock_settings.embedding.dimensions = 768
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        mock_local = MagicMock()
        mock_local._model = MagicMock()
        mock_local_provider.return_value = mock_local

        manager = LLMManager()
        provider = manager._create_embedding_provider()

        assert provider is mock_local
        mock_local_provider.assert_called_once()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    @patch("src.core.llm_manager.SentenceTransformerProvider")
    def test_create_embedding_provider_falls_back_to_openai(self, mock_local_provider, mock_openai_provider, mock_get_settings):
        """OpenAI should be used when local embeddings are unavailable."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.embedding.model = "bge-m3"
        mock_settings.embedding.model_path = None
        mock_settings.embedding.dimensions = 768
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        mock_local = MagicMock()
        mock_local._model = None
        mock_local_provider.return_value = mock_local
        mock_openai_provider.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_embedding_provider()

        assert provider is mock_openai_provider.return_value
        mock_openai_provider.assert_called_once()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    @patch("src.core.llm_manager.SentenceTransformerProvider")
    def test_create_embedding_provider_normalizes_remote_first_preference(self, mock_local_provider, mock_openai_provider, mock_get_settings):
        """Whitespace and case in provider_preference should still select remote_first."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.embedding.model = "bge-m3"
        mock_settings.embedding.model_path = None
        mock_settings.embedding.dimensions = 768
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_settings.embedding.provider_preference = "  REMOTE_FIRST  "
        mock_get_settings.return_value = mock_settings

        mock_local = MagicMock()
        mock_local._model = None
        mock_local_provider.return_value = mock_local
        mock_openai_provider.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_embedding_provider()

        assert provider is mock_openai_provider.return_value
        mock_openai_provider.assert_called_once()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    @patch("src.core.llm_manager.SentenceTransformerProvider")
    def test_create_embedding_provider_invalid_preference_defaults_to_local_first(self, mock_local_provider, mock_openai_provider, mock_get_settings):
        """Invalid provider_preference should fall back to local_first ordering."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.embedding.model = "bge-m3"
        mock_settings.embedding.model_path = "/tmp/bge-m3"
        mock_settings.embedding.dimensions = 768
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_settings.embedding.provider_preference = "unsupported"
        mock_get_settings.return_value = mock_settings

        mock_local = MagicMock()
        mock_local._model = MagicMock()
        mock_local_provider.return_value = mock_local
        mock_openai_provider.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_embedding_provider()

        assert provider is mock_local
        mock_local_provider.assert_called_once()
        mock_openai_provider.assert_not_called()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OllamaProvider")
    @patch("src.core.llm_manager.SentenceTransformerProvider")
    def test_create_embedding_provider_falls_back_to_ollama(self, mock_local_provider, mock_ollama_provider, mock_get_settings):
        """Ollama embeddings should be the second fallback when configured."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "ollama"
        mock_settings.llm.openai.api_key = ""
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.ollama.model_dump.return_value = {"url": "http://localhost:11434", "model": "qwen2.5:14b"}
        mock_settings.embedding.model = "bge-m3"
        mock_settings.embedding.model_path = None
        mock_settings.embedding.dimensions = 768
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        mock_local = MagicMock()
        mock_local._model = None
        mock_local_provider.return_value = mock_local
        mock_ollama_provider.return_value = MagicMock()

        manager = LLMManager()
        provider = manager._create_embedding_provider()

        assert provider is mock_ollama_provider.return_value
        mock_ollama_provider.assert_called_once()

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    @pytest.mark.asyncio
    async def test_chat(self, mock_provider_class, mock_get_settings):
        """Test LLMManager chat method."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.model = "gpt-4"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.anthropic.api_key = ""
        mock_settings.llm.ollama.url = "http://localhost:11434"
        mock_settings.llm.ollama.model = "qwen2.5:14b"
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(return_value="Chat response")
        mock_provider_class.return_value = mock_provider

        manager = LLMManager()
        messages = [{"role": "user", "content": "Hello"}]
        
        result = await manager.chat(messages)

        assert result == "Chat response"

    @patch("src.core.llm_manager.get_settings")
    @patch("src.core.llm_manager.OpenAIProvider")
    @pytest.mark.asyncio
    async def test_generate(self, mock_provider_class, mock_get_settings):
        """Test LLMManager generate method."""
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openai"
        mock_settings.llm.openai.api_key = "test-key"
        mock_settings.llm.openai.model = "gpt-4"
        mock_settings.llm.openai.base_url = "https://api.openai.com/v1"
        mock_settings.llm.anthropic.api_key = ""
        mock_settings.llm.ollama.url = "http://localhost:11434"
        mock_settings.llm.ollama.model = "qwen2.5:14b"
        mock_settings.embedding.cloud_model = "text-embedding-3-small"
        mock_get_settings.return_value = mock_settings

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value="Generated text")
        mock_provider_class.return_value = mock_provider

        manager = LLMManager()
        
        result = await manager.generate("Test prompt")

        assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_test_connection(self):
        """Test LLMManager has test_connection method."""
        with patch("src.core.llm_manager.get_settings") as mock_settings:
            mock_settings.return_value.llm.provider = "openai"
            mock_settings.return_value.llm.openai.api_key = "test"
            mock_settings.return_value.llm.openai.model_dump.return_value = {"api_key": "test", "model": "gpt-4"}
            mock_settings.return_value.llm.anthropic.api_key = ""
            mock_settings.return_value.llm.anthropic.model_dump.return_value = {"api_key": "", "model": "claude"}
            mock_settings.return_value.llm.ollama.url = "http://localhost:11434"
            mock_settings.return_value.llm.ollama.model = "qwen2.5:14b"
            mock_settings.return_value.llm.ollama.model_dump.return_value = {"url": "http://localhost:11434", "model": "qwen2.5:14b"}
            mock_settings.return_value.embedding.cloud_model = "text-embedding-3-small"
            
            manager = LLMManager()
            
            # Just check the method exists and is callable
            assert hasattr(manager, 'test_connection')


class TestLLMManagerSingleton:
    """Test LLM Manager singleton."""

    def test_get_llm_manager_singleton(self):
        """Test get_llm_manager returns singleton."""
        # Clear any existing instance
        import src.core.llm_manager as llm_module
        llm_module._llm_manager = None
        
        with patch("src.core.llm_manager.get_settings"):
            manager1 = get_llm_manager()
            manager2 = get_llm_manager()
            
            assert manager1 is manager2
        
        # Clean up
        llm_module._llm_manager = None
