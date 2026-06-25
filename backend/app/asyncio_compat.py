"""Asyncio compatibility helpers for browser automation."""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def configure_asyncio_for_playwright() -> None:
    """Use a Windows event loop policy that can spawn Playwright browsers."""

    if sys.platform != "win32":
        return

    proactor_policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if proactor_policy is None:
        return

    asyncio.set_event_loop_policy(proactor_policy())


def _run_in_new_playwright_loop(coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run a coroutine in a fresh event loop configured for Playwright."""

    configure_asyncio_for_playwright()
    return asyncio.run(coro_factory())


async def run_playwright_compatible(
    coro_factory: Callable[[], Awaitable[T]],
) -> T:
    """Run Playwright work on an event loop that supports subprocesses."""

    if sys.platform != "win32":
        return await coro_factory()

    return await asyncio.to_thread(_run_in_new_playwright_loop, coro_factory)
