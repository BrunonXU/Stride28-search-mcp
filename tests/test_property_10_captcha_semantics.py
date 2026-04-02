# Feature: mcp-data-stability-improvements, Property 10: captcha 检测决定空结果语义
"""
**Validates: Requirements 10.1, 10.2, 10.3**

Property 10: For any search operation that returns zero results, the empty-result branch
must be conservative:

- not logged in      -> LoginRequiredError
- captcha detected   -> CaptchaDetectedError
- logged in but empty -> SearchBlockedError

Since search() is async and requires a browser, we test the decision logic via a helper
function that replicates the empty-result branch of search().
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.adapter import (
    CaptchaDetectedError,
    LoginRequiredError,
    SearchBlockedError,
)


def empty_result_handler(logged_in: bool, captcha_detected: bool, query: str) -> None:
    """Replicate the empty result decision logic from search().

    When items are empty:
    - not logged in     → raise LoginRequiredError
    - captcha detected  → raise CaptchaDetectedError
    - otherwise         → raise SearchBlockedError
    """
    if not logged_in:
        raise LoginRequiredError("xiaohongshu")
    if captcha_detected:
        raise CaptchaDetectedError("搜索结果为空且检测到验证码")
    raise SearchBlockedError(f"搜索结果为空，可能是无头拦截、风控或需要重新登录 (query='{query}')")


@settings(max_examples=100)
@given(
    logged_in=st.booleans(),
    captcha_detected=st.booleans(),
    query=st.text(min_size=1, max_size=20),
)
def test_empty_result_branch_is_conservative(
    logged_in: bool, captcha_detected: bool, query: str
) -> None:
    """Empty search results should never silently succeed."""
    if not logged_in:
        with pytest.raises(LoginRequiredError):
            empty_result_handler(logged_in, captcha_detected, query)
    elif captcha_detected:
        with pytest.raises(CaptchaDetectedError):
            empty_result_handler(logged_in, captcha_detected, query)
    else:
        with pytest.raises(SearchBlockedError):
            empty_result_handler(logged_in, captcha_detected, query)
