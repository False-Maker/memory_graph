"""
浏览器插件采集器
处理来自浏览器扩展的消息
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from src.core.collectors.base import (
    BaseCollector, 
    CollectorType, 
    CollectorStatus,
    CollectedConversation,
    CollectedMessage
)

logger = logging.getLogger(__name__)


class BrowserMessage(BaseModel):
    """浏览器插件消息模型"""
    source: str  # chatgpt | claude | gemini | custom
    platform: str  # web | extension
    messages: List[Dict[str, Any]]
    metadata: Dict[str, Any] = {}


class BrowserCollector(BaseCollector):
    """
    浏览器插件采集器
    处理来自浏览器扩展的消息
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.backend_url = self.config.get("backend_url", "http://localhost:8000")
        self.auto_capture = self.config.get("auto_capture", True)
    
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.BROWSER
    
    async def start(self) -> bool:
        """启动浏览器采集器"""
        self._running = True
        self.status = CollectorStatus.RUNNING
        logger.info(f"{self.name} started")
        return True
    
    async def stop(self) -> bool:
        """停止浏览器采集器"""
        self._running = False
        self.status = CollectorStatus.IDLE
        logger.info(f"{self.name} stopped")
        return True
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self._running
    
    async def capture_message(self, message: BrowserMessage) -> Dict[str, Any]:
        """
        接收并处理浏览器插件发来的消息
        """
        try:
            # 1. 转换为统一对话格式
            conversation = self._normalize(message)
            
            # 2. 放入队列触发处理
            await self.put(conversation)
            
            logger.info(f"Captured browser message from {message.source}")
            return {
                "status": "success",
                "conversation_id": conversation.source_id
            }
            
        except Exception as e:
            logger.error(f"Error capturing browser message: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _normalize(self, message: BrowserMessage) -> CollectedConversation:
        """将浏览器消息转换为统一格式"""
        
        # 构建消息列表
        collected_messages = []
        for i, msg in enumerate(message.messages):
            role = msg.get("role", "user")
            content = msg.get("content", msg.get("text", ""))
            timestamp = msg.get("timestamp")
            
            if timestamp:
                try:
                    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except:
                    ts = datetime.now()
            else:
                ts = datetime.now()
            
            collected_messages.append(CollectedMessage(
                source=CollectorType.BROWSER,
                source_id=f"{message.source}_{i}",
                content=str(content),
                role=role,
                timestamp=ts,
                metadata={
                    "platform": message.platform,
                    "original_source": message.source,
                    "message_index": i
                }
            ))
        
        # 生成唯一ID
        source_id = f"browser_{message.source}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return CollectedConversation(
            source=CollectorType.BROWSER,
            source_id=source_id,
            messages=collected_messages,
            metadata={
                "source": message.source,
                "platform": message.platform,
                **message.metadata
            }
        )


# 全局实例
_browser_collector_instance: Optional[BrowserCollector] = None


def get_browser_collector(config: Optional[Dict[str, Any]] = None) -> BrowserCollector:
    """获取浏览器采集器单例"""
    global _browser_collector_instance
    if _browser_collector_instance is None:
        _browser_collector_instance = BrowserCollector(config)
    return _browser_collector_instance
