"""
配置管理模块
负责加载和管理系统配置
"""

import os
import re
from pathlib import Path
from typing import Optional, Any, Dict
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from src.core.secret_store import hydrate_settings_api_keys


SUPPORTED_LLM_PROVIDERS = {"openai", "anthropic", "ollama"}
SUPPORTED_EMBEDDING_PROVIDER_PREFERENCES = {
    "local_first",
    "remote_first",
    "local_only",
    "remote_only",
}
SUPPORTED_VECTOR_STORE_TYPES = {"faiss"}
CONFIG_PATH_ENV = "MEMORY_GRAPH_SETTINGS_PATH"


# ============================================
# 配置模型定义
# ============================================


class OpenAIConfig(BaseModel):
    """OpenAI 配置"""

    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"


class AnthropicConfig(BaseModel):
    """Anthropic (Claude) 配置"""

    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    base_url: str = "https://api.anthropic.com"


class OllamaConfig(BaseModel):
    """Ollama 本地模型配置"""

    url: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"


class LLMConfig(BaseModel):
    """LLM 配置"""

    provider: str = "openai"  # openai | anthropic | ollama
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value):
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        return normalized or "openai"


class EmbeddingConfig(BaseModel):
    """Embedding 向量配置"""

    model: str = "Qwen/Qwen3-Embedding-0.6B"
    dimensions: int = 1024
    model_path: Optional[str] = None
    provider_preference: str = "local_first"  # local_first | remote_first | local_only | remote_only
    cloud_model: str = "text-embedding-3-small"
    cloud_dimensions: int = 1536
    cloud_api_key: str = ""
    cloud_base_url: str = "https://api.openai.com/v1"

    @field_validator("provider_preference", mode="before")
    @classmethod
    def normalize_provider_preference(cls, value):
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        return normalized or "local_first"


class CommunityDetectionConfig(BaseModel):
    """Community detection configuration"""

    enabled: bool = True
    algorithm: str = "leiden"  # leiden | louvain
    resolution: float = 1.0  # Community granularity
    max_levels: int = 5  # Max hierarchy depth
    min_community_size: int = 5  # Minimum entities per community


class ChromaConfig(BaseModel):
    """历史兼容配置，用于读取旧的 chroma 字段。"""

    persist_directory: str = "./data/faiss"


class FAISSConfig(BaseModel):
    """FAISS 向量数据库配置"""

    persist_directory: str = "./data/faiss"


class VectorConfig(BaseModel):
    """向量数据库配置"""

    type: str = "faiss"
    faiss: FAISSConfig = Field(default_factory=FAISSConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)


class DatabaseConfig(BaseModel):
    """数据库配置"""

    vector: VectorConfig = Field(default_factory=VectorConfig)


class StorageConfig(BaseModel):
    """存储配置"""

    data_dir: str = "./data"
    models_dir: str = "./models"


