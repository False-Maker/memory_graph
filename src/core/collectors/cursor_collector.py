"""
Cursor IDE 集成采集器
自动捕获 Cursor 与 AI 的对话内容
"""
import asyncio
import logging
import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import hashlib

from src.core.collectors.base import (
    BaseCollector, 
    CollectorType, 
    CollectorStatus,
    CollectedConversation,
    CollectedMessage
)

logger = logging.getLogger(__name__)


class CursorConfig:
    """Cursor 配置"""
    
    def __init__(
        self,
        cursor_path: Optional[str] = None,
        auto_scan_interval: int = 300,  # 5分钟
        transcript_dir: Optional[str] = None,
        watch_projects: Optional[List[str]] = None
    ):
        self.cursor_path = cursor_path or self._find_cursor_path()
        self.auto_scan_interval = auto_scan_interval
        # 支持两种路径：
        # 1. 新版 Cursor: C:\Users\xxx\.cursor\projects\{项目名}\agent-transcripts
        # 2. 旧版/自定义: 用户自定义路径
        self.transcript_dir = transcript_dir
        self.watch_projects = watch_projects or []
    
    def _find_cursor_path(self) -> str:
        """查找 Cursor 数据目录"""
        if os.name == "nt":  # Windows
            # 新版 Cursor 使用 .cursor 目录
            user_home = os.environ.get("USERPROFILE", os.environ.get("HOMEPATH", ""))
            cursor_dot_path = os.path.join(user_home, ".cursor")
            if os.path.isdir(cursor_dot_path):
                return cursor_dot_path
            # 旧版路径
            base = os.environ.get("APPDATA", "")
            return os.path.join(base, "Cursor")
        elif os.name == "posix":
            if "darwin" in os.uname().sysname.lower():  # macOS
                return os.path.expanduser("~/.cursor")
            else:  # Linux
                return os.path.expanduser(".cursor")
        return ".cursor"
    
    def _find_transcript_dirs(self) -> List[str]:
        """查找所有项目的 transcript 目录"""
        dirs = []
        
        # 如果用户指定了自定义路径
        if self.transcript_dir and os.path.isdir(self.transcript_dir):
            dirs.append(self.transcript_dir)
        
        # 查找 .cursor/projects/ 下的所有 agent-transcripts
        if os.name == "nt":
            user_home = os.environ.get("USERPROFILE", os.environ.get("HOMEPATH", ""))
        else:
            user_home = os.path.expanduser("~")
        
        projects_dir = os.path.join(user_home, ".cursor", "projects")
        if os.path.isdir(projects_dir):
            for project_name in os.listdir(projects_dir):
                project_path = os.path.join(projects_dir, project_name)
                if os.path.isdir(project_path):
                    transcript_path = os.path.join(project_path, "agent-transcripts")
                    if os.path.isdir(transcript_path):
                        dirs.append(transcript_path)
                        logger.info(f"Found Cursor transcript: {transcript_path}")
        
        # 扫描用户配置的 watch_projects
        for project_dir in self.watch_projects:
            if os.path.isdir(project_dir):
                # 检查项目目录下的 .cursor/agent-transcripts
                cursor_dir = os.path.join(project_dir, ".cursor", "agent-transcripts")
                if os.path.isdir(cursor_dir) and cursor_dir not in dirs:
                    dirs.append(cursor_dir)
        
        return dirs


