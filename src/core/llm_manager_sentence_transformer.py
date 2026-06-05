"""Sentence-transformers embedding provider for the LLM manager."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.core.llm_manager_base import LLMProvider, _safe_int, _safe_str


class SentenceTransformerProvider(LLMProvider):
    """Local sentence-transformers embedding provider."""

    MODEL_ALIASES = {
        "bge-m3": "BAAI/bge-m3",
        "qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        raw_model_name = _safe_str(config.get("model", "BAAI/bge-m3"), "BAAI/bge-m3")
        self.model_name = self.MODEL_ALIASES.get(raw_model_name, raw_model_name)
        self.model_path = config.get("model_path")
        self.dimensions = _safe_int(config.get("dimensions"), None)
        self.model_ref = self.model_path or self.model_name
        self._model = None

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_ref)
        except ImportError:
            self._model = None
        except Exception:
            self._model = None

    @property
    def model(self):
        """Return the loaded sentence-transformers model."""
        if self._model is None:
            raise RuntimeError(
                "SentenceTransformer model not initialized. Install sentence-transformers and ensure the model is available."
            )
        return self._model

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        raise NotImplementedError("SentenceTransformer provider only supports embeddings")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        raise NotImplementedError("SentenceTransformer provider only supports embeddings")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        def _encode() -> List[List[float]]:
            encode_kwargs = {
                "normalize_embeddings": False,
                "convert_to_numpy": True,
            }
            if self.dimensions:
                encode_kwargs["truncate_dim"] = self.dimensions
            vectors = self.model.encode(texts, **encode_kwargs)
            return vectors.tolist()

        return await asyncio.to_thread(_encode)

    async def test_connection(self) -> bool:
        try:
            await self.embed(["test"])
            return True
        except Exception:
            return False
