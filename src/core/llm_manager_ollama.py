"""Ollama provider implementation for the LLM manager."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from src.core.llm_manager_base import LLMProvider, _safe_str

TEST_CONNECTION_TIMEOUT_SECONDS = 10.0


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.url = _safe_str(config.get("url", "http://localhost:11434"), "http://localhost:11434")
        self.model = _safe_str(config.get("model", "qwen2.5:14b"), "qwen2.5:14b")
        self.last_error: Optional[str] = None
        self.client = httpx.AsyncClient(base_url=self.url, timeout=120.0)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["options"] = {"num_predict": max_tokens}

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
        }
        if max_tokens:
            payload["options"] = {"num_predict": max_tokens}

        response = await self.client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            response = await self.client.post(
                "/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data.get("embedding", []))
        return embeddings

    async def test_connection(self) -> bool:
        try:
            response = await asyncio.wait_for(
                self.client.get("/api/tags"),
                timeout=TEST_CONNECTION_TIMEOUT_SECONDS,
            )
            self.last_error = None if response.status_code == 200 else (
                f"Ollama /api/tags returned HTTP {response.status_code}"
            )
            return response.status_code == 200
        except asyncio.TimeoutError:
            self.last_error = (
                f"Ollama connection test timed out after {TEST_CONNECTION_TIMEOUT_SECONDS}s"
            )
            return False
        except Exception as error:
            self.last_error = str(error)
            return False

    async def close(self) -> None:
        await self.client.aclose()
