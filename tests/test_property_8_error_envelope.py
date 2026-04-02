# Feature: mcp-data-stability-improvements, Property 8: 错误信封结构一致性与 retryable 字段
"""
**Validates: Requirements 8.1, 8.2, 8.3**

Property 8: For any ErrorCode value, platform string, tool string, and message string,
the JSON produced by EnvelopeBuilder.error(platform, tool, code, message) should contain
all required fields (ok, platform, tool, request_id, error) where error contains code,
message, and retryable (boolean). The retryable value should match _RETRYABLE_MAP default
for that error code.
"""
from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.models import (
    EnvelopeBuilder,
    ErrorCode,
    _RETRYABLE_MAP,
)


@settings(max_examples=100)
@given(
    code=st.sampled_from(list(ErrorCode)),
    platform=st.text(min_size=1, max_size=20),
    tool=st.text(min_size=1, max_size=30),
    message=st.text(min_size=0, max_size=200),
)
def test_error_envelope_structure_and_retryable(
    code: ErrorCode, platform: str, tool: str, message: str
) -> None:
    """Every error envelope has consistent structure and retryable matches _RETRYABLE_MAP."""
    envelope_json = EnvelopeBuilder.error(platform, tool, code, message)
    envelope = json.loads(envelope_json)

    # Top-level required fields
    assert envelope["ok"] is False
    assert envelope["platform"] == platform
    assert envelope["tool"] == tool
    assert isinstance(envelope["request_id"], str) and len(envelope["request_id"]) > 0
    assert "error" in envelope

    # Error sub-object required fields
    err = envelope["error"]
    assert err["code"] == code.value
    assert err["message"] == message
    assert "retryable" in err
    assert isinstance(err["retryable"], bool)
    assert err["retryable"] == _RETRYABLE_MAP[code]
