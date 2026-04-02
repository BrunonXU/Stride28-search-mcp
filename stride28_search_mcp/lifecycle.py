"""MCP 平台生命周期管理器"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

_MAX_FAILURES = 3

_WHITELIST_TOOLS: Set[str] = {"login_xiaohongshu", "login_zhihu"}


class RateLimiter:
    """统一请求频率控制器 —— 所有 tool call 的入口层"""

    def __init__(self, min_interval: float = 2.0):
        self._min_interval = min_interval
        self._last_request: Dict[str, float] = {}

    def is_whitelisted(self, tool_name: str) -> bool:
        """判断 tool 是否在白名单中（login/health check 跳过限流）"""
        return tool_name in _WHITELIST_TOOLS

    async def acquire(self, platform: str, tool_name: str):
        """统一入口：白名单跳过，其余强制等待间隔"""
        if self.is_whitelisted(tool_name):
            return
        now = time.monotonic()
        last = self._last_request.get(platform, 0)
        wait_time = self._min_interval - (now - last)
        if wait_time > 0:
            logger.info(
                "RateLimiter: 等待 %.1f 秒 (platform=%s, tool=%s)",
                wait_time,
                platform,
                tool_name,
            )
            await asyncio.sleep(wait_time)
        self._last_request[platform] = time.monotonic()


class LifecycleManager:
    """平台适配器生命周期管理"""

    def __init__(self):
        self._searchers: Dict[str, object] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._failures: Dict[str, int] = {}
        self.rate_limiter = RateLimiter(
            min_interval=float(os.getenv("STRIDE28_RATE_LIMIT_SECONDS", "2.0"))
        )

    def get_lock(self, platform: str) -> asyncio.Lock:
        if platform not in self._locks:
            self._locks[platform] = asyncio.Lock()
        return self._locks[platform]

    async def get_searcher(self, platform: str):
        if platform not in self._searchers:
            if platform == "xiaohongshu":
                from stride28_search_mcp.adapter import XhsBrowserSearcher
                self._searchers[platform] = XhsBrowserSearcher()
            elif platform == "zhihu":
                from stride28_search_mcp.zhihu_adapter import ZhihuBrowserSearcher
                self._searchers[platform] = ZhihuBrowserSearcher()
            else:
                raise ValueError(f"未知平台: {platform}")
            logger.info("平台 %s 搜索器已创建", platform)
        return self._searchers[platform]

    async def destroy_searcher(self, platform: str):
        searcher = self._searchers.pop(platform, None)
        if searcher:
            await searcher.close()
            logger.info("平台 %s 搜索器已销毁", platform)

    def record_failure(self, platform: str):
        self._failures[platform] = self._failures.get(platform, 0) + 1

    def reset_failures(self, platform: str):
        self._failures[platform] = 0

    def is_crashed(self, platform: str) -> bool:
        return self._failures.get(platform, 0) >= _MAX_FAILURES

    async def cleanup(self):
        for platform in list(self._searchers.keys()):
            await self.destroy_searcher(platform)
