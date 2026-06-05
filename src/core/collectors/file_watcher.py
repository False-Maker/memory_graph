"""
文件监控采集器
监控指定目录，新文件自动导入知识库
"""
import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import hashlib

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler, 
    FileCreatedEvent, 
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent
)

from src.core.collectors.base import (
    BaseCollector, 
    CollectorType, 
    CollectorStatus,
    CollectedConversation,
    CollectedMessage
)

logger = logging.getLogger(__name__)


class FileWatchConfig:
    """文件监控配置"""
    
    def __init__(
        self,
        watch_paths: List[str],
        supported_extensions: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0,
        recursive: bool = True,
        auto_import: bool = True,
        scan_existing_on_start: bool = False
    ):
        self.watch_paths = [os.path.expanduser(p) for p in watch_paths]
        self.supported_extensions = supported_extensions or [".md", ".txt", ".json", ".yaml", ".yml", ".jsonl"]
        # include_patterns: 只匹配这些目录/文件（通配符）
        # 例如: ["**/agent-transcripts/**", "**/.windsurf/**"]
        self.include_patterns = include_patterns or []
        self.ignore_patterns = ignore_patterns or [
            "node_modules/**",
            ".git/**",
            "__pycache__/**",
            "*.pyc",
            ".cursor/**",
            ".vscode/**"
        ]
        self.debounce_seconds = debounce_seconds
        self.recursive = recursive
        self.auto_import = auto_import
        self.scan_existing_on_start = scan_existing_on_start


class FileChangeHandler(FileSystemEventHandler):
    """
    文件变化处理器
    监听文件创建和修改事件
    """
    
    def __init__(self, config: FileWatchConfig, collector: 'FileWatcher'):
        super().__init__()
        self.config = config
        self.collector = collector
        self._pending_files: Dict[str, float] = {}
        self._debounce_task: Optional[asyncio.Task] = None
    
    def _should_process(self, path: str) -> bool:
        """检查文件是否应该被处理"""
        # 检查扩展名
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.config.supported_extensions:
            return False
        
        # 如果配置了 include_patterns，必须匹配其中一个
        if self.config.include_patterns:
            matched = False
            for pattern in self.config.include_patterns:
                if self._match_pattern(path, pattern):
                    matched = True
                    break
            if not matched:
                return False
        
        # 检查忽略模式
        for pattern in self.config.ignore_patterns:
            if pattern.startswith("**/"):
                # 通配符模式
                if pattern[:-3] in path or path.endswith(pattern[3:]):
                    return False
            elif "/*." in pattern:
                # 扩展名模式
                if path.endswith(pattern[2:]):
                    return False
            elif pattern in path:
                return False
        
        return True
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """检查路径是否匹配模式（简化版通配符匹配）"""
        # 统一路径分隔符
        path = path.replace("\\", "/")
        pattern = pattern.replace("\\", "/")
        
        # 移除末尾的通配符
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            return path.startswith(prefix) or prefix in path
        elif pattern.startswith("**/"):
            suffix = pattern[3:]
            return path.endswith(suffix) or suffix in path
        elif pattern in path:
            return True
        
        return False
    
    def _add_pending(self, path: str):
        """添加待处理文件"""
        self._pending_files[path] = time.time()
        self._schedule_debounce()
    
    def _schedule_debounce(self):
        """安排防抖处理"""
        if self._debounce_task is None or self._debounce_task.done():
            self._debounce_task = asyncio.create_task(self._process_pending())
    
    async def _process_pending(self):
        """处理待处理文件"""
        await asyncio.sleep(self.config.debounce_seconds)
        
        now = time.time()
        ready_files = []
        
        for path, add_time in list(self._pending_files.items()):
            if now - add_time >= self.config.debounce_seconds:
                ready_files.append(path)
                self._pending_files.pop(path, None)
        
        for path in ready_files:
            await self._process_file(path)
    
    async def _process_file(self, path: str):
        """处理单个文件"""
        if not os.path.exists(path):
            logger.debug(f"File no longer exists: {path}")
            return
        
        try:
            # 读取文件内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.debug(f"Empty file skipped: {path}")
                return
            
            # 获取文件元数据
            stat = os.stat(path)
            file_ext = os.path.splitext(path)[1].lower()
            
            # 根据文件类型构建对话
            conversation = self._build_conversation(path, content, file_ext, stat)
            
            # 放入队列
            await self.collector.put(conversation)
            logger.info(f"File imported: {path}")
            
        except Exception as e:
            logger.error(f"Error processing file {path}: {e}")
    
    def _build_conversation(
        self, 
        path: str, 
        content: str, 
        file_ext: str,
        stat
    ) -> CollectedConversation:
        """根据文件内容构建对话对象"""
        
        # 获取相对路径作为项目标识
        rel_path = path
        for watch_path in self.config.watch_paths:
            if path.startswith(watch_path):
                rel_path = path[len(watch_path):].lstrip(os.sep)
                break
        
        # 文件类型映射到角色
        role = "assistant" if file_ext in [".md", ".txt", ".yaml", ".yml"] else "user"
        
        # 构建消息
        message = CollectedMessage(
            source=CollectorType.FILE_WATCHER,
            source_id=path,
            content=content,
            role=role,
            timestamp=datetime.fromtimestamp(stat.st_mtime),
            metadata={
                "file_path": path,
                "relative_path": rel_path,
                "file_extension": file_ext,
                "file_size": stat.st_size,
                "file_hash": hashlib.md5(content.encode()).hexdigest()
            }
        )
        
        return CollectedConversation(
            source=CollectorType.FILE_WATCHER,
            source_id=path,
            messages=[message],
            metadata={
                "file_path": path,
                "project": os.path.dirname(path),
                "file_type": file_ext.lstrip('.')
            },
            created_at=datetime.fromtimestamp(stat.st_ctime)
        )
    
    def on_created(self, event: FileCreatedEvent):
        """文件创建事件"""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            logger.debug(f"File created: {event.src_path}")
            self._add_pending(event.src_path)
    
    def on_modified(self, event: FileModifiedEvent):
        """文件修改事件"""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            logger.debug(f"File modified: {event.src_path}")
            self._add_pending(event.src_path)
    
    def on_moved(self, event: FileMovedEvent):
        """文件移动事件"""
        if event.is_directory:
            return
        # 处理移动后的文件
        if hasattr(event, 'dest_path') and self._should_process(event.dest_path):
            logger.debug(f"File moved to: {event.dest_path}")
            self._add_pending(event.dest_path)


