"""
API Routes - Config
"""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from src.api.schemas.config import (
    ConfigActionErrorResponse,
    ConfigResponse,
    ConfigUpdate,
    ConfigUpdateResponse,
    ConnectionTestResponse,
)
from src.core.config import (
    get_config_path,
    get_settings,
    load_raw_yaml_config,
    reload_settings,
    save_yaml_config,
)
from src.core.llm_manager import LLMManager, get_llm_manager, reset_llm_manager
from src.core.graph_store import get_graph_store, reset_graph_store
from src.core.secret_store import (
    SecretStoreError,
    SecretStoreUnavailableError,
    build_secret_store_unavailable_message,
    get_secret_storage_status,
    has_configured_api_key,
    store_api_key,
)
from src.core.vector_store import get_vector_store, reset_vector_store


router = APIRouter(prefix="/api/v1/config", tags=["config"])
GRAPH_BACKEND_LABEL = "NetworkX + SQLite"
SECRET_FIELD_SPECS = {
    "openai_api_key": ("openai", ("llm", "openai", "api_key")),
    "anthropic_api_key": ("anthropic", ("llm", "anthropic", "api_key")),
}


def _build_config_response(settings) -> ConfigResponse:
    return ConfigResponse(
        llm_provider=settings.llm.provider,
        embedding_model=settings.embedding.model,
        graph_backend=GRAPH_BACKEND_LABEL,
        vector_store_type=settings.database.vector.type,
        app_host=settings.app.host,
        app_port=settings.app.port,
        openai_base_url=settings.llm.openai.base_url,
        openai_model=settings.llm.openai.model,
        openai_api_key_configured=has_configured_api_key(settings, "openai"),
        anthropic_base_url=settings.llm.anthropic.base_url,
        anthropic_model=settings.llm.anthropic.model,
        anthropic_api_key_configured=has_configured_api_key(settings, "anthropic"),
        ollama_url=settings.llm.ollama.url,
        ollama_model=settings.llm.ollama.model,
        secret_storage=get_secret_storage_status(),
    )


def _set_nested(config_dict, path, value) -> None:
    cursor = config_dict
    for key in path[:-1]:
        nested = cursor.get(key)
        if not isinstance(nested, dict):
            nested = {}
            cursor[key] = nested
        cursor = nested
    cursor[path[-1]] = value


def _apply_config_update(
    config_dict: dict,
    request: ConfigUpdate,
    *,
    include_secret_fields: bool = False,
) -> dict:
    payload = request.model_dump(exclude_none=True)

    if "llm_provider" in payload:
        _set_nested(config_dict, ("llm", "provider"), payload["llm_provider"])

    if "openai_base_url" in payload:
        _set_nested(config_dict, ("llm", "openai", "base_url"), payload["openai_base_url"])
    if "openai_model" in payload:
        _set_nested(config_dict, ("llm", "openai", "model"), payload["openai_model"])
    if include_secret_fields and payload.get("openai_api_key"):
        _set_nested(config_dict, ("llm", "openai", "api_key"), payload["openai_api_key"])

    if "anthropic_model" in payload:
        _set_nested(config_dict, ("llm", "anthropic", "model"), payload["anthropic_model"])
    if "anthropic_base_url" in payload:
        _set_nested(config_dict, ("llm", "anthropic", "base_url"), payload["anthropic_base_url"])
    if include_secret_fields and payload.get("anthropic_api_key"):
        _set_nested(config_dict, ("llm", "anthropic", "api_key"), payload["anthropic_api_key"])

    if "ollama_url" in payload:
        _set_nested(config_dict, ("llm", "ollama", "url"), payload["ollama_url"])
    if "ollama_model" in payload:
        _set_nested(config_dict, ("llm", "ollama", "model"), payload["ollama_model"])

    return config_dict


def _reload_runtime_state():
    reload_settings()
    reset_llm_manager()
    reset_graph_store()
    reset_vector_store()


def _build_settings_with_override(current_settings, request: ConfigUpdate):
    updated_config = _apply_config_update(
        current_settings.model_dump(),
        request,
        include_secret_fields=True,
    )
    return type(current_settings)(**updated_config)


def _build_effective_update_values(settings, *, include_secret_fields: bool = True) -> dict:
    payload = {
        "llm_provider": settings.llm.provider,
        "openai_base_url": settings.llm.openai.base_url,
        "openai_model": settings.llm.openai.model,
        "anthropic_base_url": settings.llm.anthropic.base_url,
        "anthropic_model": settings.llm.anthropic.model,
        "ollama_url": settings.llm.ollama.url,
        "ollama_model": settings.llm.ollama.model,
    }
    if include_secret_fields:
        payload["openai_api_key"] = settings.llm.openai.api_key
        payload["anthropic_api_key"] = settings.llm.anthropic.api_key
    return payload


