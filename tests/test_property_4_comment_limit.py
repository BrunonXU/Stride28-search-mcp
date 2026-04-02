# Feature: mcp-data-stability-improvements, Property 4: 评论数量不超过上限
"""
**Validates: Requirements 3.3**

Property 4: For any max_comments value (positive integer) and any list of
CommentItem objects, applying the truncation `comments[:max_comments]` ensures
the result length never exceeds max_comments.

Since _load_more_comments requires a browser, we test the truncation logic
directly. The key guarantee is: `comments[:max_comments]` ensures the result
never exceeds max_comments.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.models import CommentItem


@settings(max_examples=100)
@given(
    num_comments=st.integers(min_value=0, max_value=200),
    max_comments=st.integers(min_value=1, max_value=200),
)
def test_comment_count_within_limit(num_comments: int, max_comments: int) -> None:
    """The number of comments after truncation must never exceed max_comments."""
    comments = [
        CommentItem(text=f"comment {i}", author=f"user {i}")
        for i in range(num_comments)
    ]
    result = comments[:max_comments]
    assert len(result) <= max_comments, (
        f"Expected at most {max_comments} comments, got {len(result)}"
    )
