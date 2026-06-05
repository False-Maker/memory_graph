"""
WebSocket 实时同步采集器
通过 WebSocket 接收实时对话数据
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from src.core.collectors.base import (
    BaseCollector, 
    CollectorType, 
    CollectorStatus,
    CollectedConversation,
    CollectedMessage
)

logger = logging.getLogger(__name__)


class WSMessageType(str, Enum):
    """WebSocket 消息类型"""
    USER_MESSAGE = "user_message"
    AI_RESPONSE = "ai_response"
    TYPING = "typing"
    SYNC_REQUEST = "sync_request"
    MESSAGE_SYNCED = "message_synced"
    CONVERSATION_END = "conversation_end"
    PING = "ping"
    PONG = "pong"


@dataclass
class WSConversationContext:
    """WebSocket 对话上下文"""
    client_id: str
    conversation_id: str
    messages: List[CollectedMessage] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """
    WebSocket 连接管理器
    管理多个客户端连接
    """
    
    def __init__(self):
        # client_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # conversation_id -> context
        self.conversations: Dict[str, WSConversationContext] = {}
        # websocket -> client_id
        self._ws_to_client: Dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """
        处理新连接
        """
        await websocket.accept()
        
        async with self._lock:
            if client_id not in self.active_connections:
                self.active_connections[client_id] = set()
            self.active_connections[client_id].add(websocket)
            self._ws_to_client[websocket] = client_id
        
        logger.info(f"Client connected: {client_id}")
        return True
    
    async def disconnect(self, websocket: WebSocket):
        """
        处理断开连接
        """
        async with self._lock:
            client_id = self._ws_to_client.pop(websocket, None)
            
            if client_id and client_id in self.active_connections:
                self.active_connections[client_id].discard(websocket)
                if not self.active_connections[client_id]:
                    del self.active_connections[client_id]
                    
                    # 清理对话上下文
                    for conv_id, ctx in list(self.conversations.items()):
                        if ctx.client_id == client_id:
                            del self.conversations[conv_id]
            
            if client_id:
                logger.info(f"Client disconnected: {client_id}")
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """
        向指定客户端发送消息
        """
        async with self._lock:
            connections = self.active_connections.get(client_id, set())
        
        if not connections:
            return False
        
        message_json = json.dumps(message, ensure_ascii=False)
        
        for websocket in connections:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
        
        return True
    
    async def broadcast(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None):
        """
        广播消息给所有客户端
        """
        exclude = exclude or set()
        message_json = json.dumps(message, ensure_ascii=False)
        
        async with self._lock:
            all_connections = []
            for client_id, connections in self.active_connections.items():
                if client_id not in exclude:
                    all_connections.extend(connections)
        
        for websocket in all_connections:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
    
    def get_connected_clients(self) -> List[str]:
        """获取已连接的客户端列表"""
        return list(self.active_connections.keys())
    
    def get_client_count(self) -> int:
        """获取连接客户端数量"""
        return len(self.active_connections)
    
    def get_conversation_context(self, conversation_id: str) -> Optional[WSConversationContext]:
        """获取对话上下文"""
        return self.conversations.get(conversation_id)
    
    def create_conversation(self, client_id: str, conversation_id: str, metadata: Optional[Dict] = None) -> WSConversationContext:
        """创建新的对话上下文"""
        ctx = WSConversationContext(
            client_id=client_id,
            conversation_id=conversation_id,
            metadata=metadata or {}
        )
        self.conversations[conversation_id] = ctx
        return ctx


class WebSocketCollector(BaseCollector):
    """
    WebSocket 实时同步采集器
    通过 WebSocket 接收实时对话数据
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.host = self.config.get("host", "0.0.0.0")
        self.port = self.config.get("port", 8000)
        self._server_task: Optional[asyncio.Task] = None
        self._manager = ConnectionManager()
        self._running = False
        self._conversation_buffer: Dict[str, List[CollectedMessage]] = {}
    
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.WEBSOCKET
    
    @property
    def manager(self) -> ConnectionManager:
        """获取连接管理器"""
        return self._manager
    
    async def start(self) -> bool:
        """启动 WebSocket 服务器"""
        if self._running:
            logger.warning(f"{self.name} is already running")
            return True
        
        try:
            self._running = True
            self.status = CollectorStatus.RUNNING
            
            # 创建 WebSocket 服务器任务
            self._server_task = asyncio.create_task(self._run_server())
            
            logger.info(f"{self.name} started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}")
            self.status = CollectorStatus.ERROR
            self._running = False
            return False
    
    async def stop(self) -> bool:
        """停止 WebSocket 服务器"""
        if not self._running:
            return True
        
        try:
            self._running = False
            
            if self._server_task:
                self._server_task.cancel()
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    pass
                self._server_task = None
            
            self.status = CollectorStatus.IDLE
            logger.info(f"{self.name} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop {self.name}: {e}")
            self.status = CollectorStatus.ERROR
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self._running
    
    async def _run_server(self):
        """运行 WebSocket 服务器（需要外部集成 FastAPI）"""
        # 这个方法通常不会被直接调用
        # WebSocket 服务器通过 FastAPI 路由集成
        while self._running:
            await asyncio.sleep(1)
    
    async def handle_websocket(self, websocket: WebSocket, client_id: str):
        """
        处理 WebSocket 连接
        由 API 层调用
        """
        await self._manager.connect(websocket, client_id)
        
        try:
            while self._running:
                data = await websocket.receive_text()
                await self._handle_message(client_id, data)
                
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
        finally:
            await self._manager.disconnect(websocket)
    
    async def _handle_message(self, client_id: str, raw_message: str):
        """
        处理接收到的消息
        """
        try:
            data = json.loads(raw_message)
            message_type = data.get("type")
            
            if message_type == WSMessageType.USER_MESSAGE.value:
                await self._handle_user_message(client_id, data)
            elif message_type == WSMessageType.AI_RESPONSE.value:
                await self._handle_ai_response(client_id, data)
            elif message_type == WSMessageType.TYPING.value:
                await self._handle_typing(client_id, data)
            elif message_type == WSMessageType.SYNC_REQUEST.value:
                await self._handle_sync_request(client_id, data)
            elif message_type == WSMessageType.CONVERSATION_END.value:
                await self._handle_conversation_end(client_id, data)
            elif message_type == WSMessageType.PING.value:
                await self._manager.send_to_client(client_id, {"type": WSMessageType.PONG.value})
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message from {client_id}")
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
    
    async def _handle_user_message(self, client_id: str, data: Dict[str, Any]):
        """处理用户消息"""
        conversation_id = data.get("conversation_id", client_id)
        content = data.get("content", "")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        
        # 创建或更新对话上下文
        ctx = self._manager.get_conversation_context(conversation_id)
        if not ctx:
            ctx = self._manager.create_conversation(client_id, conversation_id)
        
        # 创建消息
        message = CollectedMessage(
            source=CollectorType.WEBSOCKET,
            source_id=conversation_id,
            content=content,
            role="user",
            timestamp=datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else datetime.now(),
            metadata={
                "client_id": client_id,
                "message_id": data.get("message_id")
            }
        )
        
        # 添加到缓冲区
        if conversation_id not in self._conversation_buffer:
            self._conversation_buffer[conversation_id] = []
        self._conversation_buffer[conversation_id].append(message)
        
        ctx.last_activity = datetime.now()
        
        # 确认消息已接收
        await self._manager.send_to_client(client_id, {
            "type": WSMessageType.MESSAGE_SYNCED.value,
            "conversation_id": conversation_id,
            "message_id": data.get("message_id")
        })
    
    async def _handle_ai_response(self, client_id: str, data: Dict[str, Any]):
        """处理 AI 响应"""
        conversation_id = data.get("conversation_id", client_id)
        content = data.get("content", "")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        
        message = CollectedMessage(
            source=CollectorType.WEBSOCKET,
            source_id=conversation_id,
            content=content,
            role="assistant",
            timestamp=datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else datetime.now(),
            metadata={
                "client_id": client_id,
                "message_id": data.get("message_id"),
                "model": data.get("model"),
                "streaming": data.get("streaming", False)
            }
        )
        
        if conversation_id not in self._conversation_buffer:
            self._conversation_buffer[conversation_id] = []
        self._conversation_buffer[conversation_id].append(message)
        
        ctx = self._manager.get_conversation_context(conversation_id)
        if ctx:
            ctx.last_activity = datetime.now()
    
    async def _handle_typing(self, client_id: str, data: Dict[str, Any]):
        """处理正在输入状态"""
        # 可以广播给其他相关客户端
        conversation_id = data.get("conversation_id")
        if conversation_id:
            await self._manager.broadcast({
                "type": WSMessageType.TYPING.value,
                "client_id": client_id,
                "conversation_id": conversation_id
            }, exclude={client_id})
    
    async def _handle_sync_request(self, client_id: str, data: Dict[str, Any]):
        """处理同步请求"""
        conversation_id = data.get("conversation_id")
        
        if conversation_id and conversation_id in self._conversation_buffer:
            messages = self._conversation_buffer[conversation_id]
            await self._manager.send_to_client(client_id, {
                "type": "sync_response",
                "conversation_id": conversation_id,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat()
                    }
                    for m in messages
                ]
            })
    
    async def _handle_conversation_end(self, client_id: str, data: Dict[str, Any]):
        """处理对话结束"""
        conversation_id = data.get("conversation_id")
        
        if conversation_id and conversation_id in self._conversation_buffer:
            messages = self._conversation_buffer[conversation_id]
            
            if messages:
                # 构建完整对话
                conversation = CollectedConversation(
                    source=CollectorType.WEBSOCKET,
                    source_id=conversation_id,
                    messages=messages,
                    metadata={
                        "client_id": client_id,
                        "ended_at": datetime.now().isoformat(),
                        "total_messages": len(messages)
                    }
                )
                
                # 放入处理队列
                await self.put(conversation)
                logger.info(f"Conversation completed: {conversation_id} ({len(messages)} messages)")
            
            # 清理缓冲区
            del self._conversation_buffer[conversation_id]
    
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """向客户端发送消息"""
        return await self._manager.send_to_client(client_id, message)
    
    async def broadcast_message(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None):
        """广播消息"""
        await self._manager.broadcast(message, exclude)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "connected_clients": self._manager.get_client_count(),
            "active_conversations": len(self._conversation_buffer),
            "total_messages_buffered": sum(len(m) for m in self._conversation_buffer.values())
        }


# 全局实例
_ws_collector_instance: Optional[WebSocketCollector] = None


def get_websocket_collector(config: Optional[Dict[str, Any]] = None) -> WebSocketCollector:
    """获取 WebSocket 采集器单例"""
    global _ws_collector_instance
    if _ws_collector_instance is None:
        _ws_collector_instance = WebSocketCollector(config)
    return _ws_collector_instance
