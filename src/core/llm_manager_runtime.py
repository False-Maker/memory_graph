"""Core orchestration for the LLM manager public facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from src.core.llm_manager_base import (
    LLMProvider,
    _normalize_embedding_preference,
    _normalize_provider_name,
    _safe_int,
    _safe_str,
)


@dataclass(frozen=True)
class ProviderRegistry:
    """Provider implementations used by the public facade."""

    openai: Type[LLMProvider]
    anthropic: Type[LLMProvider]
    ollama: Type[LLMProvider]
    sentence_transformer: Type[LLMProvider]


class LLMManagerCore:
    """Provider orchestration and fallback logic shared by the facade."""

    def __init__(self, settings: Any, provider_registry: ProviderRegistry):
        self.settings = settings
        self._providers = provider_registry
        self._provider: Optional[LLMProvider] = None
        self._embedding_provider: Optional[LLMProvider] = None

    @property
    def provider(self) -> LLMProvider:
        """Return the configured chat/generation provider."""
        if self._provider is None:
            self._provider = self._create_provider()
        return self._provider

    @property
    def embedding_provider(self) -> LLMProvider:
        """Return the configured embedding provider."""
        if self._embedding_provider is None:
            self._embedding_provider = self._create_embedding_provider()
        return self._embedding_provider

    def _create_provider(self) -> LLMProvider:
        """Create the configured LLM provider instance."""
        provider_name = _normalize_provider_name(getattr(self.settings.llm, "provider", None))

        if provider_name == "openai":
            return self._providers.openai(self.settings.llm.openai.model_dump())
        if provider_name == "anthropic":
            return self._providers.anthropic(self.settings.llm.anthropic.model_dump())
        if provider_name == "ollama":
            return self._providers.ollama(self.settings.llm.ollama.model_dump())
        raise ValueError(f"Unknown LLM provider: {provider_name}")

    def _create_embedding_provider(self) -> LLMProvider:
        """Create the embedding provider according to the configured fallback order."""
        provider_preference = _normalize_embedding_preference(
            getattr(self.settings.embedding, "provider_preference", None),
            "local_first",
        )
        if provider_preference not in {
            "local_first",
            "remote_first",
            "local_only",
            "remote_only",
        }:
            provider_preference = "local_first"

        openai_api_key = _safe_str(getattr(self.settings.llm.openai, "api_key", None), "")
        openai_base_url = _safe_str(
            getattr(self.settings.llm.openai, "base_url", None),
            "https://api.openai.com/v1",
        )
        local_dimensions = _safe_int(
            getattr(self.settings.embedding, "dimensions", None),
            768,
        )
        cloud_dimensions = _safe_int(
            getattr(self.settings.embedding, "cloud_dimensions", None),
            local_dimensions,
        )

        local_config = {
            "model": self.settings.embedding.model,
            "model_path": self.settings.embedding.model_path,
            "dimensions": local_dimensions,
        }
        remote_config = {
            "api_key": _safe_str(
                getattr(self.settings.embedding, "cloud_api_key", None),
                openai_api_key,
            ) or openai_api_key,
            "model": _safe_str(
                getattr(self.settings.embedding, "cloud_model", None),
                "text-embedding-3-small",
            ),
            "base_url": _safe_str(
                getattr(self.settings.embedding, "cloud_base_url", None),
                openai_base_url,
            ) or openai_base_url,
            "dimensions": cloud_dimensions,
        }

        def build_local_provider() -> Optional[LLMProvider]:
            try:
                provider = self._providers.sentence_transformer(local_config)
                if provider._model is not None:
                    return provider
            except Exception:
                return None
            return None

        def build_remote_provider() -> Optional[LLMProvider]:
            if not remote_config["api_key"]:
                if _normalize_provider_name(getattr(self.settings.llm, "provider", None)) == "ollama":
                    try:
                        return self._providers.ollama(self.settings.llm.ollama.model_dump())
                    except Exception:
                        return None
                return None

            try:
                return self._providers.openai(remote_config)
            except Exception:
                return None

        if provider_preference == "remote_first":
            remote_provider = build_remote_provider()
            if remote_provider is not None:
                return remote_provider
            local_provider = build_local_provider()
            if local_provider is not None:
                return local_provider
        elif provider_preference == "remote_only":
            remote_provider = build_remote_provider()
            if remote_provider is not None:
                return remote_provider
            raise RuntimeError("Remote embedding provider is not configured or unavailable")
        elif provider_preference == "local_only":
            local_provider = build_local_provider()
            if local_provider is not None:
                return local_provider
            raise RuntimeError("Local embedding provider is not configured or unavailable")
        else:
            local_provider = build_local_provider()
            if local_provider is not None:
                return local_provider
            remote_provider = build_remote_provider()
            if remote_provider is not None:
                return remote_provider

        fallback_provider = build_remote_provider()
        if fallback_provider is not None:
            return fallback_provider

        raise RuntimeError("No embedding provider is configured or available")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a chat request."""
        return await self.provider.chat(messages, temperature, max_tokens)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text."""
        return await self.provider.generate(prompt, temperature, max_tokens)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors."""
        return await self.embedding_provider.embed(texts)

    async def test_connection(self) -> Dict[str, Any]:
        """Test all configured provider connections."""
        results: Dict[str, Any] = {}

        async def record_provider_result(
            result_key: str,
            provider: LLMProvider,
            fallback_error: str,
        ) -> None:
            try:
                ok = await provider.test_connection()
                results[result_key] = bool(ok)
                if not ok:
                    results[f"{result_key}_error"] = (
                        getattr(provider, "last_error", None) or fallback_error
                    )
            except Exception as error:
                results[result_key] = False
                results[f"{result_key}_error"] = str(error)

        current_provider_name = _normalize_provider_name(getattr(self.settings.llm, "provider", None))

        def build_provider_failure_message(provider_name: str) -> str:
            if provider_name == "openai":
                if not getattr(self.settings.llm.openai, "api_key", ""):
                    return "OpenAI API key is not configured"
                return (
                    "OpenAI connection test returned false for "
                    f"{getattr(self.settings.llm.openai, 'base_url', 'https://api.openai.com/v1')}"
                )

            if provider_name == "anthropic":
                if not getattr(self.settings.llm.anthropic, "api_key", ""):
                    return "Anthropic API key is not configured"
                return (
                    "Anthropic connection test returned false for model "
                    f"{getattr(self.settings.llm.anthropic, 'model', 'claude-sonnet-4-20250514')} "
                    f"at {getattr(self.settings.llm.anthropic, 'base_url', 'https://api.anthropic.com')}"
                )

            if provider_name == "ollama":
                return (
                    "Ollama endpoint did not respond successfully at "
                    f"{getattr(self.settings.llm.ollama, 'url', 'http://localhost:11434')}"
                )

            return f"{provider_name} connection test returned false"

        def current_provider_requires_credentials(provider_name: str) -> bool:
            return provider_name in {"openai", "anthropic"}

        def current_provider_has_required_credentials(provider_name: str) -> bool:
            if provider_name == "openai":
                return bool(getattr(self.settings.llm.openai, "api_key", ""))
            if provider_name == "anthropic":
                return bool(getattr(self.settings.llm.anthropic, "api_key", ""))
            return True

        current_provider_error = build_provider_failure_message(current_provider_name)
        if (
            current_provider_requires_credentials(current_provider_name)
            and not current_provider_has_required_credentials(current_provider_name)
        ):
            results["current"] = False
            results["current_error"] = current_provider_error
        else:
            await record_provider_result(
                "current",
                self.provider,
                current_provider_error,
            )

        if self.settings.llm.openai.api_key:
            openai_provider = self._providers.openai(self.settings.llm.openai.model_dump())
            await record_provider_result(
                "openai",
                openai_provider,
                build_provider_failure_message("openai"),
            )

        if self.settings.llm.anthropic.api_key:
            anthropic_provider = self._providers.anthropic(self.settings.llm.anthropic.model_dump())
            await record_provider_result(
                "anthropic",
                anthropic_provider,
                build_provider_failure_message("anthropic"),
            )

        ollama_provider = self._providers.ollama(self.settings.llm.ollama.model_dump())
        try:
            await record_provider_result(
                "ollama",
                ollama_provider,
                build_provider_failure_message("ollama"),
            )
        finally:
            await ollama_provider.close()

        return results

    async def close(self) -> None:
        """Close any providers that expose an async close hook."""
        for provider in (self._provider, self._embedding_provider):
            close_method = getattr(provider, "close", None)
            if callable(close_method):
                await close_method()

    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities and relationships from text."""
        from src.core.entity_extractor import EntityExtractor

        extractor = EntityExtractor(self)
        return await extractor.extract(text)

    async def generate_answer(self, context: str, question: str) -> str:
        """Generate an answer from the supplied context."""
        prompt = f"""Based on the following context, please answer the question.

Context:
{context}

Question: {question}

Please provide a clear and accurate answer based on the context above. If the context doesn't contain enough information to answer the question, please say so."""

        return await self.generate(prompt, temperature=0.3)
