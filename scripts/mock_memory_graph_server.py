#!/usr/bin/env python3
"""Run the Memory Graph API with a mock LLM for local sync smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


class MockLLMManager:
    """Minimal async LLM manager for local smoke tests."""

    async def embed(self, texts):
        return [[0.001] * 768 for _ in texts]

    async def generate(self, prompt, temperature=0.1, max_tokens=4096):
        return '{"entities": [], "relationships": [], "facts": [], "summary": "mock"}'

    async def test_connection(self):
        return {"current": True}


def main():
    from src.api.main import app
    import src.core.llm_manager as llm_manager_module
    import src.core.memory_service as memory_service_module
    import src.core.sync.service as sync_service_module

    mock = MockLLMManager()

    llm_manager_module.get_llm_manager = lambda: mock
    memory_service_module.get_llm_manager = lambda: mock
    sync_service_module.get_llm_manager = lambda: mock
    memory_service_module._memory_service = None
    sync_service_module._sync_service = None

    uvicorn.run(app, host="127.0.0.1", port=18000)


if __name__ == "__main__":
    main()
