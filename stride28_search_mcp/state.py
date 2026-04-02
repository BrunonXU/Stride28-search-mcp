"""浏览器状态目录与运行模式工具。"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_DEFAULT_HOME = ".stride28-search-mcp"
_HEADLESS_FALSE_VALUES = {"0", "false", "no", "off"}


def get_data_home() -> Path:
    return Path(os.getenv("STRIDE28_SEARCH_MCP_HOME", Path.home() / _DEFAULT_HOME))


def get_profile_name() -> str:
    raw = os.getenv("STRIDE28_SEARCH_MCP_PROFILE", "").strip()
    if not raw:
        return ""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("._-")
    return sanitized or "profile"


def is_explicit_profile() -> bool:
    return bool(get_profile_name())


def get_profile_mode() -> str:
    return "isolated" if is_explicit_profile() else "shared_default"


def get_browser_data_dir(platform: str) -> Path:
    browser_root = get_data_home() / "browser_data"
    profile = get_profile_name()
    if profile:
        return browser_root / "profiles" / profile / platform
    return browser_root / platform


def get_non_login_headless() -> bool:
    raw = os.getenv("STRIDE28_SEARCH_MCP_HEADLESS", "true").strip().lower()
    return raw not in _HEADLESS_FALSE_VALUES


def find_cookie_store(platform: str) -> Path | None:
    browser_data_dir = get_browser_data_dir(platform)
    candidates = (
        browser_data_dir / "Default" / "Network" / "Cookies",
        browser_data_dir / "Default" / "Cookies",
        browser_data_dir / "Network" / "Cookies",
        browser_data_dir / "Cookies",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if browser_data_dir.exists():
        for candidate in browser_data_dir.rglob("Cookies"):
            return candidate
    return None


def clear_browser_data(platform: str) -> Path:
    if platform not in {"xhs", "zhihu"}:
        raise ValueError(f"unsupported platform: {platform}")
    browser_root = (get_data_home() / "browser_data").resolve(strict=False)
    target = get_browser_data_dir(platform).resolve(strict=False)
    if not target.is_relative_to(browser_root):
        raise ValueError(f"refusing to clear path outside browser_data: {target}")
    if target.exists():
        shutil.rmtree(target)
    return target
