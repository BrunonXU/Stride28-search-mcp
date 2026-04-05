# Feature: mcp-data-stability-improvements, Property 7: 请求频率间隔保证（统一入口）
"""
**Validates: Requirements 7.1, 7.2, 7.3**

Property 7: For any sequence of acquire(platform, tool_name) calls on the same platform
where tool_name is not in the whitelist, the wall-clock time between consecutive calls
completing should be >= the configured min_interval. For whitelisted tool names (login,
health check), acquire should return immediately without imposing any delay.
"""
from __future__ import annotations

import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.lifecycle import RateLimiter, _WHITELIST_TOOLS

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_NON_WHITELIST_TOOLS = [
    "search_xiaohongshu",
    "get_note_detail",
    "search_zhihu",
    "get_zhihu_question",
]

whitelist_tool_st = st.sampled_from(sorted(_WHITELIST_TOOLS))
non_whitelist_tool_st = st.sampled_from(_NON_WHITELIST_TOOLS)
platform_st = st.sampled_from(["xiaohongshu", "zhihu"])
non_jitter_platform_st = st.just("zhihu")

# Windows asyncio.sleep has ~15.6 ms granularity, so we use intervals large
# enough that the tolerance stays a small fraction of the interval.
min_interval_st = st.floats(min_value=0.05, max_value=0.10)

# Tolerance for asyncio.sleep imprecision (one Windows timer tick ≈ 15.6 ms)
_TIMER_TOLERANCE = 0.016


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    tool_name=whitelist_tool_st,
    min_interval=min_interval_st,
    platform=platform_st,
)
@pytest.mark.asyncio
async def test_whitelisted_tool_skips_rate_limit(
    tool_name: str, min_interval: float, platform: str
) -> None:
    """Whitelisted tools should return immediately with no delay, even when called consecutively."""
    rl = RateLimiter(min_interval=min_interval)

    start = time.monotonic()
    await rl.acquire(platform, tool_name)
    await rl.acquire(platform, tool_name)
    elapsed = time.monotonic() - start

    # Two consecutive whitelisted calls should complete well under min_interval
    assert elapsed < min_interval, (
        f"Whitelisted tool '{tool_name}' was delayed: elapsed={elapsed:.4f}s, "
        f"min_interval={min_interval:.4f}s"
    )


@settings(max_examples=100, deadline=None)
@given(
    tool_name=non_whitelist_tool_st,
    min_interval=min_interval_st,
    platform=non_jitter_platform_st,
)
@pytest.mark.asyncio
async def test_non_whitelisted_tool_respects_min_interval(
    tool_name: str, min_interval: float, platform: str
) -> None:
    """Non-whitelisted tools on the same platform must wait >= min_interval between calls."""
    rl = RateLimiter(min_interval=min_interval)

    # First call — establishes the _last_request timestamp
    await rl.acquire(platform, tool_name)
    first_done = rl._last_request[platform]

    # Second call — the limiter should sleep until min_interval has elapsed
    await rl.acquire(platform, tool_name)
    second_done = rl._last_request[platform]

    # The recorded monotonic timestamps inside the limiter must be >= min_interval
    # apart, minus a small tolerance for OS timer granularity (Windows ~15.6 ms).
    gap = second_done - first_done
    assert gap >= min_interval - _TIMER_TOLERANCE, (
        f"Non-whitelisted tool '{tool_name}' interval too short: "
        f"gap={gap:.4f}s, min_interval={min_interval:.4f}s"
    )
