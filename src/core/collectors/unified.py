"""
统一采集器
整合所有数据采集通道，统一处理流程
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

from src.core.collectors.base import (
    BaseCollector,
    CollectorType,
    CollectorStatus,
    CollectedConversation,
    CollectedMessage,
    CollectorRegistry,
    get_collector_support_tier,
)
from src.core.collectors.file_watcher import FileWatcher
from src.core.collectors.websocket_collector import WebSocketCollector
from src.core.collectors.cursor_collector import CursorCollector
from src.core.collectors.browser_collector import BrowserCollector

# AI IDE 采集器
from src.core.collectors.windsurf_collector import WindsurfCollector
from src.core.collectors.aider_collector import AiderCollector
from src.core.collectors.claude_code_collector import ClaudeCodeCollector
from src.core.collectors.cline_collector import ClineCollector
from src.core.collectors.opencode_collector import OpenCodeCollector
from src.core.collectors.antigravity_collector import AntigravityCollector
from src.core.collectors.trace_collector import TraceCollector
from src.core.collectors.augment_collector import AugmentCollector

logger = logging.getLogger(__name__)


class UnifiedCollector:
    """
    统一采集器
    整合所有数据采集通道，统一处理流程
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._collectors: Dict[CollectorType, BaseCollector] = {}
        self._registry = CollectorRegistry()
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._handlers: List[Callable] = []
        
        # 处理统计
        self.stats = {
            "total_processed": 0,
            "by_source": {},
            "last_processed": None
        }
    
    @property
    def file_watcher(self) -> Optional[FileWatcher]:
        return self._collectors.get(CollectorType.FILE_WATCHER)
    
    @property
    def websocket(self) -> Optional[WebSocketCollector]:
        return self._collectors.get(CollectorType.WEBSOCKET)
    
    @property
    def cursor(self) -> Optional[CursorCollector]:
        return self._collectors.get(CollectorType.CURSOR)
    
    @property
    def browser(self) -> Optional[BrowserCollector]:
        return self._collectors.get(CollectorType.BROWSER)
    
    def register_collector(self, collector: BaseCollector):
        """注册采集器"""
        self._collectors[collector.collector_type] = collector
        self._registry.register(collector)
        
        # 添加处理器用于将数据放入统一队列
        async def queue_handler(conversation: CollectedConversation):
            await self._message_queue.put(conversation)
        
        collector.add_handler(queue_handler)
        logger.info(f"Registered {collector.name} to UnifiedCollector")
    
    def get_collector(self, collector_type: CollectorType) -> Optional[BaseCollector]:
        """获取指定类型的采集器"""
        return self._collectors.get(collector_type)
    
    def get_all_collectors(self) -> Dict[CollectorType, BaseCollector]:
        """获取所有已注册的采集器"""
        return self._collectors.copy()
    
    async def start(self, enabled_types: Optional[List[CollectorType]] = None) -> Dict[str, bool]:
        """
        启动所有启用的采集器
        """
        if self._running:
            logger.warning("UnifiedCollector is already running")
            return {}
        
        self._running = True
        results = {}
        
        # 确定要启动的采集器
        if enabled_types is None:
            enabled_types = [
                CollectorType.FILE_WATCHER,
                CollectorType.CURSOR,
                CollectorType.WEBSOCKET,
                CollectorType.BROWSER
            ]
        
        # 根据配置创建和注册采集器
        collectors_config = self.config.get("collectors", {})
        
        for collector_type in enabled_types:
            type_key = collector_type.value
            type_config = collectors_config.get(type_key, {})
            
            # 检查是否启用
            if not type_config.get("enabled", True):
                logger.info(f"Collector {type_key} is disabled in config")
                continue
            
            try:
                collector = self._create_collector(collector_type, type_config)
                if collector:
                    self.register_collector(collector)
                    success = await collector.start()
                    results[type_key] = success
                    if success:
                        logger.info(f"Started collector: {type_key}")
            except Exception as e:
                logger.error(f"Failed to create/start collector {type_key}: {e}")
                results[type_key] = False
        
        # 启动处理循环
        if results:
            self._processing_task = asyncio.create_task(self._process_loop())
        
        return results
    
    async def stop(self) -> Dict[str, bool]:
        """
        停止所有采集器
        """
        if not self._running:
            return {}
        
        self._running = False
        results = {}
        
        # 停止处理循环
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
        
        # 停止所有采集器
        for collector_type, collector in self._collectors.items():
            try:
                results[collector_type.value] = await collector.stop()
            except Exception as e:
                logger.error(f"Error stopping {collector_type.value}: {e}")
                results[collector_type.value] = False
        
        return results
    
    def _create_collector(
        self,
        collector_type: CollectorType,
        config: Dict[str, Any]
    ) -> Optional[BaseCollector]:
        """根据类型创建采集器"""

        if collector_type == CollectorType.FILE_WATCHER:
            return FileWatcher(config)
        elif collector_type == CollectorType.CURSOR:
            return CursorCollector(config)
        elif collector_type == CollectorType.WEBSOCKET:
            return WebSocketCollector(config)
        elif collector_type == CollectorType.BROWSER:
            return BrowserCollector(config)

        # AI IDE 采集器
        elif collector_type == CollectorType.WINDSURF:
            return WindsurfCollector(config)
        elif collector_type == CollectorType.AIDER:
            return AiderCollector(config)
        elif collector_type == CollectorType.CLAUDE_CODE:
            return ClaudeCodeCollector(config)
        elif collector_type == CollectorType.CLINE:
            return ClineCollector(config)
        elif collector_type == CollectorType.OPENCODE:
            return OpenCodeCollector(config)
        elif collector_type == CollectorType.ANTIGRAVITY:
            return AntigravityCollector(config)
        elif collector_type == CollectorType.TRACE:
            return TraceCollector(config)
        elif collector_type == CollectorType.AUGMENT:
            return AugmentCollector(config)

        return None
    
    async def import_message(self, source: str, data: dict) -> Dict[str, Any]:
        """
        导入单条消息（手动导入）
        """
        # 根据来源类型分发
        collector_type = self._get_collector_type(source)
        
        if collector_type == CollectorType.BROWSER:
            from src.core.collectors.browser_collector import BrowserMessage
            browser_msg = BrowserMessage(**data)
            collector = self.browser
            if collector:
                return await collector.capture_message(browser_msg)
        
        return {"status": "error", "message": f"Unknown source: {source}"}
    
    def _get_collector_type(self, source: str) -> CollectorType:
        """根据来源字符串获取采集器类型"""
        source_map = {
            "cursor": CollectorType.CURSOR,
            "file": CollectorType.FILE_WATCHER,
            "file_watcher": CollectorType.FILE_WATCHER,
            "websocket": CollectorType.WEBSOCKET,
            "ws": CollectorType.WEBSOCKET,
            "browser": CollectorType.BROWSER,
            "chatgpt": CollectorType.BROWSER,
            "claude": CollectorType.BROWSER,
            "gemini": CollectorType.BROWSER
        }
        return source_map.get(source.lower(), CollectorType.BROWSER)
    
    async def _process_loop(self):
        """处理队列循环"""
        while self._running:
            try:
                conversation = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                await self._process_conversation(conversation)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
    
    async def _process_conversation(self, conversation: CollectedConversation):
        """
        处理收集到的对话
        """
        try:
            source = conversation.source.value
            
            # 更新统计
            self.stats["total_processed"] += 1
            self.stats["by_source"][source] = self.stats["by_source"].get(source, 0) + 1
            self.stats["last_processed"] = datetime.now().isoformat()
            
            # 标记为已处理
            conversation.processed = True
            
            # 触发自定义处理器
            for handler in self._handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(conversation)
                    else:
                        handler(conversation)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
            
            logger.info(f"Processed conversation from {source}: {conversation.source_id}")
            
        except Exception as e:
            logger.error(f"Error processing conversation: {e}")
    
    def add_handler(self, handler: Callable):
        """添加处理回调"""
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable):
        """移除处理回调"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def get_status(self) -> Dict[str, Any]:
        """获取统一采集器状态"""
        collectors_status = []
        for ctype, collector in self._collectors.items():
            collectors_status.append({
                "type": ctype.value,
                "name": collector.name,
                "status": collector.status.value,
                "support_tier": get_collector_support_tier(ctype).value,
                "running": collector._running
            })
        
        return {
            "running": self._running,
            "collectors": collectors_status,
            "queue_size": self._message_queue.qsize(),
            "handlers_count": len(self._handlers),
            "stats": self.stats
        }
    
    def get_collector_status(self, collector_type: CollectorType) -> Optional[Dict[str, Any]]:
        """获取指定采集器状态"""
        collector = self._collectors.get(collector_type)
        if collector:
            return collector.get_status()
        return None


# 全局实例
_unified_collector_instance: Optional[UnifiedCollector] = None


def get_unified_collector(config: Optional[Dict[str, Any]] = None) -> UnifiedCollector:
    """获取统一采集器单例"""
    global _unified_collector_instance
    if _unified_collector_instance is None:
        _unified_collector_instance = UnifiedCollector(config)
    return _unified_collector_instance
