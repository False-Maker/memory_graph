"""Drift guards for deployment standardization assets."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def test_standardization_assets_exist():
    required_paths = [
        ROOT / ".dockerignore",
        ROOT / "docs/FINAL_ACCEPTANCE.md",
        ROOT / "requirements-runtime.txt",
        ROOT / "requirements-local-embedding.txt",
        ROOT / "scripts/deployment/.env.mcp.example",
        ROOT / "scripts/deployment/final-delivery-check.sh",
        ROOT / "scripts/deployment/mcp_protocol_health_probe.py",
        ROOT / "scripts/deployment/nginx-proxy-docker-smoke.sh",
        ROOT / "scripts/deployment/systemd/memory-graph-api.service.example",
        ROOT / "scripts/deployment/systemd/memory-graph-sidecar.service.example",
        ROOT / "scripts/deployment/systemd/memory-graph-mcp.service.example",
        ROOT / "scripts/deployment/compose/.env.compose.example",
        ROOT / "scripts/deployment/compose/Dockerfile.api",
        ROOT / "scripts/deployment/compose/Dockerfile.sidecar",
        ROOT / "scripts/deployment/compose/Dockerfile.mcp",
        ROOT / "scripts/deployment/compose/docker-compose.yml",
        ROOT / "docs/deployment/standardization.md",
        ROOT / "docs/deployment/reverse-proxy-nginx.sample.conf",
        ROOT / "docs/deployment/reverse-proxy-caddy.sample",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    assert not missing, f"Missing deployment standardization assets: {missing}"


def test_dockerignore_and_systemd_templates_keep_standard_guardrails():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "config/settings.yaml" in dockerignore
    assert ".env.*" in dockerignore

    api_service = (ROOT / "scripts/deployment/systemd/memory-graph-api.service.example").read_text(encoding="utf-8")
    sidecar_service = (ROOT / "scripts/deployment/systemd/memory-graph-sidecar.service.example").read_text(encoding="utf-8")
    mcp_service = (ROOT / "scripts/deployment/systemd/memory-graph-mcp.service.example").read_text(encoding="utf-8")

    assert "memory-graph-sidecar.service" in api_service
    assert "npm --prefix /srv/memory-graph/frontend/api run build" in sidecar_service
    assert "src.mcp --transport streamable-http" in mcp_service


def test_compose_dockerfiles_use_slim_python_runtime():
    dockerfile_api = (ROOT / "scripts/deployment/compose/Dockerfile.api").read_text(encoding="utf-8")
    dockerfile_mcp = (ROOT / "scripts/deployment/compose/Dockerfile.mcp").read_text(encoding="utf-8")

    assert "FROM python:3.13-slim-bookworm AS runner" in dockerfile_api
    assert "FROM python:3.13-slim-bookworm AS runner" in dockerfile_mcp
    assert "apt-get install -y --no-install-recommends bash" in dockerfile_mcp


def test_compose_template_keeps_standard_service_names():
    compose_path = ROOT / "scripts/deployment/compose/docker-compose.yml"
    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    services = payload.get("services", {})
    assert set(services) == {
        "memory-graph-api",
        "memory-graph-sidecar",
        "memory-graph-mcp",
    }

    compose_env = (ROOT / "scripts/deployment/compose/.env.compose.example").read_text(encoding="utf-8")
    api_service = services["memory-graph-api"]
    mcp_service = services["memory-graph-mcp"]

    assert "COMPOSE_API_PUBLISHED_PORT" in compose_env
    assert "COMPOSE_MCP_PUBLISHED_PORT" in compose_env
    assert "COMPOSE_INCLUDE_LOCAL_EMBEDDING" in compose_env
    assert api_service["ports"] == ['${COMPOSE_API_PUBLISHED_PORT:-8000}:8000']
    assert mcp_service["ports"] == ['${COMPOSE_MCP_PUBLISHED_PORT:-8001}:8001']
    assert api_service["build"]["args"]["INCLUDE_LOCAL_EMBEDDING"] == '${COMPOSE_INCLUDE_LOCAL_EMBEDDING:-false}'
    assert mcp_service["build"]["args"]["INCLUDE_LOCAL_EMBEDDING"] == '${COMPOSE_INCLUDE_LOCAL_EMBEDDING:-false}'


def test_runtime_and_local_embedding_requirements_are_split():
    runtime_requirements = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    local_embedding_requirements = (ROOT / "requirements-local-embedding.txt").read_text(encoding="utf-8")
    root_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "sentence-transformers" not in runtime_requirements
    assert "sentence-transformers" in local_embedding_requirements
    assert "-r requirements-runtime.txt" in root_requirements
    assert "-r requirements-local-embedding.txt" in root_requirements


def test_legacy_streamable_http_scripts_delegate_to_canonical_mcp_scripts():
    wrappers = {
        "scripts/deployment/mcp-streamable-http-start.sh": "mcp-start.sh",
        "scripts/deployment/mcp-streamable-http-stop.sh": "mcp-stop.sh",
        "scripts/deployment/mcp-streamable-http-health-check.sh": "mcp-health-check.sh",
    }

    for relative_path, target_name in wrappers.items():
        raw = (ROOT / relative_path).read_text(encoding="utf-8")
        assert f'exec bash "${{ROOT_DIR}}/scripts/deployment/{target_name}" "$@"' in raw


def test_http_health_scripts_include_runtime_diagnostics_contract():
    intranet_health = (ROOT / "scripts/deployment/intranet-health-check.sh").read_text(encoding="utf-8")
    cloud_smoke = (ROOT / "scripts/deployment/cloud-smoke-check.sh").read_text(encoding="utf-8")

    assert "/api/v1/diagnostics/runtime" in intranet_health
    assert "/api/v1/diagnostics/runtime" in cloud_smoke


def test_mcp_health_check_uses_protocol_level_probe():
    mcp_health = (ROOT / "scripts/deployment/mcp-health-check.sh").read_text(encoding="utf-8")
    probe = (ROOT / "scripts/deployment/mcp_protocol_health_probe.py").read_text(encoding="utf-8")

    assert "mcp_protocol_health_probe.py" in mcp_health
    assert "initialize" in probe
    assert "list_tools" in probe
    assert "memory-graph://stats" in probe


def test_standardization_docs_describe_unified_contract():
    standardization = (ROOT / "docs/deployment/standardization.md").read_text(encoding="utf-8")
    enhancement_stage = (ROOT / "docs/ENHANCEMENT_STAGE.md").read_text(encoding="utf-8")
    delivery = (ROOT / "docs/DELIVERY.md").read_text(encoding="utf-8")
    final_acceptance = (ROOT / "docs/FINAL_ACCEPTANCE.md").read_text(encoding="utf-8")
    deployment_docs = [
        ROOT / "docs/deployment/standardization.md",
        ROOT / "docs/deployment/t15-intranet-deployment.md",
        ROOT / "docs/deployment/t18-mcp-deployment.md",
        ROOT / "docs/deployment/t18-mcp-streamable-http.md",
        ROOT / "docs/deployment/t6-dual-deployment-baseline.md",
    ]

    assert "GET /api/v1/diagnostics/runtime" in standardization
    assert "read_resource(memory-graph://stats)" in standardization
    assert "nginx-proxy-docker-smoke.sh" in standardization
    assert "Deployment Standardization` 已完成" in enhancement_stage
    assert "nginx` 已支持通过 Docker 做真实代理联调" in delivery
    assert "最终验收报告" in final_acceptance
    assert "bash scripts/deployment/final-delivery-check.sh" in final_acceptance
    for path in deployment_docs:
        raw = path.read_text(encoding="utf-8")
        assert "/home/elucid/projects/web/Memory_graph/" not in raw
