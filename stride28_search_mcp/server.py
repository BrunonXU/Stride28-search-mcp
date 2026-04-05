"""Stride28 MCP 搜索服务 —— 小红书 + 知乎

使用 Playwright 浏览器内操作，不调 API，不需要签名。
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import math
import signal
import subprocess
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
from stride28_search_mcp.adapter import (
    BrowserCrashError,
    BrowserLaunchError,
    CaptchaDetectedError,
    LoginRequiredError,
    SearchBlockedError,
)
from stride28_search_mcp.state import (
    clear_browser_data,
    find_cookie_store,
    get_browser_data_dir,
    get_data_home,
    get_non_login_headless,
    get_platform_headless,
    get_profile_mode,
    get_profile_name,
)

# ============================================================
# 全局实例
# ============================================================

lifecycle = LifecycleManager()
mcp = FastMCP("stride28-search")


def _browser_init_message(exc: Exception) -> str:
    detail = str(exc).strip()
    base = (
        "浏览器初始化失败，请先执行 `stride28-search-mcp install-browser` 安装 Chromium，"
        "并确认数据目录可写。"
    )
    return f"{base} 原始错误: {detail}" if detail else base


def _profile_display_name() -> str:
    return get_profile_name() or "shared-default"


def _cooldown_message(remaining_seconds: int, reason: str = "") -> str:
    minutes = max(1, math.ceil(remaining_seconds / 60))
    suffix = f" 最近触发原因: {reason}." if reason else ""
    return (
        f"小红书当前处于风控冷却期，请等待约 {minutes} 分钟后再重试。"
        f"{suffix} 如需重新回到首次用户状态，可先执行 `reset_xiaohongshu_login` "
        "或 `stride28-search-mcp clear-state xhs`。"
    )


def _active_cooldown_envelope(platform: str, tool_name: str) -> str | None:
    cooldown = lifecycle.get_risk_cooldown(platform)
    if not cooldown.get("active"):
        return None
    return EnvelopeBuilder.error(
        platform,
        tool_name,
        ErrorCode.RISK_COOLDOWN_ACTIVE,
        _cooldown_message(
            int(cooldown.get("remaining_seconds", 0)),
            str(cooldown.get("reason", "")),
        ),
    )


def _clear_state_targets(target: str) -> list[tuple[str, str]]:
    normalized = target.strip().lower()
    if normalized in {"xhs", "xiaohongshu"}:
        return [("xiaohongshu", "xhs")]
    if normalized == "zhihu":
        return [("zhihu", "zhihu")]
    if normalized == "all":
        return [("xiaohongshu", "xhs"), ("zhihu", "zhihu")]
    raise ValueError("clear-state 仅支持 xhs | zhihu | all")


async def _clear_state(target: str) -> dict:
    cleared = []
    for platform, storage_platform in _clear_state_targets(target):
        await lifecycle.destroy_searcher(platform)
        lifecycle.clear_risk_cooldown(platform)
        cleared_path = clear_browser_data(storage_platform)
        cleared.append(
            {
                "platform": platform,
                "profile": _profile_display_name(),
                "path": str(cleared_path),
            }
        )
    return {
        "target": target,
        "profile": _profile_display_name(),
        "cleared": cleared,
    }


def _run_clear_state(target: str) -> int:
    import json

    try:
        result = asyncio.run(_clear_state(target))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _run_doctor() -> int:
    import importlib
    import importlib.metadata
    import json
    from pathlib import Path

    data_home = get_data_home()
    try:
        version = importlib.metadata.version("stride28-search-mcp")
    except importlib.metadata.PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        version = "unknown"
        try:
            with pyproject_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("version ="):
                        version = stripped.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass
    report = {
        "package": "stride28-search-mcp",
        "version": version,
        "python": sys.version.split()[0],
        "data_home": str(data_home),
        "profile": _profile_display_name(),
        "profile_mode": get_profile_mode(),
        "legacy_headless_fallback": get_non_login_headless(),
        "xhs_headless": get_platform_headless("xhs"),
        "zhihu_headless": get_platform_headless("zhihu"),
        "checks": {},
    }

    report["checks"]["python_supported"] = {
        "ok": sys.version_info >= (3, 10),
        "detail": "requires Python >= 3.10",
    }

    for module_name in ("mcp", "playwright", "pydantic"):
        try:
            importlib.import_module(module_name)
            report["checks"][f"import_{module_name}"] = {"ok": True}
        except Exception as exc:
            report["checks"][f"import_{module_name}"] = {"ok": False, "detail": str(exc)}

    try:
        data_home.mkdir(parents=True, exist_ok=True)
        probe = data_home / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        report["checks"]["data_home_writable"] = {"ok": True}
    except Exception as exc:
        report["checks"]["data_home_writable"] = {"ok": False, "detail": str(exc)}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True,
            check=True,
        )
        install_location = ""
        for line in result.stdout.splitlines():
            if "Install location:" in line:
                install_location = line.split("Install location:", 1)[1].strip()
                break
        report["checks"]["chromium_installed"] = {
            "ok": bool(install_location) and Path(install_location).exists(),
            "detail": install_location or result.stdout.strip(),
        }
    except Exception as exc:
        report["checks"]["chromium_installed"] = {"ok": False, "detail": str(exc)}

    xhs_browser_data_dir = get_browser_data_dir("xhs")
    zhihu_browser_data_dir = get_browser_data_dir("zhihu")
    xhs_cookie_store = find_cookie_store("xhs")
    zhihu_cookie_store = find_cookie_store("zhihu")

    report["checks"]["xhs_browser_data_dir"] = {
        "ok": True,
        "detail": str(xhs_browser_data_dir),
    }
    report["checks"]["xhs_cookie_store"] = {
        "ok": xhs_cookie_store is not None,
        "detail": str(xhs_cookie_store or (xhs_browser_data_dir / "Default" / "Network" / "Cookies")),
    }
    report["checks"]["zhihu_browser_data_dir"] = {
        "ok": True,
        "detail": str(zhihu_browser_data_dir),
    }
    report["checks"]["zhihu_cookie_store"] = {
        "ok": zhihu_cookie_store is not None,
        "detail": str(
            zhihu_cookie_store or (zhihu_browser_data_dir / "Default" / "Network" / "Cookies")
        ),
    }
    report["checks"]["xhs_risk_cooldown"] = {
        "ok": True,
        "detail": lifecycle.get_risk_cooldown("xiaohongshu"),
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

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
    await lifecycle.rate_limiter.acquire(platform, tool_name)
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
        except BrowserLaunchError as e:
            logger.exception("浏览器初始化异常")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.BROWSER_INIT_FAILED, _browser_init_message(e),
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
async def search_xiaohongshu(query: str, limit: int = 10, note_type: str = "all") -> str:
    platform, tool_name = "xiaohongshu", "search_xiaohongshu"
    cooldown_error = _active_cooldown_envelope(platform, tool_name)
    if cooldown_error:
        return cooldown_error
    await lifecycle.rate_limiter.acquire(platform, tool_name)

    if lifecycle.is_crashed(platform):
        return EnvelopeBuilder.error(
            platform, tool_name, ErrorCode.BROWSER_CRASHED,
            "浏览器已崩溃，请重启 MCP Server",
        )

    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            search_data = await asyncio.wait_for(
                searcher.search(query, limit, note_type), timeout=60,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, search_data.model_dump())
        except CaptchaDetectedError:
            lifecycle.activate_risk_cooldown(platform, "captcha_detected")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.CAPTCHA_DETECTED,
                "搜索结果为空且检测到验证码拦截，请稍后重试或手动处理验证码",
            )
        except SearchBlockedError as e:
            lifecycle.activate_risk_cooldown(platform, "search_blocked")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_BLOCKED, str(e),
            )
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
        except BrowserLaunchError as e:
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.BROWSER_INIT_FAILED, _browser_init_message(e),
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
        "默认仅返回较少评论；如需更深评论翻页，请显式提高 max_comments。"
    ),
)
async def get_note_detail(note_id: str, xsec_token: str = "", max_comments: int = 10) -> str:
    platform, tool_name = "xiaohongshu", "get_note_detail"
    max_comments = min(max_comments, 50)  # 评论翻页会增加风控风险，硬上限 50
    cooldown_error = _active_cooldown_envelope(platform, tool_name)
    if cooldown_error:
        return cooldown_error
    await lifecycle.rate_limiter.acquire(platform, tool_name)
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            detail = await asyncio.wait_for(
                searcher.get_note_detail(note_id, xsec_token, max_comments), timeout=30,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, detail.model_dump())
        except CaptchaDetectedError:
            lifecycle.activate_risk_cooldown(platform, "captcha_detected")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.CAPTCHA_DETECTED,
                "笔记详情加载期间检测到验证码拦截，请稍后重试或手动处理验证码",
            )
        except SearchBlockedError as e:
            lifecycle.activate_risk_cooldown(platform, "search_blocked")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_BLOCKED, str(e),
            )
        except LoginRequiredError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                "小红书未登录，请先调用 login_xiaohongshu",
            )
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "获取详情超时（30秒）",
            )
        except BrowserLaunchError as e:
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.BROWSER_INIT_FAILED, _browser_init_message(e),
            )
        except Exception as e:
            logger.exception("获取详情异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))


# ============================================================
# Tool: 重置小红书登录态
# ============================================================

@mcp.tool(
    name="reset_xiaohongshu_login",
    description="清空当前 profile 下的小红书浏览器状态目录，用于重新走首次登录流程。",
)
async def reset_xiaohongshu_login() -> str:
    platform, tool_name = "xiaohongshu", "reset_xiaohongshu_login"
    lock = lifecycle.get_lock(platform)
    async with lock:
        data = await _clear_state("xhs")
        return EnvelopeBuilder.success(platform, tool_name, data)


# ============================================================
# Tool: 搜索知乎
# ============================================================

@mcp.tool(
    name="search_zhihu",
    description=(
        "搜索知乎内容（问答、专栏、视频）。"
        "当前需要先登录（login_zhihu），未登录时返回 login_required 错误。"
        "返回标题、URL、类型、赞数、作者等信息。"
    ),
)
async def search_zhihu(query: str, limit: int = 10) -> str:
    platform, tool_name = "zhihu", "search_zhihu"
    await lifecycle.rate_limiter.acquire(platform, tool_name)
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
                    platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                    "知乎当前需要登录后才能搜索，请先调用 login_zhihu 工具完成登录",
                )
            search_data = await asyncio.wait_for(
                searcher.search(query, limit), timeout=30,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, search_data.model_dump())
        except LoginRequiredError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                "知乎当前需要登录后才能搜索，请先调用 login_zhihu 工具完成登录",
            )
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "搜索超时（30秒）",
            )
        except BrowserLaunchError as e:
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.BROWSER_INIT_FAILED, _browser_init_message(e),
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
        "当前需要先登录（login_zhihu）。"
        "需要提供 question_id（从搜索结果的 xsec_token 字段获取）。"
    ),
)
async def get_zhihu_question(question_id: str, limit: int = 5, max_content_length: int = 10000) -> str:
    platform, tool_name = "zhihu", "get_zhihu_question"
    await lifecycle.rate_limiter.acquire(platform, tool_name)
    lock = lifecycle.get_lock(platform)
    async with lock:
        try:
            searcher = await lifecycle.get_searcher(platform)
            if not await searcher.check_auth():
                return EnvelopeBuilder.error(
                    platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                    "知乎当前需要登录后才能获取问题回答，请先调用 login_zhihu 工具完成登录",
                )
            data = await asyncio.wait_for(
                searcher.get_question_answers(question_id, limit, max_content_length), timeout=30,
            )
            lifecycle.reset_failures(platform)
            return EnvelopeBuilder.success(platform, tool_name, data)
        except LoginRequiredError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.LOGIN_REQUIRED,
                "知乎当前需要登录后才能获取问题回答，请先调用 login_zhihu 工具完成登录",
            )
        except asyncio.TimeoutError:
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.SEARCH_TIMEOUT, "获取回答超时（30秒）",
            )
        except BrowserLaunchError as e:
            await lifecycle.destroy_searcher(platform)
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.BROWSER_INIT_FAILED, _browser_init_message(e),
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
        "登录成功后，search_zhihu 和 get_zhihu_question 都会复用登录态。"
    ),
)
async def login_zhihu() -> str:
    platform, tool_name = "zhihu", "login_zhihu"
    await lifecycle.rate_limiter.acquire(platform, tool_name)
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
        except BrowserLaunchError as e:
            logger.exception("知乎浏览器初始化异常")
            return EnvelopeBuilder.error(
                platform, tool_name, ErrorCode.BROWSER_INIT_FAILED, _browser_init_message(e),
            )
        except Exception as e:
            logger.exception("知乎登录异常")
            return EnvelopeBuilder.error(platform, tool_name, ErrorCode.UNKNOWN_ERROR, str(e))


# ============================================================
# Tool: 重置知乎登录态
# ============================================================

@mcp.tool(
    name="reset_zhihu_login",
    description="清空当前 profile 下的知乎浏览器状态目录，用于重新走首次登录流程。",
)
async def reset_zhihu_login() -> str:
    platform, tool_name = "zhihu", "reset_zhihu_login"
    lock = lifecycle.get_lock(platform)
    async with lock:
        data = await _clear_state("zhihu")
        return EnvelopeBuilder.success(platform, tool_name, data)


# ============================================================
# 优雅退出
# ============================================================

def _sync_cleanup():
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(lifecycle.cleanup())
        else:
            asyncio.run(lifecycle.cleanup())
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
    if len(sys.argv) > 1:
        if sys.argv[1] == "install-browser":
            raise SystemExit(subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"]))
        if sys.argv[1] == "doctor":
            raise SystemExit(_run_doctor())
        if sys.argv[1] == "clear-state":
            target = sys.argv[2] if len(sys.argv) > 2 else "all"
            raise SystemExit(_run_clear_state(target))
        if sys.argv[1] in {"-h", "--help", "help"}:
            print("Usage: stride28-search-mcp [install-browser|doctor|clear-state [xhs|zhihu|all]]")
            raise SystemExit(0)
    sys.stdout = _original_stdout
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
