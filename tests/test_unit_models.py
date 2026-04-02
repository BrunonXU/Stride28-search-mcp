# Unit tests for models.py (Task 9.1)
"""
Tests for SearchResultItem, ErrorCode, _RETRYABLE_MAP.
Validates: Requirements 2.3, 6.3, 8.4, 8.5
"""
from __future__ import annotations

import json

from stride28_search_mcp.models import (
    EnvelopeBuilder,
    ErrorCode,
    SearchResultItem,
    _RETRYABLE_MAP,
)


def test_search_result_item_has_publish_time_default_empty():
    """SearchResultItem should have publish_time field defaulting to empty string."""
    item = SearchResultItem()
    assert item.publish_time == ""


def test_search_result_item_publish_time_set():
    """SearchResultItem.publish_time can be set."""
    item = SearchResultItem(publish_time="2024-01-15")
    assert item.publish_time == "2024-01-15"


def test_error_code_has_captcha_detected():
    """ErrorCode enum should contain CAPTCHA_DETECTED."""
    assert hasattr(ErrorCode, "CAPTCHA_DETECTED")
    assert ErrorCode.CAPTCHA_DETECTED.value == "captcha_detected"


def test_retryable_map_captcha_detected_false():
    """CAPTCHA_DETECTED should be retryable=false."""
    assert _RETRYABLE_MAP[ErrorCode.CAPTCHA_DETECTED] is False


def test_retryable_map_browser_crashed_false():
    """BROWSER_CRASHED should be retryable=false."""
    assert _RETRYABLE_MAP[ErrorCode.BROWSER_CRASHED] is False


def test_retryable_map_search_timeout_true():
    """SEARCH_TIMEOUT should be retryable=true."""
    assert _RETRYABLE_MAP[ErrorCode.SEARCH_TIMEOUT] is True


def test_retryable_map_login_timeout_true():
    """LOGIN_TIMEOUT should be retryable=true."""
    assert _RETRYABLE_MAP[ErrorCode.LOGIN_TIMEOUT] is True


def test_retryable_map_login_required_false():
    """LOGIN_REQUIRED should be retryable=false."""
    assert _RETRYABLE_MAP[ErrorCode.LOGIN_REQUIRED] is False


def test_retryable_map_covers_all_error_codes():
    """Every ErrorCode should have an entry in _RETRYABLE_MAP."""
    for code in ErrorCode:
        assert code in _RETRYABLE_MAP, f"{code} missing from _RETRYABLE_MAP"


def test_error_envelope_retryable_field_present():
    """Error envelope should contain retryable field."""
    envelope_json = EnvelopeBuilder.error("test", "test_tool", ErrorCode.SEARCH_TIMEOUT, "timeout")
    envelope = json.loads(envelope_json)
    assert "retryable" in envelope["error"]
    assert envelope["error"]["retryable"] is True


def test_error_envelope_retryable_override():
    """Explicit retryable parameter should override _RETRYABLE_MAP default."""
    envelope_json = EnvelopeBuilder.error(
        "test", "test_tool", ErrorCode.SEARCH_TIMEOUT, "timeout", retryable=False
    )
    envelope = json.loads(envelope_json)
    assert envelope["error"]["retryable"] is False
