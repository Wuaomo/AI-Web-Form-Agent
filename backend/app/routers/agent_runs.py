"""Agent runtime API endpoints."""

from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentRun, FormField, TaskCheckpoint
from app.routers.tasks import fill_task_form
from app.routers.workflows import _to_governed_compact_state
from app.schemas import JobResponse, TaskResponse
from app.services.agent_runtime.review_queue import (
    apply_review_decision_to_field_target,
    load_or_create_task_review_proposals,
    persist_review_decision,
    resolve_task_review_item_target,
)
from app.services.agent_runtime.schemas import (
    Proposal,
    ReviewDecision,
    ReviewDecisionValue,
)
from app.services.agent_runtime.state_store import restore_governed_runtime_state

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


class AgentRunReviewDecisionRequest(BaseModel):
    decision: ReviewDecisionValue
    edited_value: Any = None
    reviewer_note: str | None = None


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


@router.post("/{run_id}/continue", response_model=Union[TaskResponse, JobResponse])
async def continue_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> object:
    """Continue an AgentRun through the shared reviewed browser-write path."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )
    return await fill_task_form(run.legacy_task_id, db=db)


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


@router.post(
    "/{run_id}/review-items/{proposal_id}/decision",
    response_model=ReviewDecision,
)
def apply_agent_run_review_item_decision(
    run_id: str,
    proposal_id: str,
    request: AgentRunReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecision:
    """Persist a proposal review decision through the AgentRun boundary."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )
    target = resolve_task_review_item_target(db, task=run.task, proposal_id=proposal_id)
    if target is None or target.proposal is None or target.proposal.run_id != run_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    if request.decision == "edited" and request.edited_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="edited_value is required for edited decisions",
        )

    apply_review_decision_to_field_target(
        target,
        decision=request.decision,
        edited_value=request.edited_value,
    )
    decision = ReviewDecision(
        id=f"decision-{proposal_id}",
        proposal_id=proposal_id,
        decision=request.decision,
        edited_value=request.edited_value,
        reviewer_note=request.reviewer_note,
    )
    persist_review_decision(db, decision=decision)
    db.commit()
    return decision
