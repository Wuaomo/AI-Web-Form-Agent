"""Execute browser actions for form automation tasks."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Locator, Page
from playwright.async_api import async_playwright
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.database import BACKEND_DIR, SessionLocal
from app.models import ActionLog, FormField, Screenshot, Task
from app.services.log_service import create_log
from app.services.safety_checker import detect_submit_like_actions

SCREENSHOTS_DIR = BACKEND_DIR / "screenshots"
TRUE_VALUES = {"1", "true", "yes", "on", "checked"}
FALSE_VALUES = {"0", "false", "no", "off", "unchecked", ""}


def _next_log_step(task_id: int, db: Session) -> int:
    """Return the next action-log step for a task."""

    current_step = db.scalar(
        select(func.max(ActionLog.step)).where(ActionLog.task_id == task_id)
    )
    return (current_step or 0) + 1


async def _open_task_page(page: Page, url: str) -> None:
    """Open a task URL and briefly wait for client-rendered content."""

    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    try:
        await page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeoutError:
        pass


def _screenshot_path(task_id: int) -> Path:
    """Create a unique path for a task screenshot."""

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{timestamp}_{uuid4().hex[:8]}.png"
    return SCREENSHOTS_DIR / filename


async def _save_screenshot(
    page: Page,
    task_id: int,
    stage: str,
    db: Session,
) -> Screenshot:
    """Capture the current page and persist its metadata."""

    screenshot_path = _screenshot_path(task_id)
    await page.screenshot(path=str(screenshot_path), full_page=True)
    screenshot = Screenshot(
        task_id=task_id,
        file_path=screenshot_path.relative_to(BACKEND_DIR).as_posix(),
        stage=stage,
    )
    db.add(screenshot)
    db.flush()
    return screenshot


def _parse_boolean(value: str) -> bool:
    """Convert an explicit mapped string to a checkbox/radio state."""

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(
        "Expected a boolean value such as true/false, yes/no, or 1/0"
    )


async def _fill_select(locator: Locator, value: str) -> str:
    """Select by option value first, then by visible label."""

    try:
        selected = await locator.select_option(value=value, timeout=1_000)
    except PlaywrightTimeoutError:
        selected = []
    if not selected:
        try:
            selected = await locator.select_option(label=value, timeout=1_000)
        except PlaywrightTimeoutError:
            selected = []
    if not selected:
        raise ValueError(f'No select option matched "{value}"')
    return f'Selected "{value}"'


async def _fill_radio(locator: Locator, value: str) -> str:
    """Check a radio option when its value matches the mapping."""

    option_value = await locator.get_attribute("value")
    if option_value is not None:
        should_check = option_value.strip().lower() == value.strip().lower()
    else:
        should_check = _parse_boolean(value)

    if not should_check:
        return f'Radio option did not match "{value}"; left unchanged'

    await locator.check()
    return f'Checked radio option "{option_value or value}"'


async def _fill_field(page: Page, field: FormField) -> str:
    """Fill one mapped field and return a log-friendly result."""

    value = field.mapped_value
    if value is None:
        raise ValueError("Field has no mapped value")

    locator = page.locator(field.selector)
    if await locator.count() == 0:
        raise ValueError(f'Selector not found: "{field.selector}"')

    locator = locator.first
    field_type = (field.field_type or "text").lower()

    if field_type == "checkbox":
        should_check = _parse_boolean(value)
        if should_check:
            await locator.check()
            return "Checked checkbox"
        await locator.uncheck()
        return "Unchecked checkbox"

    if field_type == "radio":
        return await _fill_radio(locator, value)

    if field_type == "select":
        return await _fill_select(locator, value)

    if field_type == "textarea":
        await locator.fill(value)
        return "Filled textarea"

    if field_type in {"button", "submit", "reset", "file", "image", "hidden"}:
        raise ValueError(f'Unsupported field type "{field_type}"')

    await locator.fill(value)
    return f'Filled {field_type} input'


async def fill_task_form(
    task_id: int,
    db: Session | None = None,
) -> Task:
    """Fill confirmed mappings, save a screenshot, and pause for approval."""

    owns_session = db is None
    session = db or SessionLocal()

    try:
        statement = (
            select(Task)
            .options(selectinload(Task.profile), selectinload(Task.form_fields))
            .where(Task.id == task_id)
        )
        task = session.scalar(statement)
        if task is None:
            raise ValueError("Task not found")
        if task.status != "MAPPING_READY":
            raise ValueError("Task mapping must be confirmed before filling")

        mapped_fields = [
            field
            for field in sorted(task.form_fields, key=lambda item: item.id)
            if field.mapped_value is not None
        ]
        if not mapped_fields:
            raise ValueError("Task has no mapped form fields to fill")

        step = _next_log_step(task.id, session)
        task.status = "FILLING"
        create_log(
            task_id=task.id,
            step=step,
            action="fill_form",
            message=f"Opening {task.url} to fill {len(mapped_fields)} mapped fields.",
            status="STARTED",
            db=session,
        )
        session.commit()
        step += 1

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": 1440, "height": 900}
                )
                await _open_task_page(page, task.url)

                for field in mapped_fields:
                    field_name = field.label or field.name or field.selector
                    try:
                        result = await _fill_field(page, field)
                        log_status = "SUCCESS"
                        message = f'{result}: "{field_name}".'
                    except Exception as exc:
                        log_status = "FAILED"
                        message = f'Could not fill "{field_name}": {exc}'

                    create_log(
                        task_id=task.id,
                        step=step,
                        action="fill_field",
                        message=message,
                        status=log_status,
                        db=session,
                    )
                    session.commit()
                    step += 1

                screenshot = await _save_screenshot(
                    page=page,
                    task_id=task.id,
                    stage="form_filled",
                    db=session,
                )
                create_log(
                    task_id=task.id,
                    step=step,
                    action="capture_screenshot",
                    message=f"Saved filled form screenshot to {screenshot.file_path}.",
                    status="SUCCESS",
                    db=session,
                )
                session.commit()
                step += 1

                safety_result = await detect_submit_like_actions(page)
                if safety_result.requires_approval:
                    pause_reason = "; ".join(safety_result.reasons)
                else:
                    pause_reason = (
                        "Form filling is complete. Human approval is required "
                        "before any submission."
                    )

                task.status = "WAITING_APPROVAL"
                create_log(
                    task_id=task.id,
                    step=step,
                    action="safety_pause",
                    message=pause_reason,
                    status="WAITING_APPROVAL",
                    db=session,
                )
                session.commit()
            finally:
                await browser.close()

        session.refresh(task)
        if owns_session:
            session.expunge(task)
        return task
    except Exception as exc:
        session.rollback()
        task = session.get(Task, task_id)
        if task is not None and task.status == "FILLING":
            task.status = "FAILED"
            create_log(
                task_id=task.id,
                step=_next_log_step(task.id, session),
                action="fill_form",
                message=f"Form filling stopped because of an execution error: {exc}",
                status="FAILED",
                db=session,
            )
            session.commit()
        raise
    finally:
        if owns_session:
            session.close()


async def open_url_and_capture_screenshot(
    task_id: int,
    url: str,
    stage: str = "page_opened",
    db: Session | None = None,
) -> Screenshot:
    """Open a URL, wait for it to load, and save a full-page screenshot."""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await _open_task_page(page, url)
            screenshot_path = _screenshot_path(task_id)
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
