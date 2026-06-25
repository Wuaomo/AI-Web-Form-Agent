"""Shared Playwright browser sessions keyed by task profile and site."""

import asyncio
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
import re
from typing import TypeVar
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.database import BACKEND_DIR

BROWSER_SESSIONS_DIR = BACKEND_DIR / "browser_sessions"
DEFAULT_VIEWPORT = {"width": 1440, "height": 900}
T = TypeVar("T")


def _close_context(context: BrowserContext) -> None:
    """Close a Playwright context and ignore already-closed browser windows."""

    try:
        context.close()
    except PlaywrightError:
        pass


def _site_origin(url: str) -> str:
    """Return the URL origin used to partition browser storage."""

    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    hostname = (parsed.hostname or "unknown-site").lower()
    port = f":{parsed.port}" if parsed.port else ""
    return f"{scheme}://{hostname}{port}"


def _slugify(value: str) -> str:
    """Create a filesystem-friendly name for browser profile folders."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "site"


def get_browser_session_dir(url: str, profile_id: int) -> Path:
    """Return the persistent Playwright user-data directory for a site."""

    origin = _site_origin(url)
    hostname = urlparse(origin).hostname or "unknown-site"
    digest = sha256(f"profile:{profile_id}|origin:{origin}".encode()).hexdigest()
    return (
        BROWSER_SESSIONS_DIR
        / f"profile_{profile_id}"
        / f"{_slugify(hostname)}_{digest[:12]}"
    )


def _run_with_persistent_page_sync(
    url: str,
    profile_id: int,
    callback: Callable[[Page], T],
    *,
    headless: bool = True,
) -> T:
    """Open a page in a persistent browser profile and close it afterwards."""

    user_data_dir = get_browser_session_dir(url, profile_id)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            viewport=DEFAULT_VIEWPORT,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            return callback(page)
        finally:
            _close_context(context)


async def run_with_persistent_page(
    url: str,
    profile_id: int,
    callback: Callable[[Page], T],
    *,
    headless: bool = True,
) -> T:
    """Run a sync Playwright page callback without blocking the API event loop."""

    return await asyncio.to_thread(
        _run_with_persistent_page_sync,
        url,
        profile_id,
        callback,
        headless=headless,
    )


def _prepare_login_session_sync(
    url: str,
    profile_id: int,
    *,
    timeout_seconds: int = 900,
) -> tuple[Path, bool]:
    """Open a visible browser so the user can complete interactive login."""

    user_data_dir = get_browser_session_dir(url, profile_id)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context: BrowserContext = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            viewport=DEFAULT_VIEWPORT,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                page.wait_for_event("close", timeout=timeout_seconds * 1000)
                timed_out = False
            except PlaywrightTimeoutError:
                timed_out = True
        finally:
            _close_context(context)

    return user_data_dir, timed_out


async def prepare_login_session(
    url: str,
    profile_id: int,
    *,
    timeout_seconds: int = 900,
) -> tuple[Path, bool]:
    """Open a visible browser so the user can complete interactive login."""

    return await asyncio.to_thread(
        _prepare_login_session_sync,
        url,
        profile_id,
        timeout_seconds=timeout_seconds,
    )
