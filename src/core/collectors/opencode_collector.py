"""
OpenCode 采集器
OpenCode 支持 ACP 协议，多编辑器支持
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


class OpenCodeConfig:
    """OpenCode 配置"""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        auto_scan_interval: int = 300,
        project_dirs: Optional[List[str]] = None,
        use_acp: bool = True
    ):
        self.data_dir = data_dir or self._find_data_dir()
        self.auto_scan_interval = auto_scan_interval
        self.project_dirs = project_dirs or []
        self.use_acp = use_acp

    def _find_data_dir(self) -> str:
        """查找 OpenCode 数据目录"""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", "")
            return os.path.join(base, "OpenCode")
        else:
            return os.path.expanduser("~/.opencode")


class OpenCodeCollector(BaseCollector):
    """
    OpenCode 采集器
    从 OpenCode 项目目录读取对话数据，支持 ACP 协议
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        self._config = OpenCodeConfig(
            data_dir=self.config.get("data_dir"),
            auto_scan_interval=self.config.get("auto_scan_interval", 300),
            project_dirs=self.config.get("project_dirs", []),
            use_acp=self.config.get("use_acp", True)
        )

        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._processed_files: set = set()

    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.OPENCODE

    def _find_data_dirs(self) -> List[str]:
        """查找所有 OpenCode 数据目录"""
        data_dirs = []

        # 全局配置目录
        if os.path.isdir(self._config.data_dir):
            data_dirs.append(self._config.data_dir)

        # 项目目录
        for project_dir in self._config.project_dirs:
            if os.path.isdir(project_dir):
                # 检查 .opencode 目录
                opencode_dir = os.path.join(project_dir, ".opencode")
                if os.path.isdir(opencode_dir):
                    data_dirs.append(opencode_dir)

        return data_dirs

    async def start(self) -> bool:
        """启动 OpenCode 采集器"""
        if self._running:
            return True

        self._running = True
        self.status = CollectorStatus.RUNNING

        if self._config.auto_scan_interval > 0:
            self._scan_task = asyncio.create_task(self._scan_loop())

        logger.info(f"{self.name} started")
        return True

    async def stop(self) -> bool:
        """停止 OpenCode 采集器"""
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
            # OpenCode 可能的数据文件位置
            patterns = [
                "**/conversations/*.json",
                "**/conversations/*.jsonl",
                "**/conversations/*.jsonc",
                "**/chat/*.json",
                "**/history/*.json",
                "**/*.json",
                "**/*.jsonc",
                "**/*.acp",
            ]

            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    if file.endswith(('.json', '.jsonl', '.jsonc', '.acp')):
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

            # 尝试解析 JSONL 或 JSON/JSONC
            messages = []

            # 首先尝试 JSONL 格式
            for line in content.strip().split('\n'):
                if line.strip():
                    try:
                        # 移除 JSONC 注释
                        clean_line = self._remove_json_comments(line)
                        if clean_line.strip():
                            data = json.loads(clean_line)
                            messages.append(data)
                    except json.JSONDecodeError:
                        pass

            if not messages:
                try:
                    # 尝试作为单个 JSON
                    clean_content = self._remove_json_comments(content)
                    messages = json.loads(clean_content)
                    messages = [messages] if isinstance(messages, dict) else messages
                except json.JSONDecodeError:
                    messages = [{"role": "user", "content": content}]

            if messages:
                conversation = self._build_conversation(file_path, messages)
                await self.put(conversation)
                logger.info(f"Imported OpenCode conversation: {file_path}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    def _remove_json_comments(self, content: str) -> str:
        """移除 JSON/JSONC 中的注释"""
        lines = content.split('\n')
        result_lines = []
        for line in lines:
            # 移除 // 注释
            if '//' in line:
                line = line[:line.index('//')]
            result_lines.append(line)
        return '\n'.join(result_lines)

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
                source=CollectorType.OPENCODE,
                source_id=file_path,
                content=str(content),
                role=role,
                timestamp=timestamp,
                metadata={
                    "message_index": i,
                    "file_path": file_path,
                    "ide": "opencode",
                    "protocol": "acp" if self._config.use_acp else "unknown"
                }
            ))

        return CollectedConversation(
            source=CollectorType.OPENCODE,
            source_id=file_path,
            messages=collected_messages,
            metadata={
                "file_path": file_path,
                "project": os.path.basename(os.path.dirname(file_path)),
                "ide": "opencode",
                "protocol": "acp" if self._config.use_acp else "unknown"
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
_opencode_collector_instance: Optional[OpenCodeCollector] = None


def get_opencode_collector(config: Optional[Dict[str, Any]] = None) -> OpenCodeCollector:
    """获取 OpenCode 采集器单例"""
    global _opencode_collector_instance
    if _opencode_collector_instance is None:
        _opencode_collector_instance = OpenCodeCollector(config)
    return _opencode_collector_instance
