"""
Windsurf IDE 对话采集器
基于 Codeium，核心功能是 Cascade 工作流
"""
import asyncio
import json
import logging
import os
import hashlib
import glob as glob_module
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


class WindsurfConfig:
    """Windsurf 配置"""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        auto_scan_interval: int = 300,
        watch_projects: Optional[List[str]] = None
    ):
        self.data_dir = data_dir or self._find_data_dir()
        self.auto_scan_interval = auto_scan_interval
        self.watch_projects = watch_projects or []

    def _find_data_dir(self) -> str:
        """查找 Windsurf 数据目录"""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", "")
            return os.path.join(base, "Codeium", "Windsurf")
        elif os.name == "posix":
            if "darwin" in os.uname().sysname.lower():
                return os.path.expanduser("~/Library/Application Support/Codeium/Windsurf")
            else:
                return os.path.expanduser(".codeium/windsurf")
        return ".windsurf"


class WindsurfCollector(BaseCollector):
    """
    Windsurf IDE 采集器
    从 Windsurf 的 Cascade 工作流中采集对话
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        self._config = WindsurfConfig(
            data_dir=self.config.get("data_dir"),
            auto_scan_interval=self.config.get("auto_scan_interval", 300),
            watch_projects=self.config.get("watch_projects")
        )

        self._last_cursor: Optional[str] = None
        self._scan_task: Optional[asyncio.Task] = None
        self._running = False
        self._processed_files: set = set()

    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.WINDSURF

    def _find_data_path(self) -> Optional[str]:
        """查找数据存储路径"""
        # 优先检查项目目录
        if self._config.watch_projects:
            for project_dir in self._config.watch_projects:
                project_windsurf = os.path.join(project_dir, ".windsurf")
                if os.path.isdir(project_windsurf):
                    return project_windsurf

        # 检查全局目录
        if os.path.isdir(self._config.data_dir):
            return self._config.data_dir

        return None

    async def start(self) -> bool:
        """启动 Windsurf 采集器"""
        if self._running:
            return True

        try:
            data_path = self._find_data_path()
            if not data_path:
                logger.warning(f"Windsurf data not found at {self._config.data_dir}")
            else:
                logger.info(f"Windsurf data found at: {data_path}")

            self._running = True
            self.status = CollectorStatus.RUNNING

            if self._config.auto_scan_interval > 0:
                self._scan_task = asyncio.create_task(self._scan_loop())

            logger.info(f"{self.name} started")
            return True

        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}")
            self.status = CollectorStatus.ERROR
            return False

    async def stop(self) -> bool:
        """停止 Windsurf 采集器"""
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
        logger.info(f"{self.name} stopped")
        return True

    async def health_check(self) -> bool:
        """健康检查"""
        return self._running and self._find_data_path() is not None

    async def _scan_loop(self):
        """定时扫描循环"""
        while self._running:
            try:
                await self._scan_new_conversations()
                await asyncio.sleep(self._config.auto_scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(60)

    async def _scan_new_conversations(self):
        """扫描新对话"""
        data_path = self._find_data_path()
        if not data_path:
            return

        # Windsurf 可能的数据文件位置
        patterns = [
            "**/conversations/*.jsonl",
            "**/conversations/*.json",
            "**/chat/*.jsonl",
            "**/chat/*.json",
            "**/history/*.jsonl",
            "**/history/*.json",
            "**/cascade/*.json",
            "**/*.jsonl",
            "**/*.chat",
        ]

        for pattern in patterns:
            # 使用 glob_module 进行匹配
            search_path = os.path.join(data_path, pattern.replace("**/", ""))
            for file_path in glob_module.glob(search_path, recursive=True):
                if os.path.isfile(file_path):
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
                logger.info(f"Imported Windsurf conversation: {file_path}")

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
                source=CollectorType.WINDSURF,
                source_id=file_path,
                content=str(content),
                role=role,
                timestamp=timestamp,
                metadata={
                    "message_index": i,
                    "file_path": file_path,
                    "ide": "windsurf"
                }
            ))

        return CollectedConversation(
            source=CollectorType.WINDSURF,
            source_id=file_path,
            messages=collected_messages,
            metadata={
                "file_path": file_path,
                "project": os.path.basename(os.path.dirname(file_path)),
                "ide": "windsurf"
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
_windsurf_collector_instance: Optional[WindsurfCollector] = None


def get_windsurf_collector(config: Optional[Dict[str, Any]] = None) -> WindsurfCollector:
    """获取 Windsurf 采集器单例"""
    global _windsurf_collector_instance
    if _windsurf_collector_instance is None:
        _windsurf_collector_instance = WindsurfCollector(config)
    return _windsurf_collector_instance
