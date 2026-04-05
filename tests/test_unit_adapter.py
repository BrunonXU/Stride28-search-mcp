# Unit tests for adapter.py (Task 9.2)
"""
Tests for _parse_feeds, _make_search_url, CaptchaDetectedError.
Validates: Requirements 1.1, 1.2, 4.2, 4.3, 4.4, 10.1
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from stride28_search_mcp.adapter import (
    CaptchaDetectedError,
    LoginRequiredError,
    SearchBlockedError,
    XhsBrowserSearcher,
)


def _make_feed(title: str = "test", note_id: str = "123") -> dict:
    return {
        "id": note_id,
        "xsec_token": "tok",
        "note_card": {
            "display_title": title,
            "user": {"nickname": "user"},
            "interact_info": {"liked_count": "10"},
            "cover": {"url_default": ""},
            "type": "normal",
        },
    }


# -- R1: 过滤空标题 --

def test_parse_feeds_all_empty_titles_returns_empty():
    """All empty title feeds → empty result."""
    feeds = [_make_feed(""), _make_feed("   "), _make_feed("")]
    result = XhsBrowserSearcher._parse_feeds(feeds, limit=10)
    assert result == []


def test_parse_feeds_mixed_keeps_only_titled():
    """Mixed feeds → only non-empty titles kept."""
    feeds = [_make_feed("good", "1"), _make_feed("", "2"), _make_feed("also good", "3")]
    result = XhsBrowserSearcher._parse_feeds(feeds, limit=10)
    assert len(result) == 2
    assert result[0].title == "good"
    assert result[1].title == "also good"


def test_parse_feeds_respects_limit_after_filtering():
    """Limit is applied after filtering empty titles."""
    feeds = [_make_feed("", "0")] * 5 + [_make_feed(f"t{i}", str(i)) for i in range(10)]
    result = XhsBrowserSearcher._parse_feeds(feeds, limit=3)
    assert len(result) == 3


# -- R4: note_type URL 参数 --

def test_make_search_url_all_no_type_param():
    """note_type='all' → no type param in URL."""
    url = XhsBrowserSearcher._make_search_url("test", "all")
    assert "type=" not in url


def test_make_search_url_normal_type_1():
    """note_type='normal' → type=1 in URL."""
    url = XhsBrowserSearcher._make_search_url("test", "normal")
    assert "type=1" in url


def test_make_search_url_video_type_2():
    """note_type='video' → type=2 in URL."""
    url = XhsBrowserSearcher._make_search_url("test", "video")
    assert "type=2" in url


def test_make_search_url_invalid_note_type_no_type_param():
    """Invalid note_type → no type param (same as 'all')."""
    url = XhsBrowserSearcher._make_search_url("test", "invalid")
    assert "type=" not in url


# -- R10: CaptchaDetectedError --

def test_captcha_detected_error_is_exception():
    """CaptchaDetectedError should be an Exception subclass."""
    assert issubclass(CaptchaDetectedError, Exception)


def test_captcha_detected_error_message():
    """CaptchaDetectedError message should contain detail."""
    err = CaptchaDetectedError("test detail")
    assert "test detail" in str(err)


def test_search_blocked_error_message():
    """SearchBlockedError message should contain detail."""
    err = SearchBlockedError("blocked detail")
    assert "blocked detail" in str(err)


class _FakeContext:
    def __init__(self, cookies: list[dict]):
        self._cookies = cookies

    async def cookies(self):
        return self._cookies


def test_auth_result_rejects_visitor_cookie_only(monkeypatch):
    searcher = XhsBrowserSearcher()
    searcher._page = object()
    searcher._context = _FakeContext(
        [{"name": "web_session", "value": "visitor-only-cookie-value"}]
    )

    async def fake_selfinfo():
        return {
            "success": False,
            "parseable": False,
            "status": 200,
            "body_prefix": "create invoker failed, service: jarvis-gateway-default",
        }

    monkeypatch.setattr(searcher, "_fetch_selfinfo_state", fake_selfinfo)

    auth = asyncio.run(searcher._get_auth_result(force_refresh=True))
    assert auth.logged_in is False
    assert auth.login_cookie_names == []
    assert auth.source == "none"


def test_auth_result_accepts_whitelisted_login_cookie(monkeypatch):
    searcher = XhsBrowserSearcher()
    searcher._page = object()
    searcher._context = _FakeContext(
        [{"name": "customer-sso-sid", "value": "real-login-cookie"}]
    )

    async def fake_selfinfo():
        return {"success": False, "parseable": False, "status": 0, "body_prefix": ""}

    monkeypatch.setattr(searcher, "_fetch_selfinfo_state", fake_selfinfo)

    auth = asyncio.run(searcher._get_auth_result(force_refresh=True))
    assert auth.logged_in is True
    assert auth.source == "login_cookie"
    assert auth.login_cookie_names == ["customer-sso-sid"]


def test_auth_result_accepts_selfinfo_success(monkeypatch):
    searcher = XhsBrowserSearcher()
    searcher._page = object()
    searcher._context = _FakeContext([])

    async def fake_selfinfo():
        return {"success": True, "parseable": True, "status": 200, "body_prefix": "{}"}

    monkeypatch.setattr(searcher, "_fetch_selfinfo_state", fake_selfinfo)

    auth = asyncio.run(searcher._get_auth_result(force_refresh=True))
    assert auth.logged_in is True
    assert auth.source == "selfinfo_api"


def test_raise_for_empty_results_returns_login_required(monkeypatch):
    searcher = XhsBrowserSearcher()

    async def fake_auth(force_refresh: bool = False):
        return type("Auth", (), {"logged_in": False})()

    monkeypatch.setattr(searcher, "_get_auth_result", fake_auth)

    with pytest.raises(LoginRequiredError):
        asyncio.run(searcher._raise_for_empty_results("agent"))


def test_raise_for_empty_results_returns_captcha(monkeypatch):
    searcher = XhsBrowserSearcher()

    async def fake_auth(force_refresh: bool = False):
        return type("Auth", (), {"logged_in": True})()

    async def fake_captcha():
        return True

    monkeypatch.setattr(searcher, "_get_auth_result", fake_auth)
    monkeypatch.setattr(searcher, "_check_captcha", fake_captcha)

    with pytest.raises(CaptchaDetectedError):
        asyncio.run(searcher._raise_for_empty_results("agent"))


def test_parse_snapshot_fixture_returns_expected_titles():
    snapshot_path = Path(__file__).resolve().parent / "fixtures" / "xhs_search_feeds_snapshot.json"
    feeds = json.loads(snapshot_path.read_text(encoding="utf-8"))
    result = XhsBrowserSearcher._parse_feeds(feeds, limit=10)
    assert [item.title for item in result] == ["RAG 面试题整理", "Agent 工作流模板"]
