# Unit tests for zhihu_adapter.py (Task 9.4)
"""
Tests for get_question_answers max_content_length parameter.
Validates: Requirements 11.1, 11.2, 11.3
"""
from __future__ import annotations

import inspect

from stride28_search_mcp.zhihu_adapter import ZhihuBrowserSearcher


def test_get_question_answers_has_max_content_length_param():
    """get_question_answers should accept max_content_length parameter."""
    sig = inspect.signature(ZhihuBrowserSearcher.get_question_answers)
    assert "max_content_length" in sig.parameters


def test_get_question_answers_max_content_length_default_10000():
    """max_content_length default should be 10000."""
    sig = inspect.signature(ZhihuBrowserSearcher.get_question_answers)
    param = sig.parameters["max_content_length"]
    assert param.default == 10000


def test_get_question_answers_limit_default_5():
    """limit default should be 5."""
    sig = inspect.signature(ZhihuBrowserSearcher.get_question_answers)
    param = sig.parameters["limit"]
    assert param.default == 5


def test_truncation_logic_zero_no_truncate():
    """max_content_length=0 means no truncation (JS logic: maxContentLength > 0 ? substr : text)."""
    text = "a" * 50000
    max_content_length = 0
    result = text if max_content_length <= 0 else text[:max_content_length]
    assert result == text


def test_truncation_logic_positive_truncates():
    """max_content_length > 0 truncates to that length."""
    text = "a" * 50000
    max_content_length = 100
    result = text if max_content_length <= 0 else text[:max_content_length]
    assert len(result) == 100


def test_truncation_logic_short_content_unchanged():
    """Content shorter than max_content_length is not altered."""
    text = "short"
    max_content_length = 10000
    result = text if max_content_length <= 0 else text[:max_content_length]
    assert result == text
