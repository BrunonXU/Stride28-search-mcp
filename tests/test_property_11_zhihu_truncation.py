# Feature: mcp-data-stability-improvements, Property 11: 知乎回答内容长度截断
"""
**Validates: Requirements 11.2, 11.3**

Property 11: For any answer content string and any max_content_length value > 0,
the returned content length should be <= max_content_length. When max_content_length
is 0, the full content should be returned without truncation.

Since get_question_answers requires a browser, we test the truncation logic directly
by replicating the JS logic in Python:
    content = text[:maxContentLength] if maxContentLength > 0 else text
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st


def truncate_content(text: str, max_content_length: int) -> str:
    """Replicate the JS truncation logic from get_question_answers."""
    if max_content_length > 0:
        return text[:max_content_length]
    return text


@settings(max_examples=100)
@given(
    content=st.text(min_size=0, max_size=50000),
    max_len=st.integers(min_value=1, max_value=20000),
)
def test_truncation_respects_max_length(content: str, max_len: int) -> None:
    """When max_content_length > 0, result length must be <= max_content_length."""
    result = truncate_content(content, max_len)
    assert len(result) <= max_len, (
        f"Expected len <= {max_len}, got {len(result)}"
    )


@settings(max_examples=100)
@given(content=st.text(min_size=0, max_size=50000))
def test_zero_means_no_truncation(content: str) -> None:
    """When max_content_length is 0, full content is returned."""
    result = truncate_content(content, 0)
    assert result == content, (
        f"Expected full content (len={len(content)}), got len={len(result)}"
    )


@settings(max_examples=100)
@given(
    content=st.text(min_size=0, max_size=100),
    max_len=st.integers(min_value=100, max_value=20000),
)
def test_short_content_not_altered(content: str, max_len: int) -> None:
    """Content shorter than max_content_length is returned unchanged."""
    result = truncate_content(content, max_len)
    assert result == content
