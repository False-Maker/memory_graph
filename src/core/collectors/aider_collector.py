"""
Aider 对话采集器
Aider 是命令行工具，对话存储在 .aider.chat.history 文件中
"""
import asyncio
import logging
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.collectors.base import (
    BaseCollector,
    CollectorType,
    CollectorStatus,
    CollectedConversation,
    CollectedMessage
)

logger = logging.getLogger(__name__)


class AiderCollector(BaseCollector):
    """
    Aider 采集器
    读取 .aider.chat.history 文件
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        self._project_dirs = self.config.get("project_dirs", [])
        self._auto_scan_interval = self.config.get("auto_scan_interval", 60)
        self._last_cursor: Optional[str] = None
        self._scan_task: Optional[asyncio.Task] = None
        self._running = False
        self._processed_files: set = set()

    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.AIDER

    def _find_history_files(self) -> List[str]:
        """查找所有 Aider 历史文件"""
        history_files = []

        # 扫描配置的项目目录
        for project_dir in self._project_dirs:
            if os.path.isdir(project_dir):
                history_file = os.path.join(project_dir, ".aider.chat.history")
                if os.path.exists(history_file):
                    history_files.append(history_file)

        return history_files

    async def start(self) -> bool:
        """启动 Aider 采集器"""
        if self._running:
            return True

        self._running = True
        self.status = CollectorStatus.RUNNING

        if self._auto_scan_interval > 0:
            self._scan_task = asyncio.create_task(self._scan_loop())

        logger.info(f"{self.name} started")
        return True

    async def stop(self) -> bool:
        """停止 Aider 采集器"""
        if not self._running:
            return True

        self._running = False

        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        self.status = CollectorStatus.IDLE
        return True

    async def health_check(self) -> bool:
        """健康检查"""
        return self._running and len(self._find_history_files()) > 0

    async def _scan_loop(self):
        """定时扫描循环"""
        while self._running:
            try:
                await self._scan_history_files()
                await asyncio.sleep(self._auto_scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(30)

    async def _scan_history_files(self):
        """扫描历史文件"""
        for history_file in self._find_history_files():
            file_id = hashlib.md5(history_file.encode()).hexdigest()
            if file_id not in self._processed_files:
                await self._process_file(history_file)
                self._processed_files.add(file_id)

    async def _process_file(self, file_path: str):
        """处理 Aider 历史文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                return

            # Aider 历史文件是 Markdown 格式
            # 格式: [user]: xxx \n\n [aider]: xxx
            messages = self._parse_markdown_history(content)

            if messages:
                conversation = self._build_conversation(file_path, messages)
                await self.put(conversation)
                logger.info(f"Imported Aider conversation: {file_path}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    def _parse_markdown_history(self, content: str) -> List[Dict]:
        """解析 Markdown 格式的 Aider 历史"""
        messages = []
        current_role = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('[user]:') or line.startswith('> '):
                # 保存之前的消息
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": '\n'.join(current_content)
                    })

                current_role = "user"
                current_content = [line.split(':', 1)[1].strip()]

            elif line.startswith('[aider]:') or line.startswith('< '):
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": '\n'.join(current_content)
                    })

                current_role = "assistant"
                current_content = [line.split(':', 1)[1].strip()]
            else:
                if current_role:
                    current_content.append(line)

        # 保存最后一条消息
        if current_role and current_content:
            messages.append({
                "role": current_role,
                "content": '\n'.join(current_content)
            })

        return messages

    def _build_conversation(self, file_path: str, messages: List[Dict]) -> CollectedConversation:
        """构建对话对象"""
        collected_messages = []

        for i, msg in enumerate(messages):
            collected_messages.append(CollectedMessage(
                source=CollectorType.AIDER,
                source_id=file_path,
                content=msg.get("content", ""),
                role=msg.get("role", "user"),
                timestamp=datetime.now(),
                metadata={
                    "message_index": i,
                    "file_path": file_path,
                    "ide": "aider"
                }
            ))

        return CollectedConversation(
            source=CollectorType.AIDER,
            source_id=file_path,
            messages=collected_messages,
            metadata={
                "file_path": file_path,
                "project": os.path.basename(os.path.dirname(file_path)),
                "ide": "aider"
            }
        )

    async def get_conversations_list(self) -> List[Dict[str, Any]]:
        """获取已处理的对话列表"""
        conversations = []
        for file_id in self._processed_files:
            conversations.append({
                "id": file_id,
                "collector_type": self.collector_type.value
            })
        return conversations


# 全局实例
_aider_collector_instance: Optional[AiderCollector] = None


def get_aider_collector(config: Optional[Dict[str, Any]] = None) -> AiderCollector:
    """获取 Aider 采集器单例"""
    global _aider_collector_instance
    if _aider_collector_instance is None:
        _aider_collector_instance = AiderCollector(config)
    return _aider_collector_instance
