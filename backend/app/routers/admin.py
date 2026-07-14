"""Admin-only observability endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Task, TaskActionTrace, WorkflowMemoryItem
from app.schemas import TaskActionTraceResponse

router = APIRouter(prefix="/admin", tags=["admin"])
MEMORY_STALE_AFTER_DAYS = 90


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Require X-Admin-Token only when ADMIN_API_TOKEN is configured."""

    if not config.ADMIN_API_TOKEN:
        return
    if x_admin_token != config.ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required",
        )


def _as_aware_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _workflow_memory_response(item: WorkflowMemoryItem) -> dict[str, object]:
    reviewed_at = _as_aware_utc(item.last_used_at or item.created_at)
    stale = False
    if reviewed_at is not None:
        stale = (datetime.now(timezone.utc) - reviewed_at).days > MEMORY_STALE_AFTER_DAYS
    return {
        "id": item.id,
        "memory_type": item.memory_type,
        "workflow_type": item.workflow_type,
        "source_domain": item.source_domain,
        "field_text": item.field_text,
        "mapped_profile_key": item.mapped_profile_key,
        "success_count": item.success_count,
        "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
        "stale": stale,
    }


@router.get(
    "/workflow-memory",
    dependencies=[Depends(require_admin_token)],
)
def list_workflow_memory(
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    """Return reviewed workflow memory items."""

    items = db.scalars(
        select(WorkflowMemoryItem).order_by(WorkflowMemoryItem.created_at.desc())
    )
    return [_workflow_memory_response(item) for item in items]


@router.delete(
    "/workflow-memory/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_token)],
)
def delete_workflow_memory(
    memory_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete one reviewed workflow memory item."""

    item = db.get(WorkflowMemoryItem, memory_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow memory item not found",
        )
    db.delete(item)
    db.commit()


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

