"""Admin-only observability endpoints."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Task, TaskActionTrace
from app.schemas import TaskActionTraceResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Require X-Admin-Token only when ADMIN_API_TOKEN is configured."""

    if not config.ADMIN_API_TOKEN:
        return
    if x_admin_token != config.ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required",
        )


@router.get(
    "/tasks/{task_id}/traces",
    response_model=list[TaskActionTraceResponse],
    dependencies=[Depends(require_admin_token)],
)
def list_task_action_traces(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[TaskActionTrace]:
    """Return detailed action traces for one task."""

    if db.get(Task, task_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return list(
        db.scalars(
            select(TaskActionTrace)
            .where(TaskActionTrace.task_id == task_id)
            .order_by(TaskActionTrace.step, TaskActionTrace.id)
        )
    )

