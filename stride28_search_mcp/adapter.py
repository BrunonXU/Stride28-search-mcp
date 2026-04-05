"""MCP 小红书搜索适配器 —— 纯浏览器方案

使用 Playwright Chromium 浏览器内操作，不调 API，不需要签名。
搜索通过导航到搜索页 + 提取 __INITIAL_STATE__ 实现。
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional

from playwright.async_api import async_playwright, BrowserContext, Page

from stride28_search_mcp.models import SearchResultItem, SearchData
from stride28_search_mcp.state import get_browser_data_dir, get_platform_headless

try:
    from playwright_stealth import stealth_async
    _HAS_STEALTH = True
except ImportError:
    _HAS_STEALTH = False

logger = logging.getLogger(__name__)

_XHS_INDEX = "https://www.xiaohongshu.com/explore"
_LOGIN_COOKIE_NAMES = ("galaxy_creator_session_id", "customer-sso-sid")
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


class LoginRequiredError(Exception):
    def __init__(self, platform: str = "xiaohongshu"):
        super().__init__(f"{platform} 未登录")
        self.platform = platform


class BrowserCrashError(Exception):
    def __init__(self, detail: str = ""):
        super().__init__(f"浏览器异常: {detail}")


class BrowserLaunchError(Exception):
    def __init__(self, detail: str = ""):
        super().__init__(f"浏览器启动失败: {detail}")


class CaptchaDetectedError(Exception):
    """验证码拦截异常 (R10)"""
    def __init__(self, detail: str = ""):
        super().__init__(f"验证码拦截: {detail}")


class SearchBlockedError(Exception):
    """搜索被拦截或结果结构异常。"""
    def __init__(self, detail: str = ""):
        super().__init__(f"搜索被拦截: {detail}")


@dataclass(slots=True)
class XhsAuthResult:
    logged_in: bool
    source: str = "none"
    reason: str = ""
    login_cookie_names: List[str] = field(default_factory=list)


class XhsBrowserSearcher:
    """纯浏览器小红书搜索器（使用 Chromium）"""

    def __init__(self):
        self._pw_cm = None
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._initialized = False
        self._browser_data_dir = get_browser_data_dir("xhs")
        self._last_auth_result: Optional[XhsAuthResult] = None

    async def _launch_context(self, headless: bool = True) -> BrowserContext:
        """启动 Chromium persistent context"""
        try:
            self._browser_data_dir.mkdir(parents=True, exist_ok=True)
            self._pw_cm = async_playwright()
            self._playwright = await self._pw_cm.start()
            return await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._browser_data_dir),
                headless=headless,
                viewport={"width": 1920, "height": 1080},
                user_agent=_UA,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                ignore_default_args=["--enable-automation"],
            )
        except Exception as exc:
            raise BrowserLaunchError(str(exc)) from exc

    async def init_browser(self, headless: bool = True):
        if self._initialized:
            return
        logger.info("MCP: 初始化小红书浏览器 (headless=%s)...", headless)
        self._context = await self._launch_context(headless)
        self._page = await self._context.new_page()
        if _HAS_STEALTH:
            await stealth_async(self._page)
        self._initialized = True
        logger.info("MCP: 小红书浏览器就绪")

    async def _get_login_cookie_names(self) -> List[str]:
        if not self._context:
            return []
        try:
            cookies = await self._context.cookies()
        except Exception as exc:
            logger.warning("MCP: 读取 Cookie 失败: %s", exc)
            return []

        return sorted(
            {
                cookie.get("name", "")
                for cookie in cookies
                if cookie.get("name") in _LOGIN_COOKIE_NAMES and cookie.get("value")
            }
        )

    async def _fetch_selfinfo_state(self) -> dict:
        if not self._page:
            return {"success": False, "reason": "page_unavailable"}

        try:
            return await self._page.evaluate("""async () => {
                try {
                    const response = await fetch('/api/sns/web/v1/user/selfinfo', {
                        credentials: 'include'
                    });
                    const text = await response.text();
                    let data = null;
                    let parseable = false;
                    try {
                        data = text ? JSON.parse(text) : null;
                        parseable = !!data;
                    } catch (error) {
                        parseable = false;
                    }
                    const success = !!(
                        data && (
                            data.success === true ||
                            (data.result && data.result.success === true) ||
                            (data.data && data.data.user_id)
                        )
                    );
                    return {
                        success,
                        status: response.status,
                        parseable,
                        body_prefix: (text || '').slice(0, 160),
                    };
                } catch (error) {
                    return {
                        success: false,
                        reason: String(error),
                        parseable: false,
                        status: 0,
                        body_prefix: '',
                    };
                }
            }""")
        except Exception as exc:
            logger.warning("MCP: selfinfo API 检测失败: %s", exc)
            return {"success": False, "reason": str(exc), "parseable": False, "status": 0}

    async def _detect_auth_result(self) -> XhsAuthResult:
        if not self._page or not self._context:
            result = XhsAuthResult(
                logged_in=False,
                source="uninitialized",
                reason="browser_not_ready",
            )
            self._last_auth_result = result
            return result

        login_cookie_names = await self._get_login_cookie_names()
        selfinfo_state = await self._fetch_selfinfo_state()

        if selfinfo_state.get("success"):
            result = XhsAuthResult(
                logged_in=True,
                source="selfinfo_api",
                reason=f"status={selfinfo_state.get('status', 0)}",
                login_cookie_names=login_cookie_names,
            )
            self._last_auth_result = result
            return result

        if login_cookie_names:
            result = XhsAuthResult(
                logged_in=True,
                source="login_cookie",
                reason="matched_whitelisted_login_cookie",
                login_cookie_names=login_cookie_names,
            )
            self._last_auth_result = result
            return result

        # 方法3: DOM 元素检测（参考 xpzouying/xiaohongshu-mcp）
        # 只用精确的登录后才出现的 selector，不用宽泛的 avatar
        try:
            user_channel = await self._page.query_selector(
                '.main-container .user .link-wrapper .channel'
            )
            if user_channel:
                result = XhsAuthResult(
                    logged_in=True,
                    source="dom_user_channel",
                    reason="login_element_found",
                    login_cookie_names=login_cookie_names,
                )
                self._last_auth_result = result
                return result
        except Exception as e:
            logger.warning("MCP: DOM 登录检测异常: %s", e)

        reason = selfinfo_state.get("reason", "").strip()
        if not reason:
            if selfinfo_state.get("parseable") is False and selfinfo_state.get("body_prefix"):
                preview = str(selfinfo_state.get("body_prefix", "")).strip()
                reason = f"selfinfo_non_json:{preview[:80]}"
            else:
                reason = f"selfinfo_status={selfinfo_state.get('status', 0)}"

        result = XhsAuthResult(
            logged_in=False,
            source="none",
            reason=reason,
            login_cookie_names=login_cookie_names,
        )
        self._last_auth_result = result
        return result

    async def _get_auth_result(self, force_refresh: bool = False) -> XhsAuthResult:
        if self._last_auth_result is not None and not force_refresh:
            return self._last_auth_result

        result = await self._detect_auth_result()
        logger.info(
            "MCP: 登录检测结果 logged_in=%s source=%s cookies=%s reason=%s",
            result.logged_in,
            result.source,
            result.login_cookie_names,
            result.reason,
        )
        return result

    async def _is_logged_in(self) -> bool:
        return (await self._get_auth_result(force_refresh=True)).logged_in

    async def check_auth(self) -> bool:
        if not self._browser_data_dir.exists():
            return False
        try:
            await self.init_browser(headless=get_platform_headless("xhs"))
            self._last_auth_result = None
            if self._page and self._page.url.startswith("https://www.xiaohongshu.com"):
                auth_result = await self._get_auth_result(force_refresh=True)
            else:
                login_cookie_names = await self._get_login_cookie_names()
                auth_result = XhsAuthResult(
                    logged_in=bool(login_cookie_names),
                    source="login_cookie" if login_cookie_names else "none",
                    reason="lightweight_cookie_check",
                    login_cookie_names=login_cookie_names,
                )
                self._last_auth_result = auth_result
            logger.info(
                "MCP: check_auth 已登录=%s source=%s reason=%s",
                auth_result.logged_in,
                auth_result.source,
                auth_result.reason,
            )
            return auth_result.logged_in
        except Exception as e:
            logger.warning("MCP: check_auth 异常: %s", e)
            raise BrowserLaunchError(str(e)) from e

    async def _check_captcha(self) -> bool:
        """检查页面是否存在验证码提示"""
        try:
            captcha = await self._page.query_selector(
                '#captcha, .captcha-container, [class*="verify"], [class*="captcha"]'
            )
            return captcha is not None
        except Exception:
            return False

    async def _raise_for_empty_results(
        self,
        query: str,
        auth_result: Optional[XhsAuthResult] = None,
    ) -> None:
        auth_result = auth_result or await self._get_auth_result(force_refresh=True)
        if not auth_result.logged_in:
            raise LoginRequiredError("xiaohongshu")
        if await self._check_captcha():
            raise CaptchaDetectedError("搜索结果为空且检测到验证码")
        raise SearchBlockedError(
            f"搜索结果为空，可能是无头拦截、风控或需要重新登录 (query='{query}')"
        )

    async def _raise_for_missing_note_detail(
        self,
        note_id: str,
        auth_result: Optional[XhsAuthResult] = None,
    ) -> None:
        auth_result = auth_result or await self._get_auth_result(force_refresh=True)
        if not auth_result.logged_in:
            raise LoginRequiredError("xiaohongshu")
        if await self._check_captcha():
            raise CaptchaDetectedError("笔记详情为空且检测到验证码")
        raise SearchBlockedError(
            f"笔记详情为空，可能是风控、页面结构变化或需要重新登录 (note_id='{note_id}')"
        )

    async def search(self, query: str, limit: int = 10, note_type: str = "all") -> SearchData:
        if not self._initialized:
            await self.init_browser(headless=get_platform_headless("xhs"))

        search_url = self._make_search_url(query, note_type)
        logger.info("MCP: 导航到搜索页: %s", search_url)
        self._last_auth_result = None
        await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

        try:
            await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        try:
            await self._page.wait_for_function(
                """() => {
                    if (!window.__INITIAL_STATE__ || !window.__INITIAL_STATE__.search) return false;
                    const feeds = window.__INITIAL_STATE__.search.feeds;
                    if (!feeds) return false;
                    const data = feeds.value !== undefined ? feeds.value : feeds._value;
                    return data && data.length > 0;
                }""",
                timeout=15000,
            )
        except Exception:
            logger.warning("MCP: __INITIAL_STATE__.search.feeds 未加载或为空，再等 3 秒...")
            await self._page.wait_for_timeout(3000)

        raw_json = await self._page.evaluate("""() => {
            if (window.__INITIAL_STATE__ &&
                window.__INITIAL_STATE__.search &&
                window.__INITIAL_STATE__.search.feeds) {
                const feeds = window.__INITIAL_STATE__.search.feeds;
                const feedsData = feeds.value !== undefined ? feeds.value : feeds._value;
                if (feedsData) return JSON.stringify(feedsData);
            }
            return "";
        }""")

        if not raw_json:
            logger.warning("MCP: 搜索结果为空 (query='%s')", query)
            await self._raise_for_empty_results(
                query,
                auth_result=await self._get_auth_result(force_refresh=True),
            )

        try:
            feeds = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error("MCP: feeds JSON 解析失败: %s", e)
            raise SearchBlockedError("搜索结果结构解析失败，可能是页面结构变化或浏览器被拦截") from e

        items = self._parse_feeds(feeds, limit)
        if not items:
            logger.warning("MCP: feeds 已加载但解析后为空 (query='%s')", query)
            await self._raise_for_empty_results(
                query,
                auth_result=await self._get_auth_result(force_refresh=True),
            )
        logger.info("MCP: 搜索完成，返回 %d 条结果 (query='%s')", len(items), query)
        return SearchData(results=items, total_requested=limit, total_returned=len(items))

    async def login(self, timeout: float = 300):
        await self.close()
        logger.info("=" * 50)
        logger.info("MCP: 需要登录小红书，即将弹出浏览器窗口")
        logger.info("请手动登录，登录成功后自动检测（最多等 5 分钟）")
        logger.info("=" * 50)

        self._context = await self._launch_context(headless=False)
        self._page = await self._context.new_page()
        await self._page.goto(_XHS_INDEX, wait_until="domcontentloaded", timeout=30000)

        logged_in = False
        max_polls = int(timeout / 5)
        for i in range(max_polls):
            await self._page.wait_for_timeout(5000)
            try:
                auth_result = await self._get_auth_result(force_refresh=True)
                is_real_login = auth_result.logged_in
            except Exception as e:
                logger.warning("MCP: login 严格检测异常: %s", e)
                is_real_login = False
            if is_real_login:
                logger.info("MCP: 严格登录验证通过，登录成功！")
                logged_in = True
                break
            if i % 6 == 0:
                logger.info("等待登录中... (%ds / %ds)", (i + 1) * 5, int(timeout))

        if not logged_in:
            await self.close()
            raise RuntimeError(f"登录超时（{int(timeout)}秒）")
        await self.close()

    async def close(self):
        self._initialized = False
        self._page = None
        self._last_auth_result = None
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._pw_cm:
                await self._pw_cm.__aexit__(None, None, None)
                self._playwright = None
                self._pw_cm = None
        except Exception:
            pass

    _NOTE_TYPE_MAP = {"normal": "1", "video": "2"}

    @staticmethod
    def _make_search_url(keyword: str, note_type: str = "all") -> str:
        params = {"keyword": keyword, "source": "web_explore_feed"}
        if note_type in XhsBrowserSearcher._NOTE_TYPE_MAP:
            params["type"] = XhsBrowserSearcher._NOTE_TYPE_MAP[note_type]
        return f"https://www.xiaohongshu.com/search_result?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_feeds(feeds: list, limit: int) -> List[SearchResultItem]:
        items = []
        for feed in feeds:
            if len(items) >= limit:
                break
            try:
                note_card = feed.get("note_card") or feed.get("noteCard") or {}
                note_id = feed.get("id") or note_card.get("noteId") or ""
                xsec_token = feed.get("xsec_token") or feed.get("xsecToken") or ""
                display_title = note_card.get("display_title") or note_card.get("displayTitle") or ""
                if not display_title.strip():
                    continue  # R1: 跳过空标题条目（广告位等）
                interact_info = note_card.get("interact_info") or note_card.get("interactInfo") or {}
                liked_count = interact_info.get("liked_count") or interact_info.get("likedCount") or "0"
                user = note_card.get("user") or {}
                nickname = user.get("nickname") or user.get("nick_name") or ""
                cover = note_card.get("cover") or {}
                cover_url = cover.get("url_default") or cover.get("urlDefault") or ""
                note_type = note_card.get("type") or "normal"
                publish_time = str(note_card.get("time") or note_card.get("publishTime") or "")
                url = (
                    f"https://www.xiaohongshu.com/explore/{note_id}"
                    f"?xsec_token={xsec_token}&xsec_source=pc_search"
                ) if note_id and xsec_token else (
                    f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
                )
                items.append(SearchResultItem(
                    id=str(note_id), title=display_title, url=url,
                    snippet=display_title, cover_url=cover_url, author=nickname,
                    likes=int(str(liked_count).replace("+", "").replace("万", "0000")) if liked_count else 0,
                    xsec_token=xsec_token, note_type=note_type,
                    publish_time=publish_time,
                ))
            except Exception as e:
                logger.warning("MCP: 解析 feed 失败: %s", e)
                continue
        return items

    async def _extract_comments_from_dom(self, max_sub_per_comment: int = 10) -> List["CommentItem"]:
        """从 DOM 提取当前页面所有可见评论"""
        from stride28_search_mcp.models import CommentItem
        comments = []
        try:
            comment_elements = await self._page.query_selector_all('.comment-item, .CommentItem, [class*="commentItem"]')
            for el in comment_elements:
                try:
                    text_el = await el.query_selector('.content, .comment-content, [class*="content"]')
                    text = await text_el.inner_text() if text_el else ""
                    author_el = await el.query_selector('.author, .nickname, [class*="author"]')
                    author = await author_el.inner_text() if author_el else ""
                    if text.strip():
                        comments.append(CommentItem(text=text.strip(), author=author.strip()))
                except Exception:
                    continue
        except Exception as e:
            logger.warning("MCP: DOM 评论提取异常: %s", e)
        return comments

    async def _load_more_comments(self, max_comments: int = 50,
                                   max_duration: float = 30.0,
                                   max_empty_loads: int = 3,
                                   max_selector_failures: int = 3) -> List["CommentItem"]:
        """滚动加载更多评论，带硬停止条件"""
        import time
        comments = []
        start_time = time.monotonic()
        consecutive_empty = 0
        selector_failures = 0
        stop_reason = None

        for _ in range(max(max_comments // 5, 1)):
            if len(comments) >= max_comments:
                break

            # 硬停止条件 1: 总耗时
            elapsed = time.monotonic() - start_time
            if elapsed >= max_duration:
                stop_reason = f"max_duration={max_duration}s exceeded (elapsed={elapsed:.1f}s)"
                break

            try:
                more_btn = await self._page.query_selector(
                    'text="查看更多评论", text="展开更多评论"'
                )
                if more_btn:
                    await more_btn.click()
                    await self._page.wait_for_timeout(1500)
                    selector_failures = 0
                else:
                    # 硬停止条件 3: selector 失效
                    selector_failures += 1
                    if selector_failures >= max_selector_failures:
                        stop_reason = f"selector_failures={selector_failures} reached limit"
                        break
                    await self._page.evaluate(
                        'document.querySelector(".comments-container, .comment-list, [class*=comment]")?.scrollBy(0, 500)'
                    )
                    await self._page.wait_for_timeout(1000)

                new_comments = await self._extract_comments_from_dom()
                if len(new_comments) <= len(comments):
                    # 硬停止条件 2: 连续空加载
                    consecutive_empty += 1
                    if consecutive_empty >= max_empty_loads:
                        stop_reason = f"consecutive_empty_loads={consecutive_empty} reached limit"
                        break
                else:
                    consecutive_empty = 0
                comments = new_comments
            except Exception as e:
                logger.warning("MCP: 评论加载异常: %s", e)
                stop_reason = f"exception: {e}"
                break

        if stop_reason:
            logger.warning("MCP: 评论加载硬停止 - %s, 已加载 %d 条", stop_reason, len(comments))
        return comments[:max_comments]

    async def get_note_detail(self, note_id: str, xsec_token: str = "", max_comments: int = 10) -> "NoteDetail":
        from stride28_search_mcp.models import NoteDetail, CommentItem
        if not self._initialized:
            await self.init_browser(headless=get_platform_headless("xhs"))

        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        if xsec_token:
            url += f"?xsec_token={xsec_token}&xsec_source=pc_search"

        logger.info("MCP: 导航到笔记详情: %s", url)
        self._last_auth_result = None
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        try:
            await self._page.wait_for_function(
                """() => {
                    return window.__INITIAL_STATE__ &&
                           window.__INITIAL_STATE__.note &&
                           window.__INITIAL_STATE__.note.noteDetailMap;
                }""", timeout=10000)
        except Exception:
            await self._page.wait_for_timeout(3000)

        raw_json = await self._page.evaluate("""(noteId) => {
            try {
                const state = window.__INITIAL_STATE__;
                if (!state || !state.note || !state.note.noteDetailMap) return "";
                const detailMap = state.note.noteDetailMap;
                let detail = detailMap[noteId];
                if (!detail) {
                    const keys = Object.keys(detailMap);
                    if (keys.length > 0) detail = detailMap[keys[0]];
                }
                return detail ? JSON.stringify(detail) : "";
            } catch(e) { return ""; }
        }""", note_id)

        auth_result = await self._get_auth_result(force_refresh=True)
        if not raw_json:
            await self._raise_for_missing_note_detail(note_id, auth_result=auth_result)
        try:
            detail = json.loads(raw_json)
        except json.JSONDecodeError:
            raise SearchBlockedError(
                f"笔记详情结构解析失败，可能是页面结构变化或被拦截 (note_id='{note_id}')"
            )

        data = detail.get("note") or detail
        title = data.get("title") or ""
        desc = data.get("desc") or ""
        image_list = data.get("imageList") or data.get("image_list") or []
        image_urls = [img.get("urlDefault") or img.get("url_default") or img.get("url") or "" for img in image_list]
        image_urls = [u for u in image_urls if u]
        interact = data.get("interactInfo") or data.get("interact_info") or {}
        likes = self._safe_int(interact.get("likedCount") or interact.get("liked_count") or 0)
        collected = self._safe_int(interact.get("collectedCount") or interact.get("collected_count") or 0)
        comments_count = self._safe_int(interact.get("commentCount") or interact.get("comment_count") or 0)
        shares = self._safe_int(interact.get("shareCount") or interact.get("share_count") or 0)
        user = data.get("user") or {}
        author = user.get("nickname") or user.get("nick_name") or ""
        tag_list = data.get("tagList") or data.get("tag_list") or []
        tags = [t.get("name", "") for t in tag_list if t.get("name")]
        note_type = data.get("type") or "normal"
        publish_time = str(data.get("time") or data.get("publishTime") or "")

        # 先从 __INITIAL_STATE__ 提取首屏评论
        comments = []
        try:
            comments_data = detail.get("comments") or {}
            for c in (comments_data.get("list") or [])[:max_comments]:
                text = c.get("content") or ""
                c_user = c.get("userInfo") or c.get("user_info") or {}
                c_author = c_user.get("nickname") or ""
                c_likes = self._safe_int(c.get("likeCount") or c.get("like_count") or 0)
                if text:
                    comments.append(CommentItem(text=text, author=c_author, likes=c_likes))
                for sc in (c.get("subComments") or c.get("sub_comments") or [])[:5]:
                    if len(comments) >= max_comments:
                        break
                    sc_text = sc.get("content") or ""
                    sc_user = sc.get("userInfo") or sc.get("user_info") or {}
                    if sc_text:
                        comments.append(CommentItem(
                            text=sc_text, author=sc_user.get("nickname", ""),
                            likes=self._safe_int(sc.get("likeCount") or sc.get("like_count") or 0),
                        ))
        except Exception as e:
            logger.warning("MCP: 评论提取失败: %s", e)

        # 如果首屏评论不够，尝试翻页加载更多
        if max_comments > 10 and len(comments) < max_comments:
            try:
                more_comments = await self._load_more_comments(
                    max_comments=max_comments,
                )
                if len(more_comments) > len(comments):
                    comments = more_comments
            except Exception as e:
                logger.warning("MCP: 评论翻页加载失败: %s", e)

        comments = comments[:max_comments]

        return NoteDetail(
            id=note_id, title=title, url=url, author=author, content=desc,
            likes=likes, collected=collected, comments_count=comments_count,
            shares=shares, image_urls=image_urls, tags=tags,
            top_comments=comments, note_type=note_type,
            publish_time=publish_time,
        )

    @staticmethod
    def _safe_int(v) -> int:
        try:
            s = str(v).replace("+", "").replace("万", "0000")
            return int(float(s))
        except (ValueError, TypeError):
            return 0
