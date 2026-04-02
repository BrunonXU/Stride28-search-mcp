# Feature: mcp-data-stability-improvements, Property 1: 过滤后结果不含空标题
"""
**Validates: Requirements 1.1, 1.3**

Property 1: For any list of feed dicts (some with empty display_title, some with
non-empty), after calling _parse_feeds, every SearchResultItem in the result should
have a non-empty title field (title.strip() != "").
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.adapter import XhsBrowserSearcher


def feed_strategy():
    """Generate a single feed dict with mixed empty/non-empty display_title values."""
    return st.fixed_dictionaries({
        "id": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Nd", "L"))),
        "xsec_token": st.text(min_size=0, max_size=20),
        "note_card": st.fixed_dictionaries({
            "display_title": st.one_of(
                st.just(""),           # empty
                st.just("   "),        # whitespace only
                st.text(min_size=1, max_size=50),  # non-empty
            ),
            "user": st.fixed_dictionaries({"nickname": st.text(min_size=0, max_size=20)}),
            "interact_info": st.fixed_dictionaries({"liked_count": st.just("0")}),
            "cover": st.fixed_dictionaries({"url_default": st.just("")}),
            "type": st.just("normal"),
        }),
    })


@settings(max_examples=100)
@given(
    feeds=st.lists(feed_strategy(), min_size=0, max_size=50),
    limit=st.integers(min_value=1, max_value=100),
)
def test_parsed_feeds_have_non_empty_titles(feeds: list, limit: int) -> None:
    """Every item returned by _parse_feeds must have a non-empty title."""
    results = XhsBrowserSearcher._parse_feeds(feeds, limit)
    for item in results:
        assert item.title.strip() != "", (
            f"Found item with empty/whitespace-only title: {item!r}"
        )