class FileWatcher(BaseCollector):
    """
    文件监控采集器
    监控指定目录，新文件自动导入知识库
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # 构建配置对象
        self._watch_config = FileWatchConfig(
            watch_paths=self.config.get("watch_paths", ["~/notes"]),
            supported_extensions=self.config.get("supported_extensions"),
            include_patterns=self.config.get("include_patterns"),
            ignore_patterns=self.config.get("ignore_patterns"),
            debounce_seconds=self.config.get("debounce_seconds", 2.0),
            recursive=self.config.get("recursive", True),
            auto_import=self.config.get("auto_import", True),
            scan_existing_on_start=self.config.get("scan_existing_on_start", False)
        )
        
        self._observer: Optional[Observer] = None
        self._handlers: List[FileChangeHandler] = []
        self._processed_paths: Set[str] = set()
    
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.FILE_WATCHER
    
    async def start(self) -> bool:
        """启动文件监控"""
        if self._running:
            logger.warning(f"{self.name} is already running")
            return True
        
        try:
            # 验证监控路径
            valid_paths = []
            for path in self._watch_config.watch_paths:
                if os.path.isdir(path):
                    valid_paths.append(path)
                    logger.info(f"Watching directory: {path}")
                elif os.path.exists(path):
                    # 如果是文件，监控其所在目录
                    parent = os.path.dirname(path)
                    if os.path.isdir(parent) and parent not in valid_paths:
                        valid_paths.append(parent)
                        logger.info(f"Watching directory for file: {parent}")
                else:
                    logger.warning(f"Path does not exist: {path}")
            
            if not valid_paths:
                logger.error("No valid watch paths")
                self.status = CollectorStatus.ERROR
                return False
            
            # 更新监控路径
            self._watch_config.watch_paths = valid_paths
            
            # 创建观察者
            self._observer = Observer()
            
            # 为每个监控路径创建处理器
            for path in valid_paths:
                handler = FileChangeHandler(self._watch_config, self)
                self._observer.schedule(
                    handler,
                    path,
                    recursive=self._watch_config.recursive
                )
                self._handlers.append(handler)
            
            # 启动观察者
            self._observer.start()
            self._running = True
            self.status = CollectorStatus.RUNNING
            
            # 启动时扫描现有文件
            if self._watch_config.scan_existing_on_start:
                logger.info("Scanning existing files on startup...")
                await self._scan_existing_files(valid_paths)
            
            logger.info(f"{self.name} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}")
            self.status = CollectorStatus.ERROR
            return False
    
    async def _scan_existing_files(self, watch_paths: List[str]):
        """扫描现有文件"""
        import fnmatch
        
        for base_path in watch_paths:
            try:
                for root, dirs, files in os.walk(base_path):
                    # 递归控制
                    if not self._watch_config.recursive:
                        break
                    
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        
                        # 检查是否应该处理
                        if self._should_process_file(file_path):
                            # 避免重复处理
                            if file_path not in self._processed_paths:
                                await self.import_file(file_path)
                                self._processed_paths.add(file_path)
                                
            except Exception as e:
                logger.error(f"Error scanning {base_path}: {e}")
        
        logger.info(f"Existing file scan completed. Processed {len(self._processed_paths)} files")
    
    def _should_process_file(self, path: str) -> bool:
        """检查文件是否应该被处理（简化版，用于现有文件扫描）"""
        # 检查扩展名
        ext = os.path.splitext(path)[1].lower()
        if ext not in self._watch_config.supported_extensions:
            return False
        
        # 如果配置了 include_patterns，必须匹配其中一个
        if self._watch_config.include_patterns:
            matched = False
            for pattern in self._watch_config.include_patterns:
                # 简化匹配逻辑
                path_normalized = path.replace("\\", "/")
                pattern_normalized = pattern.replace("\\", "/")
                
                if pattern_normalized.startswith("**/"):
                    suffix = pattern_normalized[3:]
                    if suffix in path_normalized:
                        matched = True
                        break
                elif pattern_normalized.endswith("/**"):
                    prefix = pattern_normalized[:-3]
                    if path_normalized.startswith(prefix):
                        matched = True
                        break
                elif pattern_normalized in path_normalized:
                    matched = True
                    break
            
            if not matched:
                return False
        
        # 检查忽略模式
        for pattern in self._watch_config.ignore_patterns:
            if pattern in path:
                return False
        
        return True
    
    async def stop(self) -> bool:
        """停止文件监控"""
        if not self._running:
            return True
        
        try:
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None
            
            self._handlers.clear()
            self._running = False
            self.status = CollectorStatus.IDLE
            
            logger.info(f"{self.name} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop {self.name}: {e}")
            self.status = CollectorStatus.ERROR
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not self._running:
            return False
        
        # 检查观察者是否在运行
        if self._observer is None or not self._observer.is_alive():
            self.status = CollectorStatus.ERROR
            return False
        
        return True
    
    def add_watch_path(self, path: str) -> bool:
        """
        动态添加监控路径
        """
        if not os.path.isdir(path):
            logger.warning(f"Path is not a directory: {path}")
            return False
        
        if self._running and self._observer:
            self._observer.schedule(
                FileChangeHandler(self._watch_config, self),
                path,
                recursive=self._watch_config.recursive
            )
            self._watch_config.watch_paths.append(path)
            logger.info(f"Added watch path: {path}")
            return True
        
        return False
    
    def remove_watch_path(self, path: str) -> bool:
        """
        动态移除监控路径
        """
        if path in self._watch_config.watch_paths:
            self._watch_config.watch_paths.remove(path)
            logger.info(f"Removed watch path: {path}")
            return True
        return False
    
    def get_watched_paths(self) -> List[str]:
        """获取当前监控的路径列表"""
        return self._watch_config.watch_paths.copy()
    
    async def import_file(self, file_path: str) -> Optional[CollectedConversation]:
        """
        手动导入单个文件
        """
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return None
        
        if not self._should_process_file(file_path):
            logger.warning(f"File type not supported: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            stat = os.stat(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            conversation = self._build_conversation_from_file(
                file_path, content, file_ext, stat
            )
            
            await self.put(conversation)
            logger.info(f"File imported manually: {file_path}")
            return conversation
            
        except Exception as e:
            logger.error(f"Error importing file {file_path}: {e}")
            return None
    
    def _should_process_file(self, path: str) -> bool:
        """检查文件是否应该被处理"""
        ext = os.path.splitext(path)[1].lower()
        return ext in self._watch_config.supported_extensions
    
    def _build_conversation_from_file(
        self,
        path: str,
        content: str,
        file_ext: str,
        stat
    ) -> CollectedConversation:
        """从文件构建对话对象"""
        
        role = "assistant" if file_ext in [".md", ".txt", ".yaml", ".yml"] else "user"
        
        message = CollectedMessage(
            source=CollectorType.FILE_WATCHER,
            source_id=path,
            content=content,
            role=role,
            timestamp=datetime.fromtimestamp(stat.st_mtime),
            metadata={
                "file_path": path,
                "file_extension": file_ext,
                "file_size": stat.st_size,
                "import_type": "manual"
            }
        )
        
        return CollectedConversation(
            source=CollectorType.FILE_WATCHER,
            source_id=path,
            messages=[message],
            metadata={
                "file_path": path,
                "file_type": file_ext.lstrip('.'),
                "imported_at": datetime.now().isoformat()
            }
        )
