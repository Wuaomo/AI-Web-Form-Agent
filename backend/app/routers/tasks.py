"""Task-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionLog, FormField, Screenshot, Task
from app.schemas import (
    ActionLogResponse,
    FormFieldMappingUpdate,
    FormFieldResponse,
    MappingConfirmationResponse,
    ScreenshotResponse,
)
from app.services.browser_executor import open_url_and_capture_screenshot
from app.services.field_mapper import map_fields_by_rules

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
    db: Session = Depends(get_db),
) -> list[FormField]:
    """Generate and save rule-based mappings from the task's profile."""

    get_task_or_404(task_id, db)
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
