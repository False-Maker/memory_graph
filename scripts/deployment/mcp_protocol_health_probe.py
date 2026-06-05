#!/usr/bin/env python3
"""Protocol-level MCP health probe used by deployment scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from pydantic import AnyUrl

REQUIRED_TOOLS = {
    "answer_question",
    "search_memories",
    "preview_memory_layer",
    "save_memory",
    "list_memories",
    "get_graph_stats",
    "list_query_runs",
    "get_runtime_diagnostics",
}


async def run_probe(url: str, bearer_token: str) -> None:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except Exception as exc:  # pragma: no cover - exercised via shell wrapper
        raise SystemExit(
            "The official MCP SDK is required for health checks. "
            "Install mcp>=1.27,<2 before running this probe."
        ) from exc

    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else None

    async with streamablehttp_client(url, headers=headers) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            init_result = await session.initialize()
            print(
                json.dumps(
                    {
                        "server": init_result.serverInfo.name,
                        "version": init_result.serverInfo.version,
                    },
                    ensure_ascii=False,
                )
            )

            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            missing = sorted(REQUIRED_TOOLS - tool_names)
            if missing:
                raise RuntimeError(f"Missing required MCP tools: {missing}")
            print(
                json.dumps(
                    {
                        "tool_count": len(tool_names),
                        "required_tools_ok": True,
                    },
                    ensure_ascii=False,
                )
            )

            stats_result = await session.read_resource(AnyUrl("memory-graph://stats"))
            if not stats_result.contents:
                raise RuntimeError("stats resource returned no content")
            print(
                json.dumps(
                    {
                        "resource": "memory-graph://stats",
                        "ok": True,
                    },
                    ensure_ascii=False,
                )
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="MCP streamable-http endpoint URL.")
    parser.add_argument(
        "--bearer-token",
        default="",
        help="Optional bearer token for authenticated MCP endpoints.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(run_probe(args.url, args.bearer_token))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
