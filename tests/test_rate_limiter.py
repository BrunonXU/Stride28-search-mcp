# Unit tests for RateLimiter class (Task 2.1)
"""Tests for RateLimiter class in lifecycle.py.

Validates: Requirements 7.1, 7.2, 7.3, 7.4
"""
from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import patch

import pytest

from stride28_search_mcp.lifecycle import (
    LifecycleManager,
    RateLimiter,
    _WHITELIST_TOOLS,
)


def test_whitelist_contains_login_tools():
    """Whitelist includes login_xiaohongshu and login_zhihu."""
    assert "login_xiaohongshu" in _WHITELIST_TOOLS
    assert "login_zhihu" in _WHITELIST_TOOLS


def test_is_whitelisted_returns_true_for_login_tools():
    rl = RateLimiter()
    assert rl.is_whitelisted("login_xiaohongshu") is True
    assert rl.is_whitelisted("login_zhihu") is True


def test_is_whitelisted_returns_false_for_non_login_tools():
    rl = RateLimiter()
    assert rl.is_whitelisted("search_xiaohongshu") is False
    assert rl.is_whitelisted("get_note_detail") is False


def test_default_min_interval():
    rl = RateLimiter()
    assert rl._min_interval == 5.0


def test_custom_min_interval():
    rl = RateLimiter(min_interval=5.0)
    assert rl._min_interval == 5.0


@pytest.mark.asyncio
async def test_acquire_skips_whitelisted_tool():
    """Whitelisted tools should return immediately without delay."""
    rl = RateLimiter(min_interval=10.0)
    start = time.monotonic()
    await rl.acquire("xiaohongshu", "login_xiaohongshu")
    await rl.acquire("xiaohongshu", "login_xiaohongshu")
    elapsed = time.monotonic() - start
    # Should be nearly instant, well under 1 second
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_acquire_enforces_interval_for_non_whitelisted():
    """Non-whitelisted tools should wait min_interval between calls on same platform."""
    rl = RateLimiter(min_interval=0.2)
    await rl.acquire("zhihu", "search_zhihu")
    start = time.monotonic()
    await rl.acquire("zhihu", "search_zhihu")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.15  # Allow small tolerance


@pytest.mark.asyncio
async def test_acquire_different_platforms_independent():
    """Different platforms should have independent rate limiting."""
    rl = RateLimiter(min_interval=0.3)
    await rl.acquire("xiaohongshu", "search_xiaohongshu")
    start = time.monotonic()
    # Different platform should not wait
    await rl.acquire("zhihu", "search_zhihu")
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_lifecycle_manager_has_rate_limiter():
    """LifecycleManager should create a rate_limiter attribute."""
    with patch.dict(os.environ, {}, clear=False):
        lm = LifecycleManager()
        assert isinstance(lm.rate_limiter, RateLimiter)
        assert lm.rate_limiter._min_interval == 5.0


def test_lifecycle_manager_reads_env_var():
    """LifecycleManager should read STRIDE28_RATE_LIMIT_SECONDS from env."""
    with patch.dict(os.environ, {"STRIDE28_RATE_LIMIT_SECONDS": "5.0"}):
        lm = LifecycleManager()
        assert lm.rate_limiter._min_interval == 5.0
