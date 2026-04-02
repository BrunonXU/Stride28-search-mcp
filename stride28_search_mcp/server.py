"""Stride28 MCP 搜索服务 —— 小红书 + 知乎

使用 Playwright 浏览器内操作，不调 API，不需要签名。
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import signal
import sys

_original_stdout = sys.stdout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP
from stride28_search_mcp.lifecycle import LifecycleManager
from stride28_search_mcp.models import (
    EnvelopeBuilder, ErrorCode, LoginData, SearchData,
)
from stride28_search_mcp.adapter import LoginRequiredError, BrowserCrashError

# ============================================================
# 全局实例
# ============================================================

lifecycle = LifecycleManager()
mcp = FastMCP("stride28-search")

# ============================================================
# Tool: 登录小红书
# ============================================================

@mcp.tool(
    name="login_xiaohongshu",
    description=(
        "登录小红书账号。"
        "调用后会弹出浏览器窗口，需要用户使用小红书 App 手动扫码完成登录。"
        "扫码后耗时约 10-30 秒完成登录流程，总超时 5 分钟。"
        "登录成功后，后续搜索调用将使用新的登录态。"
    ),
)
async def login_xiaohongshu() -> str:
    platform, tool_name = "xiaohongshu", "login_xiaohongshu"
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            await searcher.login(timeout=300)
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.success(
                platform, tool_name,
                LoginData(message=f"{platform} 登录成功").model_dump(),
            )
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.LOGIN_TIMEOUT,
                "登录超时（5分钟），请重试",
            )
        except Exception as e:
            logger.exception("登录异常")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e),
            )


# ============================================================
# Tool: 搜索小红书
# ============================================================

@mcp.tool(
    name="search_xiaohongshu",
    description=(
        "搜索小红书笔记内容。"
        "返回标题、URL、作者、点赞数等信息。"
        "limit 建议 10-20 条。"
        "需要先登录（login_xiaohongshu），未登录时返回 login_required 错误。"
    ),
)
async def search_xiaohongshu(query: str, limit: int = 10) -> str:
    platform, tool_name = "xiaohongshu", "search_xiaohongshu"

    if lifecycle.is_crashed(platform):
        return EnvelopeBuilder.error(
            platform, tool_name, ErrorCode.BROWSER_CRASHED,
            "浏览器已崩溃，请重启 MCP Server",
        )

    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            if not await searcher.check_auth():
                return EnvelopeBuilder.error(
                    platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                    "小红书未登录或 Cookie 已失效，请先调用 login_xiaohongshu 工具完成登录",
                )
            search_data = await asyncio.wait_for(
                searcher.search(query, limit), timeout=60,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, search_data.model_dump())
        except LoginRequiredError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                "小红书未登录或 Cookie 已失效，请先调用 login_xiaohongshu 工具完成登录",
            )
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "搜索超时（60秒），请稍后重试",
            )
        except BrowserCrashError:
            lifecycle.record_failure(platform)
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.UNKNOWN_ERROR, "浏览器异常，已自动重建实例，请重试",
            )
        except Exception as e:
            lifecycle.record_failure(platform)
            logger.exception("搜索异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))

# ============================================================
# Tool: 获取笔记详情
# ============================================================

@mcp.tool(
    name="get_note_detail",
    description=(
        "获取小红书笔记的完整详情，包括正文、评论、图片、互动数据。"
        "需要提供 note_id 和 xsec_token（从搜索结果中获取）。"
        "需要先登录（login_xiaohongshu）。"
    ),
)
async def get_note_detail(note_id: str, xsec_token: str = "") -> str:
    platform, tool_name = "xiaohongshu", "get_note_detail"
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            if not await searcher.check_auth():
                return EnvelopeBuilder.error(
                    platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                    "小红书未登录，请先调用 login_xiaohongshu",
                )
            detail = await asyncio.wait_for(
                searcher.get_note_detail(note_id, xsec_token), timeout=30,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, detail.model_dump())
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "获取详情超时（30秒）",
            )
        except Exception as e:
            logger.exception("获取详情异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))


# ============================================================
# Tool: 搜索知乎
# ============================================================

@mcp.tool(
    name="search_zhihu",
    description=(
        "搜索知乎内容（问答、专栏、视频）。"
        "不需要登录即可使用。"
        "返回标题、URL、类型、赞数、作者等信息。"
    ),
)
async def search_zhihu(query: str, limit: int = 10) -> str:
    platform, tool_name = "zhihu", "search_zhihu"
    if lifecycle.is_crashed(platform):
        return EnvelopeBuilder.error(
            platform, tool_name, ErrorCode.BROWSER_CRASHED, "浏览器已崩溃，请重启 MCP Server",
        )
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            if not await searcher.check_auth():
                return EnvelopeBuilder.error(
                    platform, tool_name, ErrorCode.UNKNOWN_ERROR, "知乎浏览器初始化失败",
                )
            search_data = await asyncio.wait_for(
                searcher.search(query, limit), timeout=30,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, search_data.model_dump())
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "搜索超时（30秒）",
            )
        except Exception as e:
            lifecycle.record_failure(platform)
            logger.exception("知乎搜索异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))


# ============================================================
# Tool: 获取知乎问题回答
# ============================================================

@mcp.tool(
    name="get_zhihu_question",
    description=(
        "获取知乎问题的详情和 top N 回答。"
        "需要提供 question_id（从搜索结果的 xsec_token 字段获取）。"
    ),
)
async def get_zhihu_question(question_id: str, limit: int = 5) -> str:
    platform, tool_name = "zhihu", "get_zhihu_question"
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            if not await searcher.check_auth():
                return EnvelopeBuilder.error(
                    platform, tool_name, ErrorCode.UNKNOWN_ERROR, "知乎浏览器初始化失败",
                )
            data = await asyncio.wait_for(
                searcher.get_question_answers(question_id, limit), timeout=30,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, data)
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "获取回答超时（30秒）",
            )
        except Exception as e:
            logger.exception("知乎问题获取异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))


# ============================================================
# Tool: 登录知乎
# ============================================================

@mcp.tool(
    name="login_zhihu",
    description=(
        "登录知乎账号。"
        "调用后会弹出浏览器窗口，需要手动登录。"
        "登录成功后，get_zhihu_question 可以获取完整回答内容。"
    ),
)
async def login_zhihu() -> str:
    platform, tool_name = "zhihu", "login_zhihu"
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            await searcher.login(timeout=300)
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.success(
                platform, tool_name,
                LoginData(message="知乎登录成功").model_dump(),
            )
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.LOGIN_TIMEOUT, "登录超时（5分钟）",
            )
        except Exception as e:
            logger.exception("知乎登录异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))


# ============================================================
# 优雅退出
# ============================================================

def _sync_cleanup():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(lifecycle.cleanup())
        else:
            loop.run_until_complete(lifecycle.cleanup())
    except Exception:
        pass

atexit.register(_sync_cleanup)

if sys.platform != "win32":
    def _signal_handler(signum, frame):
        logger.info("收到信号 %s，开始清理...", signum)
        _sync_cleanup()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


# ============================================================
# 入口
# ============================================================

def main():
    sys.stdout = _original_stdout
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
