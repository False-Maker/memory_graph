"""
API Schemas - Config
"""
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SecretStorageStatus(BaseModel):
    """Secret storage behavior visible to the settings contract."""

    available: bool
    storage_type: Literal["system_keyring", "environment_only"]
    backend: Optional[str] = None
    message: str
    fallback_env_vars: list[str] = Field(
        default_factory=lambda: ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    )


class ConfigResponse(BaseModel):
    """Config response"""
    llm_provider: str
    embedding_model: str
    graph_backend: str
    vector_store_type: str
    app_host: str
    app_port: int
    openai_base_url: str
    openai_model: str
    openai_api_key_configured: bool = False
    anthropic_base_url: str
    anthropic_model: str
    anthropic_api_key_configured: bool = False
    ollama_url: str
    ollama_model: str
    secret_storage: SecretStorageStatus


class ConfigUpdate(BaseModel):
    """Config update request"""
    llm_provider: Optional[Literal["openai", "anthropic", "ollama"]] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    anthropic_model: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, value):
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        return normalized or None

    @field_validator(
        "openai_api_key",
        "openai_base_url",
        "openai_model",
        "anthropic_api_key",
        "anthropic_base_url",
        "anthropic_model",
        "ollama_url",
        "ollama_model",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        return normalized or None


class ConnectionTestResponse(BaseModel):
    """Connection test response"""
    success: bool
    providers: Dict[str, bool] = Field(default_factory=dict)
    provider_errors: Dict[str, str] = Field(default_factory=dict)
    graph_store: bool = False
    vector_store: bool = False
    current_error: Optional[str] = None
    error: Optional[str] = None


class ConfigUpdateResponse(BaseModel):
    """Success response for config persistence."""

    success: bool
    message: str


class ConfigActionErrorResponse(BaseModel):
    """Stable error contract for settings actions."""

    success: bool = False
    code: Literal["secure_secret_store_unavailable"]
    message: str
    providers: list[Literal["openai", "anthropic"]] = Field(default_factory=list)
    fallback_env_vars: list[str] = Field(
        default_factory=lambda: ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    )
    secret_storage: SecretStorageStatus
