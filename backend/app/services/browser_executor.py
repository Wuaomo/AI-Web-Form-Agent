"""Open web pages and capture screenshots with Playwright."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.database import BACKEND_DIR, SessionLocal
from app.models import FormField, Screenshot

SCREENSHOTS_DIR = BACKEND_DIR / "screenshots"


async def open_url_and_capture_screenshot(
    task_id: int,
    url: str,
    stage: str = "page_opened",
    db: Session | None = None,
) -> Screenshot:
    """Open a URL, wait for it to load, and save a full-page screenshot."""

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{timestamp}_{uuid4().hex[:8]}.png"
    screenshot_path = SCREENSHOTS_DIR / filename

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(url, wait_until="load", timeout=30_000)

            # Some pages continuously load background requests. A short
            # network-idle wait improves screenshots without blocking forever.
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except PlaywrightTimeoutError:
                pass

            await page.screenshot(path=str(screenshot_path), full_page=True)
        finally:
            await browser.close()

    relative_path = screenshot_path.relative_to(BACKEND_DIR).as_posix()
    screenshot = Screenshot(
        task_id=task_id,
        file_path=relative_path,
        stage=stage,
    )

    if db is not None:
        db.add(screenshot)
        db.flush()
        return screenshot

    with SessionLocal() as session:
        session.add(screenshot)
        session.commit()
        session.refresh(screenshot)
        session.expunge(screenshot)

    return screenshot


async def fill_form_and_capture_screenshot(
    task_id: int,
    url: str,
    fields: list[FormField],
    stage: str = "filled_form",
    db: Session | None = None,
) -> Screenshot:
    """Fill mapped input fields, stop before submission, and save a screenshot."""

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{timestamp}_{uuid4().hex[:8]}.png"
    screenshot_path = SCREENSHOTS_DIR / filename

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except PlaywrightTimeoutError:
                pass

            for field in fields:
                if not field.mapped_value:
                    continue
                field_type = (field.field_type or "").lower()
                if field_type in {"button", "submit", "reset", "image"}:
                    continue

                locator = page.locator(field.selector).first
                if field_type == "checkbox":
                    if field.mapped_value.lower() in {"1", "true", "yes", "on"}:
                        await locator.check(timeout=5_000)
                    continue
                if field_type == "radio":
                    await locator.check(timeout=5_000)
                    continue
                if field_type == "select":
                    try:
                        await locator.select_option(label=field.mapped_value, timeout=5_000)
                    except (PlaywrightError, PlaywrightTimeoutError):
                        await locator.select_option(value=field.mapped_value, timeout=5_000)
                    continue

                await locator.fill(field.mapped_value, timeout=5_000)

            await page.screenshot(path=str(screenshot_path), full_page=True)
        finally:
            await browser.close()

    relative_path = screenshot_path.relative_to(BACKEND_DIR).as_posix()
    screenshot = Screenshot(
        task_id=task_id,
        file_path=relative_path,
        stage=stage,
    )

    if db is not None:
        db.add(screenshot)
        db.flush()
        return screenshot

    with SessionLocal() as session:
        session.add(screenshot)
        session.commit()
        session.refresh(screenshot)
        session.expunge(screenshot)

    return screenshot
