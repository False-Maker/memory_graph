# Collectors 模块
# 数据采集层实现 - 负责从各种数据源收集对话和碎片

from src.core.collectors.base import (
    BaseCollector,
    CollectorType,
    CollectorStatus,
    CollectedConversation,
    CollectedMessage,
    CollectorRegistry
)
from src.core.collectors.file_watcher import FileWatcher
from src.core.collectors.websocket_collector import WebSocketCollector, ConnectionManager
from src.core.collectors.cursor_collector import CursorCollector
from src.core.collectors.browser_collector import BrowserCollector, BrowserMessage

# AI IDE 采集器
from src.core.collectors.windsurf_collector import WindsurfCollector
from src.core.collectors.aider_collector import AiderCollector
from src.core.collectors.claude_code_collector import ClaudeCodeCollector
from src.core.collectors.cline_collector import ClineCollector
from src.core.collectors.opencode_collector import OpenCodeCollector
from src.core.collectors.antigravity_collector import AntigravityCollector
from src.core.collectors.trace_collector import TraceCollector
from src.core.collectors.augment_collector import AugmentCollector

from src.core.collectors.unified import UnifiedCollector, get_unified_collector

__all__ = [
    # Base
    "BaseCollector",
    "CollectorType",
    "CollectorStatus",
    "CollectedConversation",
    "CollectedMessage",
    "CollectorRegistry",
    # Collectors
    "FileWatcher",
    "WebSocketCollector",
    "ConnectionManager",
    "CursorCollector",
    "BrowserCollector",
    "BrowserMessage",
    # AI IDE Collectors
    "WindsurfCollector",
    "AiderCollector",
    "ClaudeCodeCollector",
    "ClineCollector",
    "OpenCodeCollector",
    "AntigravityCollector",
    "TraceCollector",
    "AugmentCollector",
    # Unified
    "UnifiedCollector",
    "get_unified_collector",
]
