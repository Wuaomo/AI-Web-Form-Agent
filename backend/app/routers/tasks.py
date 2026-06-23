"""Task-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionLog, Task
from app.schemas import ActionLogResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/logs", response_model=list[ActionLogResponse])
def list_task_logs(task_id: int, db: Session = Depends(get_db)) -> list[ActionLog]:
    """Return a task's logs in execution order."""

    if db.get(Task, task_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    statement = (
        select(ActionLog)
        .where(ActionLog.task_id == task_id)
        .order_by(ActionLog.step, ActionLog.created_at, ActionLog.id)
    )
    return list(db.scalars(statement))
