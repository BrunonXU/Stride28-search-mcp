from __future__ import annotations

import asyncio

import stride28_search_mcp.lifecycle as lifecycle_module
from stride28_search_mcp.lifecycle import LifecycleManager, RateLimiter


def test_rate_limiter_adds_xhs_jitter(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(lifecycle_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(lifecycle_module.random, "uniform", lambda start, end: 1.25)

    limiter = RateLimiter(min_interval=0.0, xhs_jitter_min=0.5, xhs_jitter_max=2.0)
    asyncio.run(limiter.acquire("xiaohongshu", "search_xiaohongshu"))

    assert sleeps == [1.25]


def test_rate_limiter_skips_login_tools(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(lifecycle_module.asyncio, "sleep", fake_sleep)

    limiter = RateLimiter(min_interval=5.0)
    asyncio.run(limiter.acquire("xiaohongshu", "login_xiaohongshu"))

    assert sleeps == []


def test_risk_cooldown_activates_and_expires(monkeypatch):
    monkeypatch.setenv("STRIDE28_XHS_RISK_COOLDOWN_SECONDS", "15")
    current = {"value": 100.0}

    monkeypatch.setattr(lifecycle_module.time, "monotonic", lambda: current["value"])

    manager = LifecycleManager()
    manager.activate_risk_cooldown("xiaohongshu", "captcha_detected")

    active = manager.get_risk_cooldown("xiaohongshu")
    assert active["active"] is True
    assert active["reason"] == "captcha_detected"
    assert active["remaining_seconds"] == 15

    current["value"] = 116.0
    expired = manager.get_risk_cooldown("xiaohongshu")
    assert expired["active"] is False
    assert expired["remaining_seconds"] == 0