def _has_effective_config_changes(
    settings,
    request: ConfigUpdate,
    *,
    include_secret_fields: bool = True,
) -> bool:
    payload = request.model_dump(exclude_none=True)
    current_values = _build_effective_update_values(settings, include_secret_fields=include_secret_fields)
    if not include_secret_fields:
        payload = {key: value for key, value in payload.items() if key not in SECRET_FIELD_SPECS}
    return any(payload.get(key) != current_values.get(key) for key in payload)


def _extract_secret_updates(request: ConfigUpdate) -> dict[str, str]:
    payload = request.model_dump(exclude_none=True)
    updates: dict[str, str] = {}
    for field_name, (provider, _path) in SECRET_FIELD_SPECS.items():
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            updates[provider] = value.strip()
    return updates


def _clear_persisted_secret_fields(config_dict: dict, providers: set[str]) -> None:
    for _field_name, (provider, path) in SECRET_FIELD_SPECS.items():
        if provider in providers:
            _set_nested(config_dict, path, "")


def _split_connection_results(raw_results: dict) -> tuple[dict, dict]:
    providers = {}
    provider_errors = {}

    for key, value in raw_results.items():
        if key.endswith("_error") and isinstance(value, str):
            provider_errors[key.removesuffix("_error")] = value
        elif isinstance(value, bool):
            providers[key] = value

    return providers, provider_errors


def _build_secret_store_unavailable_response(providers: list[str]) -> JSONResponse:
    secret_storage = get_secret_storage_status()
    payload = ConfigActionErrorResponse(
        code="secure_secret_store_unavailable",
        message=build_secret_store_unavailable_message(),
        providers=providers,
        fallback_env_vars=secret_storage["fallback_env_vars"],
        secret_storage=secret_storage,
    )
    return JSONResponse(status_code=503, content=payload.model_dump())


@router.get("", response_model=ConfigResponse)
async def get_config():
    """Get current configuration"""
    try:
        return _build_config_response(get_settings())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "",
    response_model=ConfigUpdateResponse,
    responses={
        503: {
            "model": ConfigActionErrorResponse,
            "description": "Secure secret storage is unavailable for API key persistence.",
        }
    },
)
async def update_config(request: ConfigUpdate):
    """Update configuration"""
    secret_updates: dict[str, str] = {}
    try:
        current_settings = get_settings()
        secret_updates = _extract_secret_updates(request)
        has_non_secret_changes = _has_effective_config_changes(
            current_settings,
            request,
            include_secret_fields=False,
        )
        has_secret_changes = any(
            secret_updates.get(provider) != getattr(getattr(current_settings.llm, provider), "api_key", "")
            for provider in secret_updates
        )

        if not has_non_secret_changes and not has_secret_changes:
            return {
                "success": True,
                "message": "Configuration unchanged"
            }

        if has_secret_changes:
            secret_storage = get_secret_storage_status()
            if not secret_storage["available"]:
                return _build_secret_store_unavailable_response(list(secret_updates))

        config_path = get_config_path()
        config_dict = load_raw_yaml_config(config_path)
        updated_config = _apply_config_update(config_dict, request)
        for provider, value in secret_updates.items():
            store_api_key(provider, value)
        _clear_persisted_secret_fields(updated_config, set(secret_updates))
        save_yaml_config(config_path, updated_config)
        _reload_runtime_state()

        return {
            "success": True,
            "message": f"Configuration saved to {config_path.name}"
        }
    except SecretStoreUnavailableError:
        return _build_secret_store_unavailable_response(list(secret_updates))
    except SecretStoreError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connections(request: ConfigUpdate | None = Body(default=None)):
    """Test all connections"""
    llm = None
    close_llm_after_use = False
    try:
        settings = get_settings()
        if request and request.model_dump(exclude_none=True):
            settings = _build_settings_with_override(settings, request)
            llm = LLMManager(settings=settings)
            close_llm_after_use = True
        else:
            llm = get_llm_manager()
        raw_test_results = await llm.test_connection()
        test_results, provider_errors = _split_connection_results(raw_test_results)
        graph_store = get_graph_store()
        graph_ok = await graph_store.test_connection()
        vector_store = get_vector_store()
        vector_ok = await vector_store.test_connection()

        current_provider_ok = test_results.get("current")
        if current_provider_ok is None:
            current_provider_ok = test_results.get(settings.llm.provider)
        current_error = provider_errors.get("current") or provider_errors.get(settings.llm.provider)
        provider_ok = (
            current_provider_ok
            if current_provider_ok is not None
            else any(test_results.values())
        )
        success = bool(provider_ok) and graph_ok and vector_ok

        return ConnectionTestResponse(
            success=success,
            providers=test_results,
            provider_errors=provider_errors,
            graph_store=graph_ok,
            vector_store=vector_ok,
            current_error=current_error,
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            providers={},
            provider_errors={},
            current_error=None,
            error=str(e)
        )
    finally:
        if close_llm_after_use and isinstance(llm, LLMManager):
            await llm.close()
