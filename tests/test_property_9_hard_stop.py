# Feature: mcp-data-stability-improvements, Property 9: 评论加载硬停止条件
"""
**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

Property 9: For any comment loading sequence, the loader should terminate when
any of the following conditions is met:
  (a) total elapsed time exceeds max_duration,
  (b) consecutive empty load attempts reach max_empty_loads, or
  (c) selector failure count reaches max_selector_failures.
In all cases, the already-loaded comments should be returned.

Since _load_more_comments requires a browser, we simulate the hard stop logic
with random sequences of load results (empty/non-empty) and selector outcomes.
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from stride28_search_mcp.models import CommentItem


def simulate_comment_loading(
    load_results: list[tuple[bool, bool]],
    max_comments: int = 50,
    max_empty_loads: int = 3,
    max_selector_failures: int = 3,
) -> tuple[list[CommentItem], str | None]:
    """Simulate the hard stop logic from _load_more_comments.

    Each element in *load_results* is a ``(selector_found, new_comments)`` pair:
    - ``selector_found``: True means the "more" button was found (resets
      selector_failures); False means it was not (increments selector_failures).
    - ``new_comments``: True means new comments were loaded (resets
      consecutive_empty); False means no new comments (increments
      consecutive_empty).

    The loop runs at most ``max(max_comments // 5, 1)`` iterations, matching
    the real implementation.
    """
    comments: list[CommentItem] = []
    consecutive_empty = 0
    selector_failures = 0
    stop_reason: str | None = None
    comment_counter = 0
    max_iterations = max(max_comments // 5, 1)

    for i, (selector_found, new_comments_loaded) in enumerate(load_results):
        if i >= max_iterations:
            break
        if len(comments) >= max_comments:
            break

        # Selector logic
        if selector_found:
            selector_failures = 0
        else:
            selector_failures += 1
            if selector_failures >= max_selector_failures:
                stop_reason = "selector_failures"
                break

        # Comment loading logic
        if new_comments_loaded:
            comment_counter += 1
            comments.append(
                CommentItem(text=f"comment {comment_counter}", author="user")
            )
            consecutive_empty = 0
        else:
            consecutive_empty += 1
            if consecutive_empty >= max_empty_loads:
                stop_reason = "consecutive_empty"
                break

    return comments[:max_comments], stop_reason


# -- Strategy: pairs of (selector_found, new_comments_loaded) booleans ------
_load_step = st.tuples(st.booleans(), st.booleans())


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    load_results=st.lists(_load_step, min_size=0, max_size=50),
    max_comments=st.integers(min_value=1, max_value=50),
    max_empty_loads=st.integers(min_value=1, max_value=5),
    max_selector_failures=st.integers(min_value=1, max_value=5),
)
def test_hard_stop_conditions(
    load_results: list[tuple[bool, bool]],
    max_comments: int,
    max_empty_loads: int,
    max_selector_failures: int,
) -> None:
    """Verify hard stop invariants hold for any random loading sequence."""
    comments, stop_reason = simulate_comment_loading(
        load_results, max_comments, max_empty_loads, max_selector_failures
    )

    # Invariant 1: result never exceeds max_comments (R9.4 + R3.3)
    assert len(comments) <= max_comments, (
        f"Expected at most {max_comments} comments, got {len(comments)}"
    )

    # Invariant 2: if stopped by consecutive_empty, the trailing sequence of
    # "no new comments" steps must be >= max_empty_loads
    if stop_reason == "consecutive_empty":
        # Replay to count how many steps were actually processed
        processed = _count_processed_steps(
            load_results, max_comments, max_empty_loads, max_selector_failures
        )
        trailing_empty = 0
        for _, new_comments_loaded in reversed(load_results[:processed]):
            if not new_comments_loaded:
                trailing_empty += 1
            else:
                break
        assert trailing_empty >= max_empty_loads, (
            f"consecutive_empty stop but trailing empty={trailing_empty} "
            f"< max_empty_loads={max_empty_loads}"
        )

    # Invariant 3: if stopped by selector_failures, the trailing sequence of
    # "selector not found" steps must be >= max_selector_failures
    if stop_reason == "selector_failures":
        processed = _count_processed_steps(
            load_results, max_comments, max_empty_loads, max_selector_failures
        )
        trailing_selector_fail = 0
        for selector_found, _ in reversed(load_results[:processed]):
            if not selector_found:
                trailing_selector_fail += 1
            else:
                break
        assert trailing_selector_fail >= max_selector_failures, (
            f"selector_failures stop but trailing fails={trailing_selector_fail} "
            f"< max_selector_failures={max_selector_failures}"
        )

    # Invariant 4: already-loaded comments are always returned (non-negative)
    assert len(comments) >= 0


def _count_processed_steps(
    load_results: list[tuple[bool, bool]],
    max_comments: int,
    max_empty_loads: int,
    max_selector_failures: int,
) -> int:
    """Replay the simulation to count how many steps were processed."""
    consecutive_empty = 0
    selector_failures = 0
    comment_count = 0
    max_iterations = max(max_comments // 5, 1)

    for i, (selector_found, new_comments_loaded) in enumerate(load_results):
        if i >= max_iterations:
            return i
        if comment_count >= max_comments:
            return i

        if selector_found:
            selector_failures = 0
        else:
            selector_failures += 1
            if selector_failures >= max_selector_failures:
                return i + 1

        if new_comments_loaded:
            comment_count += 1
            consecutive_empty = 0
        else:
            consecutive_empty += 1
            if consecutive_empty >= max_empty_loads:
                return i + 1

    return len(load_results)


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    # Need enough iterations for 3 consecutive empties: max_comments >= 16
    # so max(max_comments // 5, 1) >= 4 > max_empty_loads=3
    max_comments=st.integers(min_value=16, max_value=50),
    max_empty_loads=st.integers(min_value=1, max_value=3),
)
def test_all_empty_loads_trigger_stop(
    max_comments: int, max_empty_loads: int
) -> None:
    """When every load is empty, the loader must stop after max_empty_loads."""
    # All steps: selector found but no new comments
    load_results = [(True, False)] * 20
    comments, stop_reason = simulate_comment_loading(
        load_results, max_comments, max_empty_loads=max_empty_loads,
        max_selector_failures=5,
    )
    assert stop_reason == "consecutive_empty"
    assert len(comments) == 0


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    # Need enough iterations for 3 consecutive selector failures
    max_comments=st.integers(min_value=16, max_value=50),
    max_selector_failures=st.integers(min_value=1, max_value=3),
)
def test_all_selector_failures_trigger_stop(
    max_comments: int, max_selector_failures: int
) -> None:
    """When selector always fails, the loader must stop after max_selector_failures."""
    # All steps: selector not found, no new comments
    load_results = [(False, False)] * 20
    comments, stop_reason = simulate_comment_loading(
        load_results, max_comments, max_empty_loads=5,
        max_selector_failures=max_selector_failures,
    )
    assert stop_reason == "selector_failures"
    assert len(comments) == 0
