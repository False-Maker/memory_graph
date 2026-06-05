"""Regression tests for docs/API.md generation and route coverage."""

import subprocess
import sys
from pathlib import Path

DOCS_API_PATH = Path("docs/API.md")

def test_api_docs_matches_generated_output():
    """docs/API.md should be fully regenerated from the current code contract."""
    result = subprocess.run(
        [sys.executable, "scripts/generate_api_docs.py", "--stdout"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert DOCS_API_PATH.read_text(encoding="utf-8") == result.stdout


def test_api_docs_mentions_collectors_websocket_path():
    """Collector websocket should stay documented even though it is not in OpenAPI."""
    raw = DOCS_API_PATH.read_text(encoding="utf-8")
    assert "/api/collectors/ws/collectors" in raw
