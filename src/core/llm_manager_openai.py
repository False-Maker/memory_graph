"""OpenAI provider implementation for the LLM manager."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.core.llm_manager_base import LLMProvider, _safe_int, _safe_str

TEST_CONNECTION_TIMEOUT_SECONDS = 10.0


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = _safe_str(config.get("api_key", ""), "")
        self.model = _safe_str(config.get("model", "gpt-4o"), "gpt-4o")
        self.base_url = _safe_str(
            config.get("base_url", "https://api.openai.com/v1"),
            "https://api.openai.com/v1",
        )
        self.last_error: Optional[str] = None
        self.dimensions = _safe_int(config.get("dimensions"), None)

        try:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
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
            raise RuntimeError("OpenAI client not initialized. Install openai package.")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content

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
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Install openai package.")

        payload = {
            "model": self.model,
            "input": texts,
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions

        response = await self.client.embeddings.create(**payload)
        return [item.embedding for item in response.data]

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
                f"OpenAI connection test timed out after {TEST_CONNECTION_TIMEOUT_SECONDS}s"
            )
            return False
        except Exception as error:
            self.last_error = str(error)
            return False
