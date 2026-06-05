"""
Antigravity 采集器
Google 官方 AI 编程助手 (VS Code fork)
"""
import asyncio
import logging
import os
import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.collectors.base import (
    BaseCollector,
    CollectorType,
    CollectorStatus,
    CollectedConversation,
    CollectedMessage
)

logger = logging.getLogger(__name__)


class AntigravityConfig:
    """Antigravity 配置"""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        auto_scan_interval: int = 300,
        project_dirs: Optional[List[str]] = None
    ):
        self.data_dir = data_dir or self._find_data_dir()
        self.auto_scan_interval = auto_scan_interval
        self.project_dirs = project_dirs or []

    def _find_data_dir(self) -> str:
        """查找 Antigravity 数据目录"""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", "")
            return os.path.join(base, "Google", "Antigravity")
        elif os.name == "posix":
            if "darwin" in os.uname().sysname.lower():
                return os.path.expanduser("~/Library/Application Support/Google/Antigravity")
            else:
                return os.path.expanduser(".antigravity")
        return ".antigravity"


class AntigravityCollector(BaseCollector):
    """
    Antigravity 采集器
    Google 官方 AI 编程助手，基于 VS Code
    支持多 Agent 并行工作区、Artifacts 工件、本地知识库等
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        self._config = AntigravityConfig(
            data_dir=self.config.get("data_dir"),
            auto_scan_interval=self.config.get("auto_scan_interval", 300),
            project_dirs=self.config.get("project_dirs", [])
        )

        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._processed_files: set = set()

    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.ANTIGRAVITY

    def _find_data_dirs(self) -> List[str]:
        """查找所有 Antigravity 数据目录"""
        data_dirs = []

        # 全局数据目录
        if os.path.isdir(self._config.data_dir):
            data_dirs.append(self._config.data_dir)

        # 项目目录
        for project_dir in self._config.project_dirs:
            if os.path.isdir(project_dir):
                # 检查 .antigravity 目录
                antigravity_dir = os.path.join(project_dir, ".antigravity")
                if os.path.isdir(antigravity_dir):
                    data_dirs.append(antigravity_dir)

        return data_dirs

    async def start(self) -> bool:
        """启动 Antigravity 采集器"""
        if self._running:
            return True

        self._running = True
        self.status = CollectorStatus.RUNNING

        if self._config.auto_scan_interval > 0:
            self._scan_task = asyncio.create_task(self._scan_loop())

        logger.info(f"{self.name} started")
        return True

    async def stop(self) -> bool:
        """停止 Antigravity 采集器"""
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
        return self._running and len(self._find_data_dirs()) > 0

    async def _scan_loop(self):
        """扫描循环"""
        while self._running:
            try:
                await self._scan_data_dirs()
                await asyncio.sleep(self._config.auto_scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(60)

    async def _scan_data_dirs(self):
        """扫描数据目录"""
        for data_dir in self._find_data_dirs():
            # Antigravity 可能的数据文件位置
            patterns = [
                "**/conversations/*.json",
                "**/conversations/*.jsonl",
                "**/chat/*.json",
                "**/history/*.json",
                "**/artifacts/*.json",
                "**/sessions/*.json",
                "**/*.json",
            ]

            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    if file.endswith(('.json', '.jsonl')):
                        file_path = os.path.join(root, file)
                        file_id = hashlib.md5(file_path.encode()).hexdigest()

                        if file_id not in self._processed_files:
                            await self._process_file(file_path)
                            self._processed_files.add(file_id)

    async def _process_file(self, file_path: str):
        """处理对话文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                return

            # 尝试解析 JSONL 或 JSON
            messages = []
            for line in content.strip().split('\n'):
                if line.strip():
                    try:
                        data = json.loads(line)
                        messages.append(data)
                    except json.JSONDecodeError:
                        pass

            if not messages:
                try:
                    messages = json.loads(content)
                    messages = [messages] if isinstance(messages, dict) else messages
                except json.JSONDecodeError:
                    messages = [{"role": "user", "content": content}]

            if messages:
                conversation = self._build_conversation(file_path, messages)
                await self.put(conversation)
                logger.info(f"Imported Antigravity conversation: {file_path}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    def _build_conversation(self, file_path: str, messages: List[Dict]) -> CollectedConversation:
        """构建对话对象"""
        collected_messages = []

        for i, msg in enumerate(messages):
            role = msg.get("role", msg.get("type", "assistant"))
            content = msg.get("content", msg.get("text", ""))

            # 处理不同字段格式
            if "parts" in msg:
                content = " ".join([p.get("text", "") for p in msg["parts"]])

            timestamp = datetime.now()
            if "timestamp" in msg:
                try:
                    timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                except:
                    pass

            collected_messages.append(CollectedMessage(
                source=CollectorType.ANTIGRAVITY,
                source_id=file_path,
                content=str(content),
                role=role,
                timestamp=timestamp,
                metadata={
                    "message_index": i,
                    "file_path": file_path,
                    "ide": "antigravity"
                }
            ))

        return CollectedConversation(
            source=CollectorType.ANTIGRAVITY,
            source_id=file_path,
            messages=collected_messages,
            metadata={
                "file_path": file_path,
                "project": os.path.basename(os.path.dirname(file_path)),
                "ide": "antigravity"
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
_antigravity_collector_instance: Optional[AntigravityCollector] = None


def get_antigravity_collector(config: Optional[Dict[str, Any]] = None) -> AntigravityCollector:
    """获取 Antigravity 采集器单例"""
    global _antigravity_collector_instance
    if _antigravity_collector_instance is None:
        _antigravity_collector_instance = AntigravityCollector(config)
    return _antigravity_collector_instance
