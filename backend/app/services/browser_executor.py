"""Open web pages and capture screenshots with Playwright."""

from datetime import datetime, timezone
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from sqlalchemy.orm import Session

from app.database import BACKEND_DIR, SessionLocal
from app.models import FormField, Screenshot
from app.services.browser_session import run_with_persistent_page

SCREENSHOTS_DIR = BACKEND_DIR / "screenshots"


async def open_url_and_capture_screenshot(
    task_id: int,
    url: str,
    profile_id: int,
    stage: str = "page_opened",
    db: Session | None = None,
) -> Screenshot:
    """Open a URL, wait for it to load, and save a full-page screenshot."""

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{timestamp}_{uuid4().hex[:8]}.png"
    screenshot_path = SCREENSHOTS_DIR / filename

    def capture(page: Page) -> None:
        page.goto(url, wait_until="load", timeout=30_000)

        # Some pages continuously load background requests. A short
        # network-idle wait improves screenshots without blocking forever.
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeoutError:
            pass

        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, capture)

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
    profile_id: int,
    fields: list[FormField],
    stage: str = "filled_form",
    db: Session | None = None,
) -> Screenshot:
    """Fill mapped input fields, stop before submission, and save a screenshot."""

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{timestamp}_{uuid4().hex[:8]}.png"
    screenshot_path = SCREENSHOTS_DIR / filename

    def fill_form(page: Page) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
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
                    locator.check(timeout=5_000)
                continue
            if field_type == "radio":
                locator.check(timeout=5_000)
                continue
            if field_type == "select":
                try:
                    locator.select_option(label=field.mapped_value, timeout=5_000)
                except (PlaywrightError, PlaywrightTimeoutError):
                    locator.select_option(value=field.mapped_value, timeout=5_000)
                continue

            locator.fill(field.mapped_value, timeout=5_000)

        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, fill_form)

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
