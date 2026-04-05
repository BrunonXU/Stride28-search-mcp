from __future__ import annotations

from pathlib import Path

from stride28_search_mcp import state


def test_browser_data_dir_uses_legacy_shared_path_when_profile_missing(monkeypatch):
    monkeypatch.delenv("STRIDE28_SEARCH_MCP_PROFILE", raising=False)
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_HOME", r"C:\tmp\stride28")
    assert state.get_browser_data_dir("xhs") == Path(r"C:\tmp\stride28") / "browser_data" / "xhs"


def test_browser_data_dir_uses_profile_when_set(monkeypatch):
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_HOME", r"C:\tmp\stride28")
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_PROFILE", "workbuddy")
    assert (
        state.get_browser_data_dir("zhihu")
        == Path(r"C:\tmp\stride28") / "browser_data" / "profiles" / "workbuddy" / "zhihu"
    )


def test_profile_name_is_sanitized(monkeypatch):
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_PROFILE", "Work Buddy / QA")
    assert state.get_profile_name() == "Work-Buddy-QA"


def test_non_login_headless_defaults_true(monkeypatch):
    monkeypatch.delenv("STRIDE28_SEARCH_MCP_HEADLESS", raising=False)
    assert state.get_non_login_headless() is True


def test_non_login_headless_false_values(monkeypatch):
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_HEADLESS", "false")
    assert state.get_non_login_headless() is False


def test_platform_headless_defaults_are_conservative(monkeypatch):
    monkeypatch.delenv("STRIDE28_SEARCH_MCP_HEADLESS", raising=False)
    monkeypatch.delenv("STRIDE28_XHS_HEADLESS", raising=False)
    monkeypatch.delenv("STRIDE28_ZHIHU_HEADLESS", raising=False)
    assert state.get_platform_headless("xhs") is False
    assert state.get_platform_headless("zhihu") is True


def test_platform_headless_prefers_specific_env(monkeypatch):
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_HEADLESS", "true")
    monkeypatch.setenv("STRIDE28_XHS_HEADLESS", "false")
    monkeypatch.setenv("STRIDE28_ZHIHU_HEADLESS", "false")
    assert state.get_platform_headless("xhs") is False
    assert state.get_platform_headless("zhihu") is False


def test_platform_headless_falls_back_to_legacy_env(monkeypatch):
    monkeypatch.setenv("STRIDE28_SEARCH_MCP_HEADLESS", "false")
    monkeypatch.delenv("STRIDE28_XHS_HEADLESS", raising=False)
    assert state.get_platform_headless("xhs") is False
