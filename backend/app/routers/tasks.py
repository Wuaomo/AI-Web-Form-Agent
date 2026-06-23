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
    MappingConfirmationResponse,
    ScreenshotResponse,
    SubmissionConfirmationResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.browser_executor import open_url_and_capture_screenshot
from app.services.field_mapper import map_fields_by_rules, map_fields_with_llm
from app.services.form_extractor import extract_form_fields
from app.services.log_service import create_log

router = APIRouter(prefix="/tasks", tags=["tasks"])


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
        extracted_fields = await extract_form_fields(task.url)

        # Re-analysis replaces stale fields instead of creating duplicates.
        db.execute(delete(FormField).where(FormField.task_id == task.id))
        for field in extracted_fields:
            db.add(
                FormField(
                    task_id=task.id,
                    label=field.label,
                    selector=field.selector,
                    field_type=field.field_type,
                    placeholder=field.placeholder,
                    name=field.name,
                    html_id=field.html_id,
                    required=field.required,
                )
            )

        task.status = "MAPPING_READY"
        create_log(
            task_id=task.id,
            step=step + 1,
            action="extract_fields",
            message=f"Extracted and saved {len(extracted_fields)} form fields.",
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
    mode: Literal["rules", "llm"] = "rules",
    db: Session = Depends(get_db),
) -> list[FormField]:
    """Generate and save rule-based or LLM-assisted profile mappings."""

    get_task_or_404(task_id, db)
    if mode == "llm":
        return map_fields_with_llm(task_id, db)
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
            field.mapped_value = getattr(task.profile, profile_key)
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
    task.status = "MAPPING_READY"
    db.commit()
    return MappingConfirmationResponse(task_id=task.id, status=task.status)


@router.post(
    "/{task_id}/confirm-submit",
    response_model=SubmissionConfirmationResponse,
)
def confirm_task_submission(
    task_id: int,
    db: Session = Depends(get_db),
) -> SubmissionConfirmationResponse:
    """Record user approval and complete the task without submitting the form."""

    task = get_task_or_404(task_id, db)
    if task.status != "WAITING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is not waiting for approval",
        )

    create_log(
        task_id=task.id,
        step=get_next_log_step(task.id, db),
        action="confirm_submit",
        message="User confirmed submission",
        status="SUCCESS",
        db=db,
    )
    task.status = "COMPLETED"
    db.commit()

    return SubmissionConfirmationResponse(task_id=task.id, status=task.status)
