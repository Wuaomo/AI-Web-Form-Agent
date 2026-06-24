"""Asyncio compatibility helpers for browser automation."""

import asyncio
import sys


def configure_asyncio_for_playwright() -> None:
    """Use a Windows event loop policy that can spawn Playwright browsers."""

    if sys.platform != "win32":
        return

    proactor_policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if proactor_policy is None:
        return

    asyncio.set_event_loop_policy(proactor_policy())
