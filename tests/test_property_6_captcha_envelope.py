# Feature: mcp-data-stability-improvements, Property 6: CAPTCHA 错误信封格式
"""
**Validates: Requirements 6.2**

Property 6: For any platform and tool name strings, the error envelope produced by
EnvelopeBuilder.error(platform, tool, ErrorCode.CAPTCHA_DETECTED, message) should be
valid JSON with ok=false, the correct error code "captcha_detected", and the provided
message. CAPTCHA_DETECTED is not retryable.
"""
from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.models import EnvelopeBuilder, ErrorCode


@settings(max_examples=100)
@given(
    platform=st.text(min_size=1, max_size=20),
    tool=st.text(min_size=1, max_size=30),
    message=st.text(min_size=0, max_size=200),
)
def test_captcha_error_envelope_format(platform: str, tool: str, message: str) -> None:
    """CAPTCHA_DETECTED error envelope has correct JSON structure and field values."""
    envelope_json = EnvelopeBuilder.error(
        platform, tool, ErrorCode.CAPTCHA_DETECTED, message
    )
    envelope = json.loads(envelope_json)

    # Top-level fields
    assert envelope["ok"] is False
    assert envelope["platform"] == platform
    assert envelope["tool"] == tool
    assert isinstance(envelope["request_id"], str) and len(envelope["request_id"]) > 0
    assert envelope["data"] is None

    # Error sub-object
    err = envelope["error"]
    assert err["code"] == "captcha_detected"
    assert err["message"] == message
    assert err["retryable"] is False
