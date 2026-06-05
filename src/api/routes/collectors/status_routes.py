"""Status routes for collectors."""

from fastapi import APIRouter, HTTPException, status

from src.api.routes.collectors.deps import get_unified_collector, parse_collector_type

router = APIRouter()


def _filter_public_collectors_status(payload):
    """Hide experimental collectors from the public status surface."""
    if not isinstance(payload, dict):
        return payload

    collectors = payload.get("collectors")
    if not isinstance(collectors, list):
        return payload

    return {
        **payload,
        "collectors": [
            item
            for item in collectors
            if str(item.get("support_tier") or "official") == "official"
        ],
    }


@router.get("/status")
async def get_collectors_status():
    """获取所有采集器状态"""
    return _filter_public_collectors_status(get_unified_collector().get_status())


@router.get("/collectors/{collector_type}")
async def get_collector_status(collector_type: str):
    """获取指定采集器状态"""
    ctype = parse_collector_type(collector_type)
    status_data = get_unified_collector().get_collector_status(ctype)
    if status_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collector not found: {collector_type}",
        )

    return status_data
