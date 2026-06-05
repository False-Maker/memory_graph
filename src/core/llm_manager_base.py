"""Shared interfaces and normalization helpers for the LLM manager."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


def _safe_str(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default

    normalized = value.strip()
    return normalized or default


def _normalize_provider_name(value: Any, default: str = "openai") -> str:
    return _safe_str(value, default).lower()


def _normalize_embedding_preference(value: Any, default: str = "local_first") -> str:
    return _safe_str(value, default).lower()


def _safe_int(value: Any, default: Optional[int]) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


class LLMProvider(ABC):
    """LLM provider abstract base class."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Send a chat request and return the text response."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate text from a prompt."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors."""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Check whether the provider is reachable."""
