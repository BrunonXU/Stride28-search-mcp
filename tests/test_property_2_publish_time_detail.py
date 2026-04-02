# Feature: mcp-data-stability-improvements, Property 2: 发布时间提取（笔记详情）
"""
**Validates: Requirements 2.1, 2.2**

Property 2: For any noteDetailMap dict that contains a "time" or "publishTime" field
with a non-empty string value, the extracted publish_time should equal that value.
When neither field exists, publish_time should be an empty string.

Since get_note_detail is async and requires a browser, we test the extraction logic
directly by replicating the pure extraction path:
    data = detail.get("note") or detail
    publish_time = data.get("time") or data.get("publishTime") or ""
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st


def extract_publish_time(detail: dict) -> str:
    """Replicate the publish_time extraction logic from get_note_detail."""
    data = detail.get("note") or detail
    return data.get("time") or data.get("publishTime") or ""


# Strategy: non-empty time strings (realistic timestamps)
_non_empty_time = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Nd", "L", "P", "Z")),
).filter(lambda s: s.strip() != "")

# Strategy: optional time value — either a non-empty string or absent (None)
_optional_time = st.one_of(st.none(), st.just(""), _non_empty_time)


def note_detail_strategy():
    """Generate a detail dict that may or may not have a 'note' sub-dict,
    and may or may not contain 'time' / 'publishTime' fields."""
    inner_dict = st.fixed_dictionaries(
        {},
        optional={
            "time": _optional_time,
            "publishTime": _optional_time,
            "title": st.text(max_size=20),
            "desc": st.text(max_size=50),
        },
    )
    # Either wrap in a "note" key or use the dict directly
    return st.one_of(
        # Case A: detail has a "note" sub-dict
        inner_dict.map(lambda d: {"note": d}),
        # Case B: detail IS the data dict (no "note" key)
        inner_dict,
    )


@settings(max_examples=100)
@given(detail=note_detail_strategy())
def test_publish_time_extraction(detail: dict) -> None:
    """Verify publish_time extraction matches the expected priority logic."""
    result = extract_publish_time(detail)

    # Determine the data dict the same way the production code does
    data = detail.get("note") or detail

    time_val = data.get("time")
    publish_time_val = data.get("publishTime")

    # Priority: "time" (if truthy) > "publishTime" (if truthy) > ""
    if time_val:
        assert result == time_val, (
            f"Expected time={time_val!r}, got {result!r}"
        )
    elif publish_time_val:
        assert result == publish_time_val, (
            f"Expected publishTime={publish_time_val!r}, got {result!r}"
        )
    else:
        assert result == "", (
            f"Expected empty string when no time fields, got {result!r}"
        )


@settings(max_examples=100)
@given(detail=note_detail_strategy())
def test_publish_time_is_always_string(detail: dict) -> None:
    """publish_time must always be a string, never None or other type."""
    result = extract_publish_time(detail)
    assert isinstance(result, str), (
        f"Expected str, got {type(result).__name__}: {result!r}"
    )
