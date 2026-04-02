# Feature: mcp-data-stability-improvements, Property 3: 发布时间提取（搜索结果）
"""
**Validates: Requirements 2.4**

Property 3: For any feed dict that contains a time-related field in note_card,
the parsed SearchResultItem.publish_time should contain that value. When no time
field exists, publish_time should be an empty string.

The extraction logic in _parse_feeds is:
    publish_time = note_card.get("time") or note_card.get("publishTime") or ""

Priority: "time" (if truthy) > "publishTime" (if truthy) > ""

Note: feeds with empty display_title are filtered out (R1), so the strategy
always generates a non-empty display_title to ensure the feed is parsed.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from stride28_search_mcp.adapter import XhsBrowserSearcher


# Strategy: non-empty time strings (realistic timestamp-like values)
_non_empty_time = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Nd", "L", "P", "Z")),
).filter(lambda s: bool(s.strip()))

# Strategy: optional time value — either absent (None), empty string, or non-empty
_optional_time = st.one_of(st.none(), st.just(""), _non_empty_time)


def feed_strategy():
    """Generate a single feed dict with a non-empty display_title and optional
    time / publishTime fields in note_card."""
    return st.fixed_dictionaries({
        "id": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Nd", "L"))),
        "xsec_token": st.text(min_size=0, max_size=20),
        "note_card": st.fixed_dictionaries(
            {
                "display_title": st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
                "user": st.fixed_dictionaries({"nickname": st.text(min_size=0, max_size=20)}),
                "interact_info": st.fixed_dictionaries({"liked_count": st.just("0")}),
                "cover": st.fixed_dictionaries({"url_default": st.just("")}),
                "type": st.just("normal"),
            },
            optional={
                "time": _optional_time,
                "publishTime": _optional_time,
            },
        ),
    })


@settings(max_examples=100)
@given(feed=feed_strategy())
def test_publish_time_extraction_from_feed(feed: dict) -> None:
    """Verify publish_time in parsed SearchResultItem matches the expected
    priority logic: time > publishTime > empty string."""
    results = XhsBrowserSearcher._parse_feeds([feed], limit=1)

    # Feed has non-empty display_title, so it should be parsed
    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    item = results[0]

    note_card = feed.get("note_card") or {}
    time_val = note_card.get("time")
    publish_time_val = note_card.get("publishTime")

    # Mirror the production logic: or-chain with truthy check
    if time_val:
        assert item.publish_time == time_val, (
            f"Expected time={time_val!r}, got {item.publish_time!r}"
        )
    elif publish_time_val:
        assert item.publish_time == publish_time_val, (
            f"Expected publishTime={publish_time_val!r}, got {item.publish_time!r}"
        )
    else:
        assert item.publish_time == "", (
            f"Expected empty string when no time fields, got {item.publish_time!r}"
        )


@settings(max_examples=100)
@given(feed=feed_strategy())
def test_publish_time_is_always_string(feed: dict) -> None:
    """publish_time must always be a string, never None or other type."""
    results = XhsBrowserSearcher._parse_feeds([feed], limit=1)
    assert len(results) == 1
    assert isinstance(results[0].publish_time, str), (
        f"Expected str, got {type(results[0].publish_time).__name__}: {results[0].publish_time!r}"
    )