class AppConfig(BaseModel):
    """应用配置"""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    environment: str = "development"
    api_auth_enabled: bool = True
    api_token: str = Field(
        default_factory=lambda: os.getenv("MEMORY_GRAPH_API_TOKEN", "").strip()
    )
    docs_enabled: bool = False
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_file_roots: list[str] = Field(default_factory=lambda: ["./data/imports"])
    cors: Dict[str, Any] = Field(
        default_factory=lambda: {
            "allow_origins": [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:4173",
                "http://127.0.0.1:4173",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
            "allow_credentials": True,
        }
    )

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        return normalized or "development"

    @field_validator("api_token", mode="before")
    @classmethod
    def read_api_token_from_env(cls, value):
        if isinstance(value, str) and value.strip():
            return value.strip()
        return os.getenv("MEMORY_GRAPH_API_TOKEN", "").strip()


class CacheConfig(BaseModel):
    """缓存配置"""

    enabled: bool = True
    ttl: int = 3600


class AdvancedConfig(BaseModel):
    """高级配置"""

    extraction_batch_size: int = 10
    top_k: int = 5
    community_level: int = 2
    cache: CacheConfig = Field(default_factory=CacheConfig)
    community_detection: CommunityDetectionConfig = Field(
        default_factory=CommunityDetectionConfig
    )


class MemoryLayerIdentityConfig(BaseModel):
    """Identity-layer configuration."""

    profile_text: str = ""


class MemoryLayerBudgetConfig(BaseModel):
    """Token budget for one memory layer."""

    max_tokens: int


class MemoryLayerL1Config(MemoryLayerBudgetConfig):
    """Additional knobs for the essential layer."""

    max_tokens: int = 700
    max_entities: int = 12
    max_communities: int = 4
    max_pinned_memories: int = 6


class MemoryLayerL0Config(MemoryLayerBudgetConfig):
    """Identity layer budget."""

    max_tokens: int = 120


class MemoryLayerL2Config(MemoryLayerBudgetConfig):
    """On-demand layer budget."""

    max_tokens: int = 400
    default_top_k: int = 5


class MemoryLayerL3Config(BaseModel):
    """Deep-search layer configuration."""

    enabled: bool = True
    max_tokens: int = 1200
    default_strategy: str = "hybrid"


class MemoryLayersConfig(BaseModel):
    """Memory layer configuration."""

    enabled: bool = True
    default_layer: str = "auto"
    identity: MemoryLayerIdentityConfig = Field(default_factory=MemoryLayerIdentityConfig)
    l0: MemoryLayerL0Config = Field(default_factory=MemoryLayerL0Config)
    l1: MemoryLayerL1Config = Field(default_factory=MemoryLayerL1Config)
    l2: MemoryLayerL2Config = Field(default_factory=MemoryLayerL2Config)
    l3: MemoryLayerL3Config = Field(default_factory=MemoryLayerL3Config)

    @field_validator("default_layer", mode="before")
    @classmethod
    def normalize_default_layer(cls, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        return normalized or "auto"


# ============================================
# 采集器配置
# ============================================


class CursorCollectorConfig(BaseModel):
    """Cursor 采集器配置"""

    enabled: bool = True
    cursor_path: Optional[str] = None
    auto_scan_interval: int = 300  # 5分钟
    transcript_dir: Optional[str] = None
    watch_projects: list = Field(default_factory=list)


class FileWatcherConfig(BaseModel):
    """文件监控器配置"""

    enabled: bool = True
    watch_paths: list = Field(default_factory=lambda: ["~/notes", "~/documents"])
    supported_extensions: list = Field(
        default_factory=lambda: [".md", ".txt", ".json", ".yaml", ".yml", ".jsonl"]
    )
    include_patterns: list = Field(default_factory=list)
    ignore_patterns: list = Field(
        default_factory=lambda: [
            "node_modules/**",
            ".git/**",
            "__pycache__/**",
            "*.pyc",
            ".cursor/**",
            ".vscode/**",
        ]
    )
    debounce_seconds: float = 2.0
    recursive: bool = True
    auto_import: bool = True
    scan_existing_on_start: bool = False


class WebSocketConfig(BaseModel):
    """WebSocket 配置"""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


class BrowserCollectorConfig(BaseModel):
    """浏览器插件配置"""

    enabled: bool = True
    backend_url: str = "http://localhost:8000"
    auto_capture: bool = True


class WindsurfCollectorConfig(BaseModel):
    """Windsurf collector configuration."""

    enabled: bool = True
    data_dir: Optional[str] = None
    auto_scan_interval: int = 300
    watch_projects: list[str] = Field(default_factory=list)


class ClaudeCodeCollectorConfig(BaseModel):
    """Claude Code collector configuration."""

    enabled: bool = True
    data_dir: Optional[str] = None
    auto_scan_interval: int = 60
    project_dirs: list[str] = Field(default_factory=list)
    watch_terminal: bool = False


class AiderCollectorConfig(BaseModel):
    """Aider collector configuration."""

    enabled: bool = True
    auto_scan_interval: int = 60
    project_dirs: list[str] = Field(default_factory=list)


class ClineCollectorConfig(BaseModel):
    """Cline collector configuration."""

    enabled: bool = True
    extension_path: Optional[str] = None
    auto_scan_interval: int = 300
    project_dirs: list[str] = Field(default_factory=list)


class OpenCodeCollectorConfig(BaseModel):
    """OpenCode collector configuration."""

    enabled: bool = True
    data_dir: Optional[str] = None
    auto_scan_interval: int = 300
    project_dirs: list[str] = Field(default_factory=list)
    use_acp: bool = True


class AntigravityCollectorConfig(BaseModel):
    """Antigravity collector configuration."""

    enabled: bool = True
    data_dir: Optional[str] = None
    auto_scan_interval: int = 300
    project_dirs: list[str] = Field(default_factory=list)


class TraceCollectorConfig(BaseModel):
    """Trace collector configuration."""

    enabled: bool = True
    data_dir: Optional[str] = None
    auto_scan_interval: int = 300
    project_dirs: list[str] = Field(default_factory=list)


class AugmentCollectorConfig(BaseModel):
    """Augment collector configuration."""

    enabled: bool = True
    data_dir: Optional[str] = None
    auto_scan_interval: int = 300
    project_dirs: list[str] = Field(default_factory=list)


class CollectorsConfig(BaseModel):
    """采集器总配置"""

    cursor: CursorCollectorConfig = Field(default_factory=CursorCollectorConfig)
    file_watcher: FileWatcherConfig = Field(default_factory=FileWatcherConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    browser: BrowserCollectorConfig = Field(default_factory=BrowserCollectorConfig)
    windsurf: WindsurfCollectorConfig = Field(default_factory=WindsurfCollectorConfig)
    claude_code: ClaudeCodeCollectorConfig = Field(default_factory=ClaudeCodeCollectorConfig)
    aider: AiderCollectorConfig = Field(default_factory=AiderCollectorConfig)
    cline: ClineCollectorConfig = Field(default_factory=ClineCollectorConfig)
    opencode: OpenCodeCollectorConfig = Field(default_factory=OpenCodeCollectorConfig)
    antigravity: AntigravityCollectorConfig = Field(default_factory=AntigravityCollectorConfig)
    trace: TraceCollectorConfig = Field(default_factory=TraceCollectorConfig)
    augment: AugmentCollectorConfig = Field(default_factory=AugmentCollectorConfig)


class Settings(BaseSettings):
    """
    主配置类
    支持从 YAML 文件和环境变量加载配置
    """

    # 配置版本
    version: str = "1.0.0"

    # 核心配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    memory_layers: MemoryLayersConfig = Field(default_factory=MemoryLayersConfig)
    collectors: CollectorsConfig = Field(default_factory=CollectorsConfig)

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


def validate_settings(settings: Settings) -> Settings:
    """Validate startup-critical configuration values."""
    provider = settings.llm.provider
    if provider not in SUPPORTED_LLM_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
        raise ValueError(f"Unsupported llm.provider '{provider}'. Supported values: {supported}")

    provider_preference = settings.embedding.provider_preference
    if provider_preference not in SUPPORTED_EMBEDDING_PROVIDER_PREFERENCES:
        supported = ", ".join(sorted(SUPPORTED_EMBEDDING_PROVIDER_PREFERENCES))
        raise ValueError(
            "Unsupported embedding.provider_preference "
            f"'{provider_preference}'. Supported values: {supported}"
        )

    vector_type = settings.database.vector.type.strip().lower()
    if vector_type not in SUPPORTED_VECTOR_STORE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_VECTOR_STORE_TYPES))
        raise ValueError(
            "Unsupported database.vector.type "
            f"'{settings.database.vector.type}'. Supported values: {supported}"
        )

    if settings.embedding.dimensions <= 0:
        raise ValueError("embedding.dimensions must be a positive integer")

    if settings.embedding.cloud_dimensions <= 0:
        raise ValueError("embedding.cloud_dimensions must be a positive integer")

    if provider == "openai":
        if not settings.llm.openai.base_url.strip():
            raise ValueError("llm.openai.base_url must not be empty when llm.provider=openai")
        if not settings.llm.openai.model.strip():
            raise ValueError("llm.openai.model must not be empty when llm.provider=openai")
    elif provider == "anthropic":
        if not settings.llm.anthropic.base_url.strip():
            raise ValueError("llm.anthropic.base_url must not be empty when llm.provider=anthropic")
        if not settings.llm.anthropic.model.strip():
            raise ValueError("llm.anthropic.model must not be empty when llm.provider=anthropic")
    elif provider == "ollama":
        if not settings.llm.ollama.url.strip():
            raise ValueError("llm.ollama.url must not be empty when llm.provider=ollama")
        if not settings.llm.ollama.model.strip():
            raise ValueError("llm.ollama.model must not be empty when llm.provider=ollama")

    if settings.embedding.provider_preference in {"remote_first", "remote_only"}:
        if not settings.embedding.cloud_model.strip():
            raise ValueError(
                "embedding.cloud_model must not be empty when embedding.provider_preference "
                "prefers remote embeddings"
            )
        if not settings.embedding.cloud_base_url.strip():
            raise ValueError(
                "embedding.cloud_base_url must not be empty when embedding.provider_preference "
                "prefers remote embeddings"
            )

    if settings.app.max_upload_bytes <= 0:
        raise ValueError("app.max_upload_bytes must be a positive integer")

    if settings.app.api_auth_enabled and not settings.app.api_token:
        raise ValueError(
            "app.api_token must be configured when app.api_auth_enabled=true "
            "(or set MEMORY_GRAPH_API_TOKEN)"
        )

    allow_origins = settings.app.cors.get("allow_origins", [])
    if settings.app.environment == "production" and "*" in allow_origins:
        raise ValueError("app.cors.allow_origins must not contain '*' in production")

    return settings


# ============================================
# 配置加载器
# ============================================


def get_config_path(require_exists: bool = False) -> Path:
    """获取配置文件路径。"""
    configured_path = str(os.getenv(CONFIG_PATH_ENV, "") or "").strip()
    if configured_path:
        explicit_path = Path(configured_path).expanduser()
        if explicit_path.exists():
            return explicit_path
        if require_exists:
            raise FileNotFoundError(
                f"Config file from {CONFIG_PATH_ENV} not found: {explicit_path}"
            )
        return explicit_path

    possible_paths = [
        Path("config/settings.yaml"),
        Path("config/settings.local.yaml"),
        Path(__file__).parent.parent.parent / "config" / "settings.yaml",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    if require_exists:
        searched = ", ".join(str(path) for path in possible_paths)
        raise FileNotFoundError(f"Config file not found. Looked in: {searched}")

    return possible_paths[0]


def preload_env_file(dotenv_path: Path) -> None:
    """Load .env pairs into os.environ before resolving ${VAR} in YAML."""
    if not dotenv_path.exists():
        return

    with open(dotenv_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[len("export "):].lstrip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue

            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]

            os.environ[key] = value


def resolve_env_vars(value: Any) -> Any:
    """
    解析环境变量引用
    支持格式: ${ENV_VAR_NAME} 或 ${ENV_VAR_NAME:default_value}
    """
    if not isinstance(value, str):
        return value

    pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

    def replace(match):
        env_var = match.group(1)
        default = match.group(2)
        return os.environ.get(env_var, default if default is not None else "")

    return re.sub(pattern, replace, value)


def process_config_dict(config_dict: Dict) -> Dict:
    """递归处理配置字典，解析环境变量"""
    result = {}
    for key, value in config_dict.items():
        if isinstance(value, dict):
            result[key] = process_config_dict(value)
        else:
            result[key] = resolve_env_vars(value)
    return result


def normalize_config_layout(config_dict: Dict) -> Dict:
    """Promote supported legacy config shapes into the current runtime layout."""
    if not isinstance(config_dict, dict):
        return {}

    normalized = dict(config_dict)
    legacy_community_detection = normalized.get("community_detection")
    if isinstance(legacy_community_detection, dict):
        advanced = normalized.get("advanced")
        if not isinstance(advanced, dict):
            advanced = {}
            normalized["advanced"] = advanced

        if not isinstance(advanced.get("community_detection"), dict):
            advanced["community_detection"] = dict(legacy_community_detection)

    return normalized


def load_yaml_config(config_path: Path) -> Dict:
    """加载 YAML 配置文件"""
    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        return {}

    return normalize_config_layout(process_config_dict(config_dict))


def load_raw_yaml_config(config_path: Path) -> Dict:
    """加载原始 YAML 配置文件，不解析环境变量。"""
    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    if not isinstance(config_dict, dict):
        return {}

    return config_dict


def save_yaml_config(config_path: Path, config_dict: Dict) -> None:
    """保存 YAML 配置文件。"""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            config_dict,
            f,
            allow_unicode=True,
            sort_keys=False,
        )


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例
    加载顺序: settings.yaml -> 环境变量 -> 默认值
    """
    preload_env_file(Path(".env"))
    preload_env_file(Path(__file__).parent.parent.parent / ".env")
    config_path = get_config_path(require_exists=bool(str(os.getenv(CONFIG_PATH_ENV, "") or "").strip()))
    yaml_config = load_yaml_config(config_path)

    # 合并配置
    settings = hydrate_settings_api_keys(Settings(**yaml_config))
    return validate_settings(settings)


def reload_settings() -> Settings:
    """重新加载配置"""
    get_settings.cache_clear()
    return get_settings()
