"""Secure API key storage helpers."""

from __future__ import annotations

import logging
import os
from typing import Any


logger = logging.getLogger(__name__)

SECRET_SERVICE_NAME = "memory-graph"
SECRET_STORAGE_FALLBACK_ENV_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
SECRET_STORE_DISABLE_ENV = "MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE"
_PROVIDER_SECRET_NAMES = {
    "openai": "llm.openai.api_key",
    "anthropic": "llm.anthropic.api_key",
}


class SecretStoreError(RuntimeError):
    """Base error for secure secret storage failures."""


class SecretStoreUnavailableError(SecretStoreError):
    """Raised when no supported secure secret backend is available."""


def _secret_store_disabled_by_env() -> bool:
    return str(os.getenv(SECRET_STORE_DISABLE_ENV, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in _PROVIDER_SECRET_NAMES:
        supported = ", ".join(sorted(_PROVIDER_SECRET_NAMES))
        raise ValueError(f"Unsupported secret provider '{provider}'. Supported values: {supported}")
    return normalized


def _load_keyring_module() -> Any | None:
    try:
        import keyring  # type: ignore

        return keyring
    except Exception:
        return None


def _get_keyring_backend(keyring_module: Any) -> Any | None:
    try:
        return keyring_module.get_keyring()
    except Exception:
        return None


def _describe_keyring_backend(keyring_module: Any) -> str | None:
    backend = _get_keyring_backend(keyring_module)
    if backend is None:
        return None

    return f"{backend.__class__.__module__}.{backend.__class__.__qualname__}"


def _keyring_backend_is_usable(keyring_module: Any) -> bool:
    backend = _get_keyring_backend(keyring_module)
    if backend is None:
        return False

    backend_name = f"{backend.__class__.__module__}.{backend.__class__.__qualname__}".lower()
    return "keyring.backends.fail" not in backend_name


def secure_secret_store_available() -> bool:
    """Return whether a secure keyring backend is available for persistence."""
    if _secret_store_disabled_by_env():
        return False

    keyring_module = _load_keyring_module()
    if keyring_module is None:
        return False

    return _keyring_backend_is_usable(keyring_module)


def _build_status_message(*, available: bool, disabled_by_env: bool = False) -> str:
    env_vars = " / ".join(SECRET_STORAGE_FALLBACK_ENV_VARS)
    if disabled_by_env:
        return (
            f"Secure secret storage is disabled by {SECRET_STORE_DISABLE_ENV}. "
            f"The Settings page can save non-secret fields only; provide API keys via {env_vars}."
        )

    if available:
        return "API keys will be stored in the system keyring and kept out of config/settings.yaml."

    return (
        "No usable system keyring backend is available. "
        f"The Settings page can save non-secret fields only; provide API keys via {env_vars} "
        "or configure a supported system keyring."
    )


def build_secret_store_unavailable_message() -> str:
    """Return the stable error message for missing secure secret storage."""
    env_vars = " / ".join(SECRET_STORAGE_FALLBACK_ENV_VARS)
    if _secret_store_disabled_by_env():
        return (
            f"Secure secret storage is disabled by {SECRET_STORE_DISABLE_ENV}. "
            f"API keys were not saved. Use {env_vars} environment variables instead."
        )

    return (
        "Secure secret storage is unavailable in this environment. "
        f"API keys were not saved. Use {env_vars} environment variables or configure a supported system keyring."
    )


def get_secret_storage_status() -> dict[str, Any]:
    """Describe the current secret storage behavior for UI/API consumers."""
    if _secret_store_disabled_by_env():
        return {
            "available": False,
            "storage_type": "environment_only",
            "backend": f"disabled_by_env:{SECRET_STORE_DISABLE_ENV}",
            "message": _build_status_message(available=False, disabled_by_env=True),
            "fallback_env_vars": list(SECRET_STORAGE_FALLBACK_ENV_VARS),
        }

    keyring_module = _load_keyring_module()
    backend_name = _describe_keyring_backend(keyring_module) if keyring_module is not None else None
    available = bool(keyring_module is not None and _keyring_backend_is_usable(keyring_module))

    return {
        "available": available,
        "storage_type": "system_keyring" if available else "environment_only",
        "backend": backend_name,
        "message": _build_status_message(available=available),
        "fallback_env_vars": list(SECRET_STORAGE_FALLBACK_ENV_VARS),
    }


def _secret_name(provider: str) -> str:
    return _PROVIDER_SECRET_NAMES[_normalize_provider(provider)]


def get_stored_api_key(provider: str) -> str:
    """Read one provider API key from the secure store, if available."""
    if _secret_store_disabled_by_env():
        return ""

    keyring_module = _load_keyring_module()
    if keyring_module is None or not _keyring_backend_is_usable(keyring_module):
        return ""

    try:
        value = keyring_module.get_password(SECRET_SERVICE_NAME, _secret_name(provider))
    except Exception as exc:
        logger.warning("Failed to read %s API key from secure store: %s", provider, exc)
        return ""

    if not isinstance(value, str):
        return ""
    return value.strip()


def store_api_key(provider: str, value: str) -> None:
    """Persist one provider API key into the secure store."""
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return

    if _secret_store_disabled_by_env():
        raise SecretStoreUnavailableError(build_secret_store_unavailable_message())

    keyring_module = _load_keyring_module()
    if keyring_module is None or not _keyring_backend_is_usable(keyring_module):
        raise SecretStoreUnavailableError(build_secret_store_unavailable_message())

    try:
        keyring_module.set_password(
            SECRET_SERVICE_NAME,
            _secret_name(provider),
            normalized_value,
        )
    except Exception as exc:
        raise SecretStoreError(f"Failed to persist {provider} API key in the secure store: {exc}") from exc


def delete_api_key(provider: str) -> None:
    """Delete one provider API key from the secure store, if present."""
    if _secret_store_disabled_by_env():
        return

    keyring_module = _load_keyring_module()
    if keyring_module is None or not _keyring_backend_is_usable(keyring_module):
        return

    try:
        keyring_module.delete_password(SECRET_SERVICE_NAME, _secret_name(provider))
    except Exception:
        return


def has_configured_api_key(settings: Any, provider: str) -> bool:
    """Return whether one provider has an API key from runtime settings or secure storage."""
    normalized_provider = _normalize_provider(provider)
    current_value = ""
    llm_config = getattr(getattr(settings, "llm", None), normalized_provider, None)
    if llm_config is not None:
        current_value = str(getattr(llm_config, "api_key", "") or "").strip()

    return bool(current_value or get_stored_api_key(normalized_provider))


def hydrate_settings_api_keys(settings: Any) -> Any:
    """Populate missing provider API keys from the secure store."""
    llm = getattr(settings, "llm", None)
    if llm is None:
        return settings

    for provider in ("openai", "anthropic"):
        llm_config = getattr(llm, provider, None)
        if llm_config is None:
            continue
        if str(getattr(llm_config, "api_key", "") or "").strip():
            continue

        stored_value = get_stored_api_key(provider)
        if stored_value:
            setattr(llm_config, "api_key", stored_value)

    return settings
