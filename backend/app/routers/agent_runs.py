"""Agent runtime API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from sqlalchemy import select

from app.models import AgentRun, FormField, TaskCheckpoint
from app.routers.workflows import _to_governed_compact_state
from app.services.agent_runtime.review_queue import load_or_create_task_review_proposals
from app.services.agent_runtime.schemas import Proposal
from app.services.agent_runtime.state_store import restore_governed_runtime_state

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("/{run_id}", status_code=status.HTTP_200_OK)
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    """Return compact persisted AgentRun state."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )

    raw_state = restore_governed_runtime_state(db, task=run.task, run_id=run_id)
    if raw_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )
    return {"run_id": run_id, **_to_governed_compact_state(raw_state)}


@router.get("/{run_id}/review-items", response_model=list[Proposal])
def list_agent_run_review_items(
    run_id: str,
    db: Session = Depends(get_db),
) -> list[Proposal]:
    """Return proposal-backed Review Queue items for an AgentRun."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )
    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == run.legacy_task_id)
            .order_by(FormField.id)
        )
    )
    checkpoints = list(
        db.scalars(
            select(TaskCheckpoint)
            .where(TaskCheckpoint.task_id == run.legacy_task_id)
            .order_by(TaskCheckpoint.created_at)
        )
    )
    proposals = load_or_create_task_review_proposals(
        db,
        task=run.task,
        fields=fields,
        checkpoints=checkpoints,
    )
    db.commit()
    return proposals
