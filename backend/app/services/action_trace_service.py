"""Persistence helpers for admin-only task action traces."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TaskActionTrace


def _next_trace_step(db: Session, task_id: int) -> int:
    """Return the next trace step number for one task."""

    current_step = db.scalar(
        select(func.max(TaskActionTrace.step)).where(
            TaskActionTrace.task_id == task_id
        )
    )
    return (current_step or 0) + 1


def record_action_trace(
    db: Session,
    *,
    task_id: int,
    phase: str,
    action: str,
    result: str,
    selector: str | None = None,
    field_id: int | None = None,
    input_value: str | None = None,
    error_message: str | None = None,
    screenshot_id: int | None = None,
) -> TaskActionTrace:
    """Persist one browser automation trace entry."""

    trace = TaskActionTrace(
        task_id=task_id,
        step=_next_trace_step(db, task_id),
        phase=phase,
        action=action,
        selector=selector,
        field_id=field_id,
        input_value=input_value,
        result=result,
        error_message=error_message,
        screenshot_id=screenshot_id,
    )
    db.add(trace)
    db.flush()
    return trace

