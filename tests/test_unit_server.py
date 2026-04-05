from __future__ import annotations

import asyncio
import json

from stride28_search_mcp.adapter import SearchBlockedError
from stride28_search_mcp.server import (
    _clear_state_targets,
    lifecycle,
    search_xiaohongshu,
    search_zhihu,
)


async def _noop(*args, **kwargs):
    return None


class _FakeXhsLoginRequiredSearcher:
    async def check_auth(self):
        return False


class _FakeXhsBlockedSearcher:
    async def check_auth(self):
        return True

    async def search(self, query, limit, note_type):
        raise SearchBlockedError("blocked in test")


class _FakeXhsSearchOkSearcher:
    async def check_auth(self):
        return True

    async def search(self, query, limit, note_type):
        from stride28_search_mcp.models import SearchData

        return SearchData(results=[], total_requested=limit, total_returned=0)


class _FakeZhihuLoginRequiredSearcher:
    async def check_auth(self):
        return False


def test_clear_state_targets_all():
    assert _clear_state_targets("all") == [
        ("xiaohongshu", "xhs"),
        ("zhihu", "zhihu"),
    ]


def test_search_xiaohongshu_returns_login_required_when_auth_missing(monkeypatch):
    async def fake_get_searcher(platform):
        return _FakeXhsLoginRequiredSearcher()

    monkeypatch.setattr(lifecycle.rate_limiter, "acquire", _noop)
    monkeypatch.setattr(lifecycle, "is_crashed", lambda platform: False)
    monkeypatch.setattr(lifecycle, "get_searcher", fake_get_searcher)
    monkeypatch.setattr(lifecycle, "get_risk_cooldown", lambda platform: {"active": False})

    envelope = json.loads(asyncio.run(search_xiaohongshu("agent", 5)))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "login_required"


def test_search_xiaohongshu_returns_search_blocked(monkeypatch):
    async def fake_get_searcher(platform):
        return _FakeXhsBlockedSearcher()

    activated = []

    monkeypatch.setattr(lifecycle.rate_limiter, "acquire", _noop)
    monkeypatch.setattr(lifecycle, "is_crashed", lambda platform: False)
    monkeypatch.setattr(lifecycle, "get_searcher", fake_get_searcher)
    monkeypatch.setattr(lifecycle, "get_risk_cooldown", lambda platform: {"active": False})
    monkeypatch.setattr(
        lifecycle,
        "activate_risk_cooldown",
        lambda platform, reason="": activated.append((platform, reason)),
    )

    envelope = json.loads(asyncio.run(search_xiaohongshu("agent", 5)))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "search_blocked"
    assert activated == [("xiaohongshu", "search_blocked")]


def test_search_xiaohongshu_returns_risk_cooldown_when_active(monkeypatch):
    monkeypatch.setattr(lifecycle, "get_risk_cooldown", lambda platform: {
        "active": True,
        "remaining_seconds": 180,
        "reason": "captcha_detected",
    })
    monkeypatch.setattr(lifecycle.rate_limiter, "acquire", _noop)

    envelope = json.loads(asyncio.run(search_xiaohongshu("agent", 5)))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "risk_cooldown_active"


def test_search_zhihu_returns_login_required_when_auth_missing(monkeypatch):
    async def fake_get_searcher(platform):
        return _FakeZhihuLoginRequiredSearcher()

    monkeypatch.setattr(lifecycle.rate_limiter, "acquire", _noop)
    monkeypatch.setattr(lifecycle, "is_crashed", lambda platform: False)
    monkeypatch.setattr(lifecycle, "get_searcher", fake_get_searcher)

    envelope = json.loads(asyncio.run(search_zhihu("agent", 5)))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "login_required"
