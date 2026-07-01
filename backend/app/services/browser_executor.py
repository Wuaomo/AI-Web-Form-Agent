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
from app.services.action_trace_service import record_action_trace

SCREENSHOTS_DIR = BACKEND_DIR / "screenshots"
NON_FILLABLE_FIELD_TYPES = {"button", "file", "submit", "reset", "image"}


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


def _checkbox_should_be_checked(value: str) -> bool | None:
    """Return the intended checkbox state for a mapped value."""

    normalized_value = value.lower()
    if normalized_value in {"1", "true", "yes", "on", "checked"}:
        return True
    if normalized_value in {"0", "false", "no", "off", "unchecked"}:
        return False
    return None


def _radio_selector_for_value(field: FormField) -> str:
    """Return the radio option selector matching the mapped value."""

    mapped_value = field.mapped_value or ""
    for option in field.options:
        if mapped_value in {option.get("label"), option.get("value")}:
            return option.get("selector") or field.selector
    return field.selector


def _trace_fill_action(
    db: Session | None,
    task_id: int | None,
    field: FormField,
    action: str,
    result: str,
    error_message: str | None = None,
) -> None:
    """Record a fill trace when task context is available."""

    if db is None or task_id is None:
        return
    record_action_trace(
        db,
        task_id=task_id,
        phase="fill",
        action=action,
        result=result,
        selector=field.selector,
        field_id=field.id,
        input_value=field.mapped_value,
        error_message=error_message,
    )


def _trace_browser_action(
    db: Session | None,
    task_id: int | None,
    *,
    phase: str,
    action: str,
    result: str,
    selector: str | None = None,
    error_message: str | None = None,
    screenshot_id: int | None = None,
) -> None:
    """Record a non-field browser action when task context is available."""

    if db is None or task_id is None:
        return
    record_action_trace(
        db,
        task_id=task_id,
        phase=phase,
        action=action,
        result=result,
        selector=selector,
        error_message=error_message,
        screenshot_id=screenshot_id,
    )


def _fill_fields(
    page: Page,
    fields: list[FormField],
    task_id: int | None = None,
    db: Session | None = None,
) -> None:
    """Fill mapped fields on the current page."""

    for field in fields:
        if not field.mapped_value:
            _trace_fill_action(db, task_id, field, "skip", "skipped")
            continue
        field_type = (field.field_type or "").lower()
        if field_type in NON_FILLABLE_FIELD_TYPES:
            _trace_fill_action(db, task_id, field, "skip", "skipped")
            continue

        try:
            locator = page.locator(field.selector).first
            action = "fill"
            if field_type == "checkbox":
                checked = _checkbox_should_be_checked(field.mapped_value)
                action = "check" if checked is True else "uncheck"
                if checked is True:
                    locator.check(timeout=5_000)
                elif checked is False:
                    locator.uncheck(timeout=5_000)
                else:
                    _trace_fill_action(db, task_id, field, "skip", "skipped")
                    continue
            elif field_type == "radio":
                action = "check"
                page.locator(_radio_selector_for_value(field)).first.check(timeout=5_000)
            elif field_type == "select":
                action = "select"
                try:
                    locator.select_option(label=field.mapped_value, timeout=5_000)
                except (PlaywrightError, PlaywrightTimeoutError):
                    locator.select_option(value=field.mapped_value, timeout=5_000)
            else:
                locator.fill(field.mapped_value, timeout=5_000)
            _trace_fill_action(db, task_id, field, action, "success")
        except Exception as exc:
            _trace_fill_action(db, task_id, field, "fill", "failed", str(exc))
            raise


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
        _trace_browser_action(
            db,
            task_id,
            phase="open_page",
            action="goto",
            result="success",
        )
        _wait_for_network_idle(page)
        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, capture)
    screenshot = _save_screenshot_record(task_id, relative_path, stage, db)
    _trace_browser_action(
        db,
        task_id,
        phase=stage,
        action="screenshot",
        result="success",
        screenshot_id=screenshot.id,
    )
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

    relative_path, screenshot_path = _new_screenshot_path(task_id)

    def fill_form(page: Page) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        _trace_browser_action(
            db,
            task_id,
            phase="fill",
            action="goto",
            result="success",
        )
        _wait_for_network_idle(page)
        _fill_fields(page, fields, task_id=task_id, db=db)
        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, fill_form)
    screenshot = _save_screenshot_record(task_id, relative_path, stage, db)
    _trace_browser_action(
        db,
        task_id,
        phase=stage,
        action="screenshot",
        result="success",
        screenshot_id=screenshot.id,
    )
    return screenshot


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
        _trace_browser_action(
            db,
            task_id,
            phase="submit",
            action="goto",
            result="success",
        )
        _wait_for_network_idle(page)
        _fill_fields(page, fields, task_id=task_id, db=db)

        submit_button = page.locator(
            'button[type="submit"], input[type="submit"], button:not([type])'
        ).first
        if submit_button.count() == 0:
            raise RuntimeError("No submit button was found")

        submit_button.click(timeout=5_000)
        _trace_browser_action(
            db,
            task_id,
            phase="submit",
            action="click",
            result="success",
            selector='button[type="submit"], input[type="submit"], button:not([type])',
        )
        _wait_for_network_idle(page)
        page.screenshot(path=str(screenshot_path), full_page=True)

    await run_with_persistent_page(url, profile_id, submit_form)
    screenshot = _save_screenshot_record(task_id, relative_path, stage, db)
    _trace_browser_action(
        db,
        task_id,
        phase=stage,
        action="screenshot",
        result="success",
        screenshot_id=screenshot.id,
    )
    return screenshot
