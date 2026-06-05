#!/usr/bin/env python3
"""Generate docs/API.md from the current FastAPI OpenAPI spec."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.main import app


DOCS_PATH = ROOT / "docs/API.md"
IGNORED_OPENAPI_PATHS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}
NON_OPENAPI_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/api/collectors/ws/collectors",
        "summary": "Collector websocket endpoint",
        "status_codes": "101",
        "notes": "WebSocket endpoint, intentionally not emitted by OpenAPI.",
    }
]
METHOD_ORDER = {
    "get": 0,
    "post": 1,
    "put": 2,
    "patch": 3,
    "delete": 4,
}
SCHEMA_SECTIONS = [
    ("ConfigResponse", "GET /api/v1/config 响应"),
    ("SecretStorageStatus", "secret_storage 对象"),
    ("ConfigUpdate", "PUT /api/v1/config 请求体"),
    ("ConfigUpdateResponse", "PUT /api/v1/config 成功响应"),
    ("ConfigActionErrorResponse", "PUT /api/v1/config 失败响应（503）"),
    ("ConnectionTestResponse", "POST /api/v1/config/test-connection 响应"),
]
ROUTE_GROUPS = [
    ("系统与运行态", lambda path: path in {"/", "/health", "/api/v1/diagnostics/runtime", "/{full_path}"} or path.startswith("/sidecar/")),
    ("配置", lambda path: path.startswith("/api/v1/config")),
    ("记忆", lambda path: path.startswith("/api/v1/memories")),
    ("检索", lambda path: path.startswith("/api/v1/query")),
    ("图谱", lambda path: path.startswith("/api/v1/graph")),
    ("社区", lambda path: path.startswith("/api/v1/communities")),
    ("数据与运维", lambda path: path.startswith("/api/v1/data") or path.startswith("/api/v1/evals")),
    ("同步", lambda path: path.startswith("/api/v1/sync")),
    ("采集器", lambda path: path.startswith("/api/collectors")),
]


def _sort_status_code(value: str) -> tuple[int, str]:
    return (0, value) if value.isdigit() else (1, value)


def _format_status_codes(operation: dict) -> str:
    statuses = sorted(operation.get("responses", {}).keys(), key=_sort_status_code)
    return ", ".join(statuses) if statuses else "-"


def _format_schema_type(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]

    if "anyOf" in schema:
        parts = []
        for item in schema["anyOf"]:
            formatted = _format_schema_type(item)
            if formatted not in parts:
                parts.append(formatted)
        return " or ".join(parts)

    if "enum" in schema:
        return "enum[" + ", ".join(str(item) for item in schema["enum"]) + "]"

    schema_type = schema.get("type")
    if schema_type == "array":
        return f"array<{_format_schema_type(schema.get('items', {}))}>"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"object<string, {_format_schema_type(additional)}>"
        return "object"
    if schema_type:
        return schema_type
    return "unknown"


def _format_default(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "-"
    return str(value)


def _load_spec() -> dict:
    return app.openapi()


def _iter_operations(spec: dict) -> list[dict]:
    operations = []
    for path, methods in spec.get("paths", {}).items():
        if path in IGNORED_OPENAPI_PATHS:
            continue
        for method, operation in methods.items():
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary") or operation.get("operationId") or "-",
                    "status_codes": _format_status_codes(operation),
                    "tags": ", ".join(operation.get("tags", [])) or "-",
                }
            )
    return sorted(
        operations,
        key=lambda item: (item["path"], METHOD_ORDER.get(item["method"].lower(), 99), item["method"]),
    )


def _group_operations(operations: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: list[tuple[str, list[dict]]] = []
    remaining = list(operations)

    for label, matcher in ROUTE_GROUPS:
        matched = [item for item in remaining if matcher(item["path"])]
        if not matched:
            continue
        grouped.append((label, matched))
        remaining = [item for item in remaining if not matcher(item["path"])]

    if remaining:
        grouped.append(("其他", remaining))

    return grouped


def _render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["_无_"]

    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _render_route_sections(spec: dict) -> list[str]:
    operations = _iter_operations(spec)
    sections: list[str] = []

    for label, items in _group_operations(operations):
        sections.append(f"### {label}")
        sections.extend(
            _render_table(
                ["方法", "路径", "说明", "状态码", "标签"],
                [
                    [
                        item["method"],
                        f"`{item['path']}`",
                        item["summary"],
                        item["status_codes"],
                        item["tags"],
                    ]
                    for item in items
                ],
            )
        )
        sections.append("")

    sections.append("### 非 OpenAPI 入口")
    sections.extend(
        _render_table(
            ["方法", "路径", "说明", "状态码", "备注"],
            [
                [
                    item["method"],
                    f"`{item['path']}`",
                    item["summary"],
                    item["status_codes"],
                    item["notes"],
                ]
                for item in NON_OPENAPI_ENDPOINTS
            ],
        )
    )
    return sections


def _render_schema_table(spec: dict, schema_name: str) -> list[str]:
    schema = spec.get("components", {}).get("schemas", {}).get(schema_name)
    if not schema:
        return [f"_未找到 schema `{schema_name}`_"]

    required = set(schema.get("required", []))
    rows = []
    for field_name, field_schema in schema.get("properties", {}).items():
        rows.append(
            [
                f"`{field_name}`",
                _format_schema_type(field_schema),
                "yes" if field_name in required else "no",
                _format_default(field_schema.get("default")),
                field_schema.get("description") or "-",
            ]
        )

    return _render_table(["字段", "类型", "必填", "默认值", "说明"], rows)


def render_api_docs() -> str:
    spec = _load_spec()
    operations = _iter_operations(spec)
    lines = [
        "# Memory Graph API 文档",
        "",
        "- 状态: Active",
        "- 对齐基线: `src.api.main:app`",
        "- 生成方式: `python3 scripts/generate_api_docs.py`",
        "- 维护策略: 本文档由当前 OpenAPI 与 settings contract 自动生成；接口变更后必须重新生成并通过 `tests/test_api_docs.py`",
        "",
        "## 1. 说明",
        "",
        "这份文档不再手工维护整页接口清单，而是直接从当前代码暴露的 OpenAPI 和关键 settings schema 生成。",
        "",
        "本文档保留三类信息：",
        "",
        "- 当前公开 HTTP / WebSocket 入口地图",
        "- 关键 settings contract（配置读取、保存、连通性测试、secure secret store 行为）",
        "- 文档刷新命令与 drift 守卫入口",
        "",
        "更细的请求/响应定义仍以 Swagger `/docs` 与 OpenAPI `/openapi.json` 为准。",
        "",
        "## 2. 基础信息",
        "",
        "| 项目 | 值 |",
        "| --- | --- |",
        "| 默认基础地址 | `http://127.0.0.1:8000` |",
        "| Swagger | `/docs` |",
        "| OpenAPI JSON | `/openapi.json` |",
        "| 当前公开 HTTP paths | `" + str(len({item['path'] for item in operations})) + "` |",
        "| Sidecar 代理 | `/sidecar/health`、`/sidecar/ready` |",
        "",
        "## 3. 响应约定",
        "",
        "- 当前接口没有全局统一的 `{success,data}` 包装。",
        "- 读取类接口通常直接返回对象或数组；管理类接口会按路由定义返回独立 schema。",
        "- 失败响应默认遵循 FastAPI 风格；`PUT /api/v1/config` 的 secure secret store 不可用场景额外提供稳定的错误响应体。",
        "- 常见状态码：`200`、`400`、`404`、`422`、`500`、`502`、`503`。",
        "",
        "## 4. 文档维护",
        "",
        "```bash",
        "python3 scripts/generate_api_docs.py",
        "python3 scripts/generate_api_docs.py --check",
        "python3 -m pytest tests/test_api_docs.py",
        "```",
        "",
        "- `python3 scripts/generate_api_docs.py` 会刷新 [docs/API.md](/home/elucid/projects/web/Memory_graph/docs/API.md)。",
        "- `--check` 适合本地 pre-commit 或 CI 做 docs drift 守卫。",
        "- `tests/test_api_docs.py` 会把文档生成结果和仓库内文件做逐字比对。",
        "",
        "## 5. 关键 Settings Contract",
        "",
        "- `GET /api/v1/config` 现在同时暴露 `secret_storage`，让设置页知道当前环境是 `system_keyring` 还是 `environment_only`。",
        "- `PUT /api/v1/config` 在 secure secret store 不可用且请求包含新 API key 时，返回稳定的 `503` 错误响应，而不是只抛原始异常文本。",
        "- 设置 `MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE=1` 会显式进入 `environment_only` 模式，适合无 keyring 部署或隔离 smoke。",
        "- `POST /api/v1/config/test-connection` 仍只测试当前表单值，不会持久化配置。",
        "",
    ]

    for schema_name, title in SCHEMA_SECTIONS:
        lines.append(f"### {title}")
        lines.extend(_render_schema_table(spec, schema_name))
        lines.append("")

    lines.extend(
        [
            "## 6. 当前公开路由清单",
            "",
        ]
    )
    lines.extend(_render_route_sections(spec))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only check whether docs/API.md is up to date.")
    parser.add_argument("--stdout", action="store_true", help="Print generated Markdown to stdout.")
    args = parser.parse_args()

    rendered = render_api_docs()

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    if args.check:
        current = DOCS_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print("docs/API.md is out of date. Run: python3 scripts/generate_api_docs.py", file=sys.stderr)
            return 1
        return 0

    DOCS_PATH.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
