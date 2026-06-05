"""File watcher routes for collectors."""

from fastapi import APIRouter

from src.api.routes.collectors.deps import require_runtime_component
from src.api.security import resolve_allowed_path
from src.api.routes.collectors_runtime import (
    handle_get_watched_paths,
    handle_import_file,
    handle_watch_path_mutation,
)

router = APIRouter()


@router.get("/file-watcher/paths")
async def get_watched_paths():
    """获取当前监控的文件路径"""
    file_watcher = require_runtime_component("file_watcher", "File watcher not initialized")
    return handle_get_watched_paths(file_watcher)


@router.post("/file-watcher/paths")
async def add_watch_path(path: str):
    """添加监控路径"""
    file_watcher = require_runtime_component("file_watcher", "File watcher not initialized")
    resolved_path = str(resolve_allowed_path(path))
    return handle_watch_path_mutation(
        path=resolved_path,
        success=file_watcher.add_watch_path(resolved_path),
        status_label="added",
    )


@router.delete("/file-watcher/paths")
async def remove_watch_path(path: str):
    """移除监控路径"""
    file_watcher = require_runtime_component("file_watcher", "File watcher not initialized")
    resolved_path = str(resolve_allowed_path(path))
    return handle_watch_path_mutation(
        path=resolved_path,
        success=file_watcher.remove_watch_path(resolved_path),
        status_label="removed",
    )


@router.post("/file-watcher/import")
async def import_file(file_path: str):
    """手动导入单个文件"""
    file_watcher = require_runtime_component("file_watcher", "File watcher not initialized")
    return await handle_import_file(file_watcher=file_watcher, file_path=str(resolve_allowed_path(file_path)))
