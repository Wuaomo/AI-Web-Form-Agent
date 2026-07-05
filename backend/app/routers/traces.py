"""Read-only workflow trace endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, WorkflowSpan
from app.schemas import WorkflowSpanResponse
from app.services.workflow_trace_service import list_spans_for_task

router = APIRouter(prefix="/tasks", tags=["traces"])


@router.get(
    "/{task_id}/trace",
    response_model=list[WorkflowSpanResponse],
)
def get_task_trace(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[WorkflowSpan]:
    """Return workflow spans for one task."""

    if db.get(Task, task_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return list_spans_for_task(db, task_id)
