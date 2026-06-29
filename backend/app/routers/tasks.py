"""Task-related API endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import ActionLog, FormField, Profile, Screenshot, Task
from app.schemas import (
    ActionLogResponse,
    FormFieldMappingUpdate,
    FormFieldResponse,
    LLMProvider,
    MappingConfirmationResponse,
    ScreenshotResponse,
    SubmissionConfirmationResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.browser_executor import (
    fill_form_and_capture_screenshot,
    open_url_and_capture_screenshot,
    submit_form_and_capture_screenshot,
)
from app.services.field_mapper import (
    get_profile_value,
    map_fields_by_rules,
    map_fields_with_llm,
)
from app.services.form_extractor import ExtractedFormAnalysis, extract_form_analysis
from app.services.browser_session import prepare_login_session
from app.services.llm_provider_config import (
    get_provider_setup_hint,
    is_provider_configured,
    resolve_llm_provider,
)
from app.services.log_service import create_log

router = APIRouter(prefix="/tasks", tags=["tasks"])

NON_FILLABLE_FIELD_TYPES = {
    "button",
    "file",
    "submit",
    "reset",
    "image",
}


def is_fillable_field(field: FormField) -> bool:
    """Return whether a field can receive profile or manual input."""

    return (field.field_type or "").lower() not in NON_FILLABLE_FIELD_TYPES


def field_display_name(field: FormField) -> str:
    """Return a useful human label for a form field."""

    return field.label or field.name or field.placeholder or field.selector


def get_missing_required_fields(fields: list[FormField]) -> list[FormField]:
    """Find required fields that still need a value before filling."""

    return [
        field
        for field in fields
        if field.required
        and is_fillable_field(field)
        and field.mapped_value in (None, "")
    ]


def missing_required_detail(fields: list[FormField]) -> str:
    """Build a concise API error for required fields needing user input."""

    missing_names = ", ".join(field_display_name(field) for field in fields)
    return f"Required fields need values: {missing_names}"


def get_task_or_404(task_id: int, db: Session) -> Task:
    """Return a task or raise a consistent not-found response."""

    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


def get_task_field_or_404(task_id: int, field_id: int, db: Session) -> FormField:
    """Return a form field only when it belongs to the requested task."""

    statement = select(FormField).where(
        FormField.id == field_id,
        FormField.task_id == task_id,
    )
    field = db.scalar(statement)
    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form field not found",
        )
    return field


def get_next_log_step(task_id: int, db: Session) -> int:
    """Return the next chronological action-log step for a task."""

    current_step = db.scalar(
        select(func.max(ActionLog.step)).where(ActionLog.task_id == task_id)
    )
    return (current_step or 0) + 1


def mark_login_required(task: Task, db: Session) -> None:
    """Pause analysis until the user explicitly starts manual login."""

    task.status = "LOGIN_REQUIRED"
    create_log(
        task_id=task.id,
        step=get_next_log_step(task.id, db),
        action="login_required",
        message=(
            "The target URL opened a login page. User confirmation is needed "
            "before opening a login browser."
        ),
        status="WAITING",
        db=db,
    )


def save_extracted_fields(
    task: Task,
    analysis: ExtractedFormAnalysis,
    db: Session,
) -> None:
    """Persist extracted fields and move the task to mapping-ready state."""

    db.execute(delete(FormField).where(FormField.task_id == task.id))
    for field in analysis.fields:
        db.add(
            FormField(
                task_id=task.id,
                element_ref=field.element_ref,
                form_title=field.form_title,
                section_title=field.section_title,
                label=field.label,
                selector=field.selector,
                field_type=field.field_type,
                placeholder=field.placeholder,
                name=field.name,
                html_id=field.html_id,
                current_value=field.current_value,
                required=field.required,
            )
        )

    task.status = "MAPPING_READY"
    create_log(
        task_id=task.id,
        step=get_next_log_step(task.id, db),
        action="extract_fields",
        message=f"Extracted and saved {len(analysis.fields)} form fields.",
        status="SUCCESS",
        db=db,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(task_data: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """Create a task ready for form analysis."""

    if db.get(Profile, task_data.profile_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    task = Task(**task_data.model_dump(), status="CREATED")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    """Return all tasks ordered newest first."""

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    return list(db.scalars(statement))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """Return task details together with extracted form fields."""

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task_id)
    )
    task = db.scalar(statement)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.post("/{task_id}/analyze", response_model=TaskResponse)
async def analyze_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Open a task URL, extract its fields, and persist the result."""

    task = get_task_or_404(task_id, db)
    step = get_next_log_step(task.id, db)

    task.status = "ANALYZING"
    create_log(
        task_id=task.id,
        step=step,
        action="analyze_form",
        message=f"Opening {task.url} and analyzing form fields.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        analysis = await extract_form_analysis(task.url, task.profile_id)
        if analysis.login_required:
            mark_login_required(task, db)
        else:
            save_extracted_fields(task, analysis, db)
        db.commit()
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="analyze_form",
            message=f"Form analysis failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form analysis failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.get("/{task_id}/logs", response_model=list[ActionLogResponse])
def list_task_logs(task_id: int, db: Session = Depends(get_db)) -> list[ActionLog]:
    """Return a task's logs in execution order."""

    get_task_or_404(task_id, db)
    statement = (
        select(ActionLog)
        .where(ActionLog.task_id == task_id)
        .order_by(ActionLog.step, ActionLog.created_at, ActionLog.id)
    )
    return list(db.scalars(statement))


@router.post(
    "/{task_id}/screenshots",
    response_model=ScreenshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_task_screenshot(
    task_id: int,
    db: Session = Depends(get_db),
) -> Screenshot:
    """Open the task URL and capture a screenshot for browser testing."""

    task = get_task_or_404(task_id, db)
    screenshot = await open_url_and_capture_screenshot(
        task_id=task.id,
        url=task.url,
        profile_id=task.profile_id,
        stage="page_opened",
        db=db,
    )
    db.commit()
    db.refresh(screenshot)
    return screenshot


@router.get(
    "/{task_id}/screenshots",
    response_model=list[ScreenshotResponse],
)
def list_task_screenshots(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[Screenshot]:
    """Return all screenshots captured for a task."""

    get_task_or_404(task_id, db)
    statement = (
        select(Screenshot)
        .where(Screenshot.task_id == task_id)
        .order_by(Screenshot.created_at, Screenshot.id)
    )
    return list(db.scalars(statement))


@router.post(
    "/{task_id}/map-fields",
    response_model=list[FormFieldResponse],
)
def map_task_fields(
    task_id: int,
    mode: Literal["rules", "llm"] = "llm",
    provider: LLMProvider | None = None,
    db: Session = Depends(get_db),
) -> list[FormField]:
    """Generate and save Agent mappings, with a developer rule-mode override."""

    get_task_or_404(task_id, db)
    if mode == "llm":
        try:
            selected_provider = resolve_llm_provider(provider)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        if not is_provider_configured(selected_provider):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=get_provider_setup_hint(selected_provider),
            )
        return map_fields_with_llm(task_id, db, provider=selected_provider)
    return map_fields_by_rules(task_id, db)


@router.get(
    "/{task_id}/fields",
    response_model=list[FormFieldResponse],
)
def list_task_fields(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[FormField]:
    """Return extracted fields and their current mappings."""

    get_task_or_404(task_id, db)
    statement = (
        select(FormField)
        .where(FormField.task_id == task_id)
        .order_by(FormField.id)
    )
    return list(db.scalars(statement))


@router.put(
    "/{task_id}/fields/{field_id}",
    response_model=FormFieldResponse,
)
def update_task_field_mapping(
    task_id: int,
    field_id: int,
    mapping_data: FormFieldMappingUpdate,
    db: Session = Depends(get_db),
) -> FormField:
    """Apply a user's correction or clear a field mapping."""

    task = get_task_or_404(task_id, db)
    field = get_task_field_or_404(task_id, field_id, db)
    changes = mapping_data.model_dump(exclude_unset=True)

    if "mapped_profile_key" in changes:
        profile_key = changes["mapped_profile_key"]
        field.mapped_profile_key = profile_key
        if profile_key is None:
            field.mapped_value = None
            field.confidence = None
        elif "mapped_value" not in changes:
            field.mapped_value = get_profile_value(task.profile, profile_key)
            field.confidence = 1.0 if field.mapped_value is not None else None

    if "mapped_value" in changes:
        field.mapped_value = changes["mapped_value"]
        field.confidence = 1.0 if field.mapped_value is not None else None

    db.commit()
    db.refresh(field)
    return field


@router.post(
    "/{task_id}/confirm-mapping",
    response_model=MappingConfirmationResponse,
)
def confirm_task_mapping(
    task_id: int,
    db: Session = Depends(get_db),
) -> MappingConfirmationResponse:
    """Mark the task's reviewed field mapping as ready for filling."""

    task = get_task_or_404(task_id, db)
    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    task.status = "READY_TO_FILL"
    db.commit()
    return MappingConfirmationResponse(task_id=task.id, status=task.status)


@router.post("/{task_id}/fill", response_model=TaskResponse)
async def fill_task_form(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Fill mapped fields and pause before any final submission."""

    task = get_task_or_404(task_id, db)
    if task.status != "READY_TO_FILL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Review and confirm mapping before filling",
        )

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    mapped_fields = [field for field in fields if field.mapped_value]
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    if not mapped_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No mapped fields are ready to fill",
        )

    step = get_next_log_step(task.id, db)
    task.status = "FILLING"
    create_log(
        task_id=task.id,
        step=step,
        action="fill_form",
        message=f"Filling {len(mapped_fields)} mapped fields.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        await fill_form_and_capture_screenshot(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            fields=mapped_fields,
            stage="filled_form",
            db=db,
        )
        task.status = "WAITING_APPROVAL"
        create_log(
            task_id=task.id,
            step=step + 1,
            action="fill_form",
            message="Filled mapped fields and paused before submission.",
            status="SUCCESS",
            db=db,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="fill_form",
            message=f"Form filling failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form filling failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.post("/{task_id}/login-and-analyze", response_model=TaskResponse)
async def login_and_analyze_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Let the user log in, then retry extracting the original target form."""

    task = get_task_or_404(task_id, db)
    step = get_next_log_step(task.id, db)
    task.status = "LOGIN_IN_PROGRESS"
    create_log(
        task_id=task.id,
        step=step,
        action="manual_login",
        message="Opened login browser. Close it after login to continue analysis.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        _, timed_out = await prepare_login_session(
            url=task.url,
            profile_id=task.profile_id,
        )
        if timed_out:
            task.status = "LOGIN_REQUIRED"
            create_log(
                task_id=task.id,
                step=get_next_log_step(task.id, db),
                action="manual_login",
                message="Login browser timed out before it was closed.",
                status="TIMEOUT",
                db=db,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Login browser timed out. Try logging in again.",
            )

        task.status = "ANALYZING"
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="resume_after_login",
            message="Reopened the original URL with saved login state.",
            status="STARTED",
            db=db,
        )
        db.commit()

        analysis = await extract_form_analysis(task.url, task.profile_id)
        if analysis.login_required:
            mark_login_required(task, db)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Login is still required. Complete login and close the browser window.",
            )

        save_extracted_fields(task, analysis, db)
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="manual_login",
            message=f"Login and analysis failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login and analysis failed",
        ) from exc

    statement = (
        select(Task)
        .options(selectinload(Task.form_fields))
        .where(Task.id == task.id)
    )
    return db.scalar(statement)


@router.post(
    "/{task_id}/confirm-submit",
    response_model=SubmissionConfirmationResponse,
)
async def confirm_task_submission(
    task_id: int,
    db: Session = Depends(get_db),
) -> SubmissionConfirmationResponse:
    """Submit the reviewed browser form after explicit user approval."""

    task = get_task_or_404(task_id, db)
    if task.status != "WAITING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is not waiting for approval",
        )

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    mapped_fields = [field for field in fields if field.mapped_value]
    missing_required_fields = get_missing_required_fields(fields)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=missing_required_detail(missing_required_fields),
        )

    if not mapped_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No mapped fields are ready to submit",
        )

    step = get_next_log_step(task.id, db)
    create_log(
        task_id=task.id,
        step=step,
        action="confirm_submit",
        message="User approved final form submission.",
        status="STARTED",
        db=db,
    )
    db.commit()

    try:
        await submit_form_and_capture_screenshot(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            fields=mapped_fields,
            stage="submitted_form",
            db=db,
        )
        task.status = "COMPLETED"
        create_log(
            task_id=task.id,
            step=step + 1,
            action="submit_form",
            message="Submitted the reviewed form after user approval.",
            status="SUCCESS",
            db=db,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        task = get_task_or_404(task_id, db)
        task.status = "FAILED"
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="submit_form",
            message=f"Form submission failed: {exc}",
            status="FAILED",
            db=db,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form submission failed",
        ) from exc

    return SubmissionConfirmationResponse(task_id=task.id, status=task.status)
