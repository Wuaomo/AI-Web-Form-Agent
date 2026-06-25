"""Open web pages, fill forms, and capture screenshots with Playwright."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from sqlalchemy.orm import Session

from app.database import BACKEND_DIR, SessionLocal
from app.models import FormField, Screenshot
from app.services.browser_session import run_with_persistent_page

SCREENSHOTS_DIR = BACKEND_DIR / "screenshots"
NON_FILLABLE_FIELD_TYPES = {"button", "submit", "reset", "image"}


def _new_screenshot_path(task_id: int) -> tuple[str, Path]:
    """Create the screenshot directory and return a unique file path."""

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{timestamp}_{uuid4().hex[:8]}.png"
    screenshot_path = SCREENSHOTS_DIR / filename
    return screenshot_path.relative_to(BACKEND_DIR).as_posix(), screenshot_path


def _save_screenshot_record(
    task_id: int,
    relative_path: str,
    stage: str,
    db: Session | None,
) -> Screenshot:
    """Persist screenshot metadata using the provided or ad-hoc session."""

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


def _wait_for_network_idle(page: Page) -> None:
    """Wait briefly for a page to settle without requiring idle forever."""

    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeoutError:
        pass


def _fill_fields(page: Page, fields: list[FormField]) -> None:
    """Fill mapped fields on the current page."""

    for field in fields:
        if not field.mapped_value:
            continue
        field_type = (field.field_type or "").lower()
        if field_type in NON_FILLABLE_FIELD_TYPES:
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


async def open_url_and_capture_screenshot(
    task_id: int,
    url: str,
    profile_id: int,
    stage: str = "page_opened",
    db: Session | None = None,
) -> Screenshot:
    """Open a URL, wait for it to load, and save a full-page screenshot."""

    relative_path, screenshot_path = _new_screenshot_path(task_id)

    def capture(page: Page) -> None:
        page.goto(url, wait_until="load", timeout=30_000)
        _wait_for_network_idle(page)
        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, capture)
    return _save_screenshot_record(task_id, relative_path, stage, db)


async def fill_form_and_capture_screenshot(
    task_id: int,
    url: str,
    profile_id: int,
    fields: list[FormField],
    stage: str = "filled_form",
    db: Session | None = None,
) -> Screenshot:
    """Fill mapped input fields, stop before submission, and save a screenshot."""

    relative_path, screenshot_path = _new_screenshot_path(task_id)

    def fill_form(page: Page) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        _wait_for_network_idle(page)
        _fill_fields(page, fields)
        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, fill_form)
    return _save_screenshot_record(task_id, relative_path, stage, db)


async def submit_form_and_capture_screenshot(
    task_id: int,
    url: str,
    profile_id: int,
    fields: list[FormField],
    stage: str = "submitted_form",
    db: Session | None = None,
) -> Screenshot:
    """Fill mapped input fields, click submit, and save a screenshot."""

    relative_path, screenshot_path = _new_screenshot_path(task_id)

    def submit_form(page: Page) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        _wait_for_network_idle(page)
        _fill_fields(page, fields)

        submit_button = page.locator(
            'button[type="submit"], input[type="submit"], button:not([type])'
        ).first
        if submit_button.count() == 0:
            raise RuntimeError("No submit button was found")

        submit_button.click(timeout=5_000)
        _wait_for_network_idle(page)
        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, submit_form)
    return _save_screenshot_record(task_id, relative_path, stage, db)
