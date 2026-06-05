"""Anthropic provider implementation for the LLM manager."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.core.llm_manager_base import LLMProvider, _safe_str

TEST_CONNECTION_TIMEOUT_SECONDS = 10.0


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = _safe_str(config.get("api_key", ""), "")
        self.model = _safe_str(
            config.get("model", "claude-sonnet-4-20250514"),
            "claude-sonnet-4-20250514",
        )
        self.base_url = _safe_str(
            config.get("base_url", "https://api.anthropic.com"),
            "https://api.anthropic.com",
        )
        self.last_error: Optional[str] = None

        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except ImportError:
            self.client = None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        if not self.client:
            raise RuntimeError("Anthropic client not initialized. Install anthropic package.")

        system = None
        for message in messages:
            if message.get("role") == "system":
                system = message.get("content")
                break

        user_messages = [message for message in messages if message.get("role") != "system"]

        response = await self.client.messages.create(
            model=self.model,
            messages=user_messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens or 4096,
            **kwargs,
        )
        return response.content[0].text

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature, max_tokens, **kwargs)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("Anthropic does not provide embedding API")

    async def test_connection(self) -> bool:
        try:
            await asyncio.wait_for(
                self.generate("test", max_tokens=5),
                timeout=TEST_CONNECTION_TIMEOUT_SECONDS,
            )
            self.last_error = None
            return True
        except asyncio.TimeoutError:
            self.last_error = (
                f"Anthropic connection test timed out after {TEST_CONNECTION_TIMEOUT_SECONDS}s"
            )
            return False
        except Exception as error:
            self.last_error = str(error)
            return False
