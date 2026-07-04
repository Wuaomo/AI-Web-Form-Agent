"""Open web pages, fill forms, and capture screenshots with Playwright."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from sqlalchemy.orm import Session

from app.database import BACKEND_DIR, SessionLocal
from app.models import (
    FormField,
    Screenshot,
    VERIFICATION_REASON_SELECTOR_NOT_FOUND,
)
from app.services.browser_session import run_with_persistent_page
from app.services.action_trace_service import record_action_trace

SCREENSHOTS_DIR = BACKEND_DIR / "screenshots"
NON_FILLABLE_FIELD_TYPES = {"button", "file", "submit", "reset", "image"}


class FieldVerificationData:
    """Data collected for post-fill verification of one field."""

    def __init__(
        self,
        field_id: Optional[int],
        selector: str,
        expected_value: Optional[str],
        actual_value: Optional[str],
        status: str,
        reason: Optional[str] = None,
        message: Optional[str] = None,
    ):
        self.field_id = field_id
        self.selector = selector
        self.expected_value = expected_value
        self.actual_value = actual_value
        self.status = status
        self.reason = reason
        self.message = message


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


def _read_field_value(page: Page, field: FormField) -> str | None:
    """Read the actual value of a field from the browser."""

    field_type = (field.field_type or "").lower()
    try:
        locator = page.locator(field.selector).first
        if field_type == "checkbox":
            return str(locator.is_checked(timeout=3_000)).lower()
        elif field_type == "radio":
            radio_selector = _radio_selector_for_value(field)
            return str(page.locator(radio_selector).first.is_checked(timeout=3_000)).lower()
        elif field_type == "select":
            selected = locator.evaluate(
                """(el) => {
                    if (!el.options || el.selectedIndex < 0) return null;
                    const opt = el.options[el.selectedIndex];
                    return opt.value || opt.textContent || null;
                }""",
                timeout=3_000,
            )
            return selected
        else:
            return locator.input_value(timeout=3_000)
    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        return None


def _values_match(field: FormField, expected: str | None, actual: str | None) -> bool:
    """Return whether expected and actual values should be considered a match."""

    if expected is None or actual is None:
        return expected == actual

    field_type = (field.field_type or "").lower()
    if field_type == "checkbox" or field_type == "radio":
        expected_bool = _checkbox_should_be_checked(expected)
        actual_bool = actual == "true"
        return expected_bool == actual_bool

    return expected == actual


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
) -> list[FieldVerificationData]:
    """Fill mapped fields on the current page and return verification data."""

    from app.models import (
        VERIFICATION_STATUS_VERIFIED,
        VERIFICATION_STATUS_FAILED,
        VERIFICATION_STATUS_SKIPPED,
        VERIFICATION_REASON_VALUE_MISMATCH,
        VERIFICATION_REASON_SELECTOR_NOT_FOUND,
    )
    from app.services.execution_verification_service import should_skip_verification

    verification_data: list[FieldVerificationData] = []

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

            if should_skip_verification(field):
                verification_data.append(
                    FieldVerificationData(
                        field_id=field.id,
                        selector=field.selector,
                        expected_value=None,
                        actual_value=None,
                        status=VERIFICATION_STATUS_SKIPPED,
                        reason="SENSITIVE_FIELD_SKIPPED",
                    )
                )
                continue

            actual_value = _read_field_value(page, field)
            if actual_value is None:
                verification_data.append(
                    FieldVerificationData(
                        field_id=field.id,
                        selector=field.selector,
                        expected_value=field.mapped_value,
                        actual_value=None,
                        status=VERIFICATION_STATUS_FAILED,
                        reason=VERIFICATION_REASON_SELECTOR_NOT_FOUND,
                        message="Could not read field value after fill",
                    )
                )
            elif _values_match(field, field.mapped_value, actual_value):
                verification_data.append(
                    FieldVerificationData(
                        field_id=field.id,
                        selector=field.selector,
                        expected_value=field.mapped_value,
                        actual_value=actual_value,
                        status=VERIFICATION_STATUS_VERIFIED,
                    )
                )
            else:
                verification_data.append(
                    FieldVerificationData(
                        field_id=field.id,
                        selector=field.selector,
                        expected_value=field.mapped_value,
                        actual_value=actual_value,
                        status=VERIFICATION_STATUS_FAILED,
                        reason=VERIFICATION_REASON_VALUE_MISMATCH,
                    )
                )

        except Exception as exc:
            _trace_fill_action(db, task_id, field, "fill", "failed", str(exc))
            verification_data.append(
                FieldVerificationData(
                    field_id=field.id,
                    selector=field.selector,
                    expected_value=field.mapped_value,
                    actual_value=None,
                    status=VERIFICATION_STATUS_FAILED,
                    reason=VERIFICATION_REASON_SELECTOR_NOT_FOUND,
                    message=str(exc),
                )
            )
            raise

    return verification_data


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
) -> tuple[Screenshot, list[FieldVerificationData]]:
    """Fill mapped input fields, stop before submission, and save a screenshot."""

    relative_path, screenshot_path = _new_screenshot_path(task_id)
    verification_data: list[FieldVerificationData] = []

    def fill_form(page: Page) -> None:
        nonlocal verification_data
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        _trace_browser_action(
            db,
            task_id,
            phase="fill",
            action="goto",
            result="success",
        )
        _wait_for_network_idle(page)
        verification_data = _fill_fields(page, fields, task_id=task_id, db=db)
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
    return screenshot, verification_data


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