class CursorCollector(BaseCollector):
    """
    Cursor IDE 采集器
    从 Cursor 的数据库和文件系统中采集对话
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self._config = CursorConfig(
            cursor_path=self.config.get("cursor_path"),
            auto_scan_interval=self.config.get("auto_scan_interval", 300),
            transcript_dir=self.config.get("transcript_dir"),
            watch_projects=self.config.get("watch_projects")
        )
        
        self._db_path: Optional[str] = None
        self._last_cursor: Optional[str] = None  # 上次同步位置
        self._scan_task: Optional[asyncio.Task] = None
        self._running = False
        self._transcript_dirs: List[str] = []  # 存储所有 transcript 目录
    
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.CURSOR
    
    def _find_cursor_path(self) -> str:
        """查找 Cursor 数据目录"""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", "")
            return os.path.join(base, "Cursor")
        elif os.name == "posix":
            if "darwin" in os.uname().sysname.lower():  # macOS
                return os.path.expanduser("~/Library/Application Support/Cursor")
            else:  # Linux
                return os.path.expanduser(".cursor")
        return ".cursor"
    
    def _find_database(self) -> Optional[str]:
        """查找 Cursor SQLite 数据库"""
        # 尝试多个可能的数据库位置
        possible_paths = [
            os.path.join(self._config.cursor_path, "user-data", "globalStorage", "storage.json"),
            os.path.join(self._config.cursor_path, "Cursor.exe"),  # Windows下的标识
            os.path.join(self._config.cursor_path, "resources", "app", "product.json"),
        ]
        
        # 检查数据目录
        data_dir = os.path.join(self._config.cursor_path, "user-data")
        if os.path.isdir(data_dir):
            # 查找 Default 目录中的数据库
            default_dir = os.path.join(data_dir, "Default")
            if os.path.isdir(default_dir):
                db_path = os.path.join(default_dir, "IndexedDB", "file__0.indexeddb.leveldb")
                if os.path.exists(os.path.dirname(db_path)):
                    return db_path
        
        # 尝试 transcript 目录 (新版本 Cursor 使用 .cursor/projects/)
        if self._config.transcript_dir and os.path.isdir(self._config.transcript_dir):
            logger.info(f"Found transcript directory: {self._config.transcript_dir}")
            return "transcripts"
        
        return None
    
    async def start(self) -> bool:
        """启动 Cursor 采集器"""
        if self._running:
            return True
        
        try:
            # 查找数据库
            self._db_path = self._find_database()
            if not self._db_path:
                logger.warning(f"Could not find Cursor data at {self._config.cursor_path}")
                # 不报错，继续运行，只是没有实时数据
            
            self._running = True
            self.status = CollectorStatus.RUNNING
            
            # 启动定时扫描任务
            if self._config.auto_scan_interval > 0:
                self._scan_task = asyncio.create_task(self._scan_loop())
            
            logger.info(f"{self.name} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}")
            self.status = CollectorStatus.ERROR
            return False
    
    async def stop(self) -> bool:
        """停止 Cursor 采集器"""
        if not self._running:
            return True
        
        try:
            self._running = False
            
            if self._scan_task:
                self._scan_task.cancel()
                try:
                    await self._scan_task
                except asyncio.CancelledError:
                    pass
                self._scan_task = None
            
            self.status = CollectorStatus.IDLE
            logger.info(f"{self.name} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop {self.name}: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not self._running:
            return False
        
        # 检查数据库是否可访问
        if self._db_path and self._db_path != "transcripts":
            return os.path.exists(os.path.dirname(self._db_path) if os.path.dirname else self._db_path)
        
        return True
    
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
                await asyncio.sleep(60)  # 出错后等待一分钟
    
    async def _scan_new_conversations(self):
        """扫描新对话"""
        # 查找所有 transcript 目录
        transcript_dirs = self._config._find_transcript_dirs()
        
        if not transcript_dirs:
            logger.debug("No Cursor transcript directories found")
            return
        
        # 遍历所有 transcript 目录
        for transcript_dir in transcript_dirs:
            if not os.path.isdir(transcript_dir):
                continue
            
            for root, dirs, files in os.walk(transcript_dir):
                for file in files:
                    # 支持 .txt, .jsonl, .json 格式
                    if file.endswith((".txt", ".jsonl", ".json")):
                        file_path = os.path.join(root, file)
                        file_id = hashlib.md5(file_path.encode()).hexdigest()
                        
                        # 检查是否已处理
                        if file_id != self._last_cursor:
                            await self._process_transcript_file(file_path)
                            self._last_cursor = file_id
    
    async def _process_transcript_file(self, file_path: str):
        """处理 transcript 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return
            
            messages = []
            
            # 检测文件格式
            if file_path.endswith('.txt'):
                # Cursor 的 .txt transcript 格式：user: ... assistant: ...
                messages = self._parse_txt_transcript(content)
            else:
                # JSONL 或 JSON 格式
                for line in content.strip().split('\n'):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            messages.append(data)
                        except json.JSONDecodeError:
                            pass
                
                if not messages:
                    try:
                        data = json.loads(content)
                        messages = [data] if isinstance(data, dict) else data
                    except json.JSONDecodeError:
                        messages = [{"role": "user", "content": content}]
            
            if messages:
                conversation = self._build_conversation(file_path, messages)
                await self.put(conversation)
                logger.info(f"Imported Cursor conversation: {file_path}")
                
        except Exception as e:
            logger.error(f"Error processing transcript {file_path}: {e}")
    
    def _parse_txt_transcript(self, content: str) -> List[Dict]:
        """解析 Cursor 的 .txt transcript 格式"""
        messages = []
        current_role = None
        current_content = []
        
        for line in content.split('\n'):
            # 检测角色标识
            if line.startswith('user:') or line.startswith('User:'):
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": '\n'.join(current_content).strip()
                    })
                current_role = "user"
                current_content = [line[5:].strip()]
            elif line.startswith('assistant:') or line.startswith('Assistant:'):
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": '\n'.join(current_content).strip()
                    })
                current_role = "assistant"
                current_content = [line[10:].strip()]
            else:
                if current_role:
                    current_content.append(line)
        
        # 保存最后一条消息
        if current_role and current_content:
            messages.append({
                "role": current_role,
                "content": '\n'.join(current_content).strip()
            })
        
        return messages
    
    def _build_conversation(self, file_path: str, messages: List[Dict]) -> CollectedConversation:
        """从原始消息构建对话对象"""
        collected_messages = []
        
        for i, msg in enumerate(messages):
            # 提取角色和内容
            role = msg.get("role", msg.get("type", "assistant"))
            content = msg.get("content", msg.get("text", ""))
            
            # 处理不同格式
            if isinstance(msg, dict):
                # Cursor 可能使用不同字段
                if "parts" in msg:
                    content = " ".join([p.get("text", "") for p in msg["parts"]])
                if "timestamp" in msg:
                    timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                else:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            collected_messages.append(CollectedMessage(
                source=CollectorType.CURSOR,
                source_id=file_path,
                content=str(content),
                role=role,
                timestamp=timestamp,
                metadata={
                    "message_index": i,
                    "file_path": file_path
                }
            ))
        
        return CollectedConversation(
            source=CollectorType.CURSOR,
            source_id=file_path,
            messages=collected_messages,
            metadata={
                "file_path": file_path,
                "project": os.path.basename(os.path.dirname(file_path)),
                "total_messages": len(collected_messages)
            }
        )
    
    async def import_conversation(self, conversation_id: str) -> Optional[CollectedConversation]:
        """
        手动导入指定对话
        """
        if not self._db_path:
            return None
        
        # 如果使用 transcript 目录，查找对应文件
        if self._db_path == "transcripts" and os.path.isdir(self._config.transcript_dir):
            # 搜索包含 conversation_id 的文件
            for root, dirs, files in os.walk(self._config.transcript_dir):
                for file in files:
                    if conversation_id in file:
                        file_path = os.path.join(root, file)
                        await self._process_transcript_file(file_path)
                        break
        
        return None
    
    async def get_conversations_list(self) -> List[Dict[str, Any]]:
        """
        获取对话列表
        """
        conversations = []
        
        # 使用 _find_transcript_dirs 获取所有 transcript 目录
        transcript_dirs = self._config._find_transcript_dirs()
        if not transcript_dirs:
            return conversations
        
        for transcript_dir in transcript_dirs:
            if not os.path.isdir(transcript_dir):
                continue
            
            for root, dirs, files in os.walk(transcript_dir):
                for file in files:
                    if file.endswith((".txt", ".jsonl", ".json")):
                        file_path = os.path.join(root, file)
                        stat = os.stat(file_path)
                        conversations.append({
                            "id": hashlib.md5(file_path.encode()).hexdigest(),
                            "file_path": file_path,
                            "file_name": file,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "size": stat.st_size
                        })
        
        # 按修改时间排序
        conversations.sort(key=lambda x: x["modified_at"], reverse=True)
        return conversations


# 全局实例
_cursor_collector_instance: Optional[CursorCollector] = None


def get_cursor_collector(config: Optional[Dict[str, Any]] = None) -> CursorCollector:
    """获取 Cursor 采集器单例"""
    global _cursor_collector_instance
    if _cursor_collector_instance is None:
        _cursor_collector_instance = CursorCollector(config)
    return _cursor_collector_instance
