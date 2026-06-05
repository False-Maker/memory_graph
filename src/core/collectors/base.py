"""
采集器基类模块
定义所有采集器的通用接口和类型
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CollectorType(str, Enum):
    """采集器类型枚举"""
    # 现有
    CURSOR = "cursor"           # Cursor IDE 集成
    FILE_WATCHER = "file_watcher"  # 文件夹监控
    WEBSOCKET = "websocket"     # WebSocket 实时同步
    BROWSER = "browser"         # 浏览器插件

    # AI IDE 采集器
    WINDSURF = "windsurf"       # Codeium Windsurf IDE
    CLAUDE_CODE = "claude_code" # Anthropic Claude Code
    AIDER = "aider"             # Aider 命令行工具
    CLINE = "cline"             # Cline VS Code 扩展
    OPENCODE = "opencode"       # OpenCode ACP 协议
    ANTIGRAVITY = "antigravity" # Google Antigravity
    TRACE = "trace"             # Trace 代码追踪
    AUGMENT = "augment"         # Augment 代码增强


class CollectorSupportTier(str, Enum):
    """产品支持级别。"""

    OFFICIAL = "official"
    EXPERIMENTAL = "experimental"


COLLECTOR_SUPPORT_TIERS: Dict[CollectorType, CollectorSupportTier] = {
    CollectorType.CURSOR: CollectorSupportTier.OFFICIAL,
    CollectorType.FILE_WATCHER: CollectorSupportTier.OFFICIAL,
    CollectorType.WEBSOCKET: CollectorSupportTier.OFFICIAL,
    CollectorType.BROWSER: CollectorSupportTier.OFFICIAL,
    CollectorType.WINDSURF: CollectorSupportTier.OFFICIAL,
    CollectorType.CLAUDE_CODE: CollectorSupportTier.OFFICIAL,
    CollectorType.AIDER: CollectorSupportTier.OFFICIAL,
    CollectorType.CLINE: CollectorSupportTier.EXPERIMENTAL,
    CollectorType.OPENCODE: CollectorSupportTier.EXPERIMENTAL,
    CollectorType.ANTIGRAVITY: CollectorSupportTier.EXPERIMENTAL,
    CollectorType.TRACE: CollectorSupportTier.EXPERIMENTAL,
    CollectorType.AUGMENT: CollectorSupportTier.EXPERIMENTAL,
}


def get_collector_support_tier(collector_type: CollectorType) -> CollectorSupportTier:
    """Return the current product support tier for one collector type."""
    return COLLECTOR_SUPPORT_TIERS.get(collector_type, CollectorSupportTier.EXPERIMENTAL)


def is_public_collector_type(collector_type: CollectorType) -> bool:
    """Return whether a collector type is part of the current public product surface."""
    return get_collector_support_tier(collector_type) == CollectorSupportTier.OFFICIAL


class CollectorStatus(str, Enum):
    """采集器状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class CollectedMessage:
    """收集到的单条消息"""
    source: CollectorType
    source_id: str           # 来源唯一标识
    content: str              # 消息内容
    role: str                # user | assistant
    timestamp: datetime       # 消息时间
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectedConversation:
    """收集到的完整对话"""
    source: CollectorType
    source_id: str           # 来源唯一标识（如文件路径、conversation_id等）
    messages: List[CollectedMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    processed: bool = False


class BaseCollector(ABC):
    """
    采集器基类
    所有采集器需要继承此类并实现抽象方法
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.status = CollectorStatus.IDLE
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._handlers: List[callable] = []
        
    @property
    @abstractmethod
    def collector_type(self) -> CollectorType:
        """返回采集器类型"""
        pass
    
    @property
    def name(self) -> str:
        """返回采集器名称"""
        return self.__class__.__name__
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动采集器
        Returns:
            bool: 启动是否成功
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止采集器
        Returns:
            bool: 停止是否成功
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查
        Returns:
            bool: 采集器是否健康
        """
        pass
    
    def add_handler(self, handler: callable):
        """
        添加消息处理器
        Args:
            handler: 处理CollectedConversation的回调函数
        """
        self._handlers.append(handler)
    
    def remove_handler(self, handler: callable):
        """移除消息处理器"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    async def _notify_handlers(self, conversation: CollectedConversation):
        """通知所有处理器有新数据"""
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(conversation)
                else:
                    handler(conversation)
            except Exception as e:
                logger.error(f"Handler error in {self.name}: {e}")
    
    async def put(self, conversation: CollectedConversation):
        """
        将收集到的对话放入队列
        """
        await self._queue.put(conversation)
        await self._notify_handlers(conversation)
    
    async def get(self, timeout: Optional[float] = None) -> Optional[CollectedConversation]:
        """
        从队列获取对话
        """
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """获取采集器状态"""
        return {
            "type": self.collector_type.value,
            "name": self.name,
            "status": self.status.value,
            "support_tier": get_collector_support_tier(self.collector_type).value,
            "queue_size": self._queue.qsize(),
            "handlers_count": len(self._handlers),
            "running": self._running
        }


class CollectorRegistry:
    """
    采集器注册表
    管理所有采集器实例
    """
    
    _instance = None
    _collectors: Dict[CollectorType, BaseCollector] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, collector: BaseCollector):
        """注册采集器"""
        self._collectors[collector.collector_type] = collector
        logger.info(f"Registered collector: {collector.collector_type.value}")
    
    def unregister(self, collector_type: CollectorType):
        """注销采集器"""
        if collector_type in self._collectors:
            del self._collectors[collector_type]
            logger.info(f"Unregistered collector: {collector_type.value}")
    
    def get(self, collector_type: CollectorType) -> Optional[BaseCollector]:
        """获取指定类型的采集器"""
        return self._collectors.get(collector_type)
    
    def get_all(self) -> Dict[CollectorType, BaseCollector]:
        """获取所有采集器"""
        return self._collectors.copy()
    
    async def start_all(self) -> Dict[CollectorType, bool]:
        """启动所有采集器"""
        results = {}
        for collector in self._collectors.values():
            try:
                results[collector.collector_type] = await collector.start()
            except Exception as e:
                logger.error(f"Failed to start {collector.name}: {e}")
                results[collector.collector_type] = False
        return results
    
    async def stop_all(self) -> Dict[CollectorType, bool]:
        """停止所有采集器"""
        results = {}
        for collector in self._collectors.values():
            try:
                results[collector.collector_type] = await collector.stop()
            except Exception as e:
                logger.error(f"Failed to stop {collector.name}: {e}")
                results[collector.collector_type] = False
        return results
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """获取所有采集器状态"""
        return [c.get_status() for c in self._collectors.values()]


# 全局注册表实例
get_collector_registry = CollectorRegistry
