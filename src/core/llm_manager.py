"""Public facade for the LLM manager and provider imports."""

from __future__ import annotations

from typing import Optional

from src.core.config import get_settings
from src.core.llm_manager_anthropic import AnthropicProvider
from src.core.llm_manager_base import LLMProvider
from src.core.llm_manager_ollama import OllamaProvider
from src.core.llm_manager_openai import OpenAIProvider
from src.core.llm_manager_runtime import LLMManagerCore, ProviderRegistry
from src.core.llm_manager_sentence_transformer import SentenceTransformerProvider


class LLMManager(LLMManagerCore):
    """Compatibility facade that preserves the historic public import surface."""

    def __init__(self, settings=None):
        resolved_settings = settings or get_settings()
        super().__init__(
            settings=resolved_settings,
            provider_registry=ProviderRegistry(
                openai=OpenAIProvider,
                anthropic=AnthropicProvider,
                ollama=OllamaProvider,
                sentence_transformer=SentenceTransformerProvider,
            ),
        )


_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Return the cached LLM manager singleton."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


def reset_llm_manager() -> None:
    """Reset the cached LLM manager singleton."""
    global _llm_manager
    _llm_manager = None
