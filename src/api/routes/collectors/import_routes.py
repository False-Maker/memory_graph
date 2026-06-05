"""Import routes for collectors."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from src.api.routes.collectors_scan import DirectoryScanRequest, ScanResult, import_scan_results, perform_directory_scan
from src.api.routes.collectors.deps import get_unified_collector, scan_directory as package_scan_directory
from src.api.routes.collectors_runtime import handle_import_directory, handle_import_message

router = APIRouter()


@router.post("/import")
async def import_message(source: str, data: Dict[str, Any]):
    """手动导入消息"""
    return await handle_import_message(
        unified=get_unified_collector(),
        source=source,
        data=data,
    )


@router.post("/scan-directory", response_model=ScanResult)
async def scan_directory(request: DirectoryScanRequest):
    """
    扫描目录，识别对话文件

    用户在页面输入目录路径，系统自动扫描目录下所有文件，
    自动识别哪些是对话文件（如 Cursor 的 agent-transcripts），
    跳过其他无关文件（如 node_modules、.git 等）。
    """
    try:
        return await perform_directory_scan(request)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory not found: {exc.args[0]}",
        ) from exc


@router.post("/import-directory")
async def import_directory(request: DirectoryScanRequest):
    """
    扫描目录并批量导入对话文件

    用户在页面输入目录路径，系统自动：
    1. 扫描目录下所有文件
    2. 自动识别对话格式（Cursor/Windsurf/Claude/通用）
    3. 过滤掉无关文件
    4. 批量导入到知识库
    """
    from src.core.collectors.file_watcher import FileWatcher

    return await handle_import_directory(
        request=request,
        scan_directory=package_scan_directory,
        get_unified_collector=get_unified_collector,
        import_scan_results=import_scan_results,
        file_watcher_factory=FileWatcher,
    )
