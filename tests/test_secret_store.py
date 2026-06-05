"""Tests for secure secret store runtime modes."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.secret_store import (
    SECRET_STORE_DISABLE_ENV,
    SecretStoreUnavailableError,
    build_secret_store_unavailable_message,
    get_secret_storage_status,
    get_stored_api_key,
    secure_secret_store_available,
    store_api_key,
)


def test_secret_store_can_be_forced_to_environment_only(monkeypatch):
    """Environment override should force environment-only secret behavior."""
    monkeypatch.setenv(SECRET_STORE_DISABLE_ENV, "1")

    keyring_module = MagicMock()
    keyring_module.get_keyring.return_value = MagicMock()

    with patch("src.core.secret_store._load_keyring_module", return_value=keyring_module):
        status = get_secret_storage_status()
        assert secure_secret_store_available() is False
        assert get_stored_api_key("openai") == ""

    assert status["available"] is False
    assert status["storage_type"] == "environment_only"
    assert status["backend"] == f"disabled_by_env:{SECRET_STORE_DISABLE_ENV}"
    assert SECRET_STORE_DISABLE_ENV in status["message"]


def test_store_api_key_rejects_when_secret_store_disabled_by_env(monkeypatch):
    """Forced environment-only mode should reject secure-store writes."""
    monkeypatch.setenv(SECRET_STORE_DISABLE_ENV, "true")

    with pytest.raises(SecretStoreUnavailableError, match=SECRET_STORE_DISABLE_ENV):
        store_api_key("openai", "sk-test")

    assert SECRET_STORE_DISABLE_ENV in build_secret_store_unavailable_message()
