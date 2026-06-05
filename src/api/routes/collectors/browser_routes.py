"""Browser collectors routes."""

from fastapi import APIRouter

from src.core.collectors import BrowserMessage
from src.api.routes.collectors.deps import require_runtime_component
from src.api.routes.collectors_runtime import handle_capture_browser_message

router = APIRouter()


@router.post("/browser/capture")
async def capture_browser_message(message: BrowserMessage):
    """接收浏览器插件发来的消息"""
    browser = require_runtime_component("browser", "Browser collector not initialized")
    return await handle_capture_browser_message(browser=browser, message=message)
