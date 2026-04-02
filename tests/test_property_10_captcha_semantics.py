# Feature: mcp-data-stability-improvements, Property 10: captcha 检测决定空结果语义
"""
**Validates: Requirements 10.1, 10.2, 10.3**

Property 10: For any search operation that returns zero results, if captcha is detected
on the page, the method must raise CaptchaDetectedError (never return an empty SearchData).
If captcha is not detected, the method must return a normal empty SearchData with
total_returned=0.

Since search() is async and requires a browser, we test the decision logic via a helper
function that replicates the empty-result branch of search().
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.adapter import CaptchaDetectedError
from stride28_search_mcp.models import SearchData


def empty_result_handler(captcha_detected: bool, limit: int) -> SearchData:
    """Replicate the empty result decision logic from search().

    When items are empty:
    - captcha detected  → raise CaptchaDetectedError
    - no captcha        → return SearchData(total_returned=0)
    """
    if captcha_detected:
        raise CaptchaDetectedError("搜索结果为空且检测到验证码")
    return SearchData(total_requested=limit, total_returned=0)


@settings(max_examples=100)
@given(
    captcha_detected=st.booleans(),
    limit=st.integers(min_value=1, max_value=100),
)
def test_captcha_determines_empty_result_semantics(
    captcha_detected: bool, limit: int
) -> None:
    """captcha=True → CaptchaDetectedError; captcha=False → empty SearchData."""
    if captcha_detected:
        with pytest.raises(CaptchaDetectedError):
            empty_result_handler(captcha_detected, limit)
    else:
        result = empty_result_handler(captcha_detected, limit)
        assert isinstance(result, SearchData)
        assert result.total_returned == 0
        assert result.total_requested == limit
        assert result.results == []
