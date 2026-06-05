"""Control routes for collectors."""

from typing import Any, Dict

from fastapi import APIRouter

from src.api.routes.collectors.deps import (
    get_settings,
    get_unified_collector,
    parse_collector_types,
    require_registered_collector,
)
from src.api.routes.collectors_runtime import (
    handle_single_collector_action,
    handle_start_collectors,
    handle_stop_collectors,
)

router = APIRouter()


@router.post("/start")
async def start_collectors(request: Dict[str, Any]):
    """
    启动采集器
    请求体格式: {"enabled_types": ["cursor", "file_watcher"]} 或 {"collector_types": ["cursor"]}
    """
    return await handle_start_collectors(
        unified=get_unified_collector(),
        settings=get_settings(),
        request=request,
        parse_collector_types=parse_collector_types,
    )


@router.post("/stop")
async def stop_collectors(request: Dict[str, Any]):
    """
    停止采集器
    请求体格式: {"collector_types": ["cursor"]}
    """
    return await handle_stop_collectors(
        unified=get_unified_collector(),
        request=request,
        parse_collector_types=parse_collector_types,
    )


@router.post("/collectors/{collector_type}/start")
async def start_collector(collector_type: str):
    """启动指定采集器"""
    _, collector = require_registered_collector(collector_type)
    return await handle_single_collector_action(
        collector=collector,
        collector_type=collector_type,
        action="start",
    )


@router.post("/collectors/{collector_type}/stop")
async def stop_collector(collector_type: str):
    """停止指定采集器"""
    _, collector = require_registered_collector(collector_type)
    return await handle_single_collector_action(
        collector=collector,
        collector_type=collector_type,
        action="stop",
    )
