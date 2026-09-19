"""Agent runtime API endpoints."""

from typing import Any, Literal, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import AgentRun, FormField, TaskCheckpoint
from app.routers.tasks import fill_agent_run_task_form, submit_reviewed_task_form
from app.routers.workflows import _to_governed_compact_state
from app.schemas import JobResponse, SubmissionConfirmationResponse, TaskResponse
from app.services.agent_runtime.review_queue import (
    apply_review_queue_decision,
    load_or_create_task_review_proposals,
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


class AgentRunContinueRequest(BaseModel):
    action: Literal["fill_form", "submit_form"] = "fill_form"


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


@router.post(
    "/{run_id}/continue",
    response_model=Union[TaskResponse, JobResponse, SubmissionConfirmationResponse],
)
async def continue_agent_run(
    run_id: str,
    request: AgentRunContinueRequest | None = None,
    db: Session = Depends(get_db),
) -> object:
    """Continue an AgentRun through the shared reviewed browser-write path."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent run state found for {run_id}.",
        )
    if (request or AgentRunContinueRequest()).action == "submit_form":
        return await submit_reviewed_task_form(
            run.legacy_task_id,
            db,
            agent_run_id=run.id,
        )
    return await fill_agent_run_task_form(
        task_id=run.legacy_task_id,
        agent_run_id=run.id,
        db=db,
        enqueue_async=config.ASYNC_JOBS_ENABLED,
    )


async def continue_agent_run_fill_job(
    run_id: str,
    db: Session,
    *,
    task_id: int | None = None,
) -> object:
    """Execute an AgentRun-backed async fill job without re-enqueueing it."""

    run = db.get(AgentRun, run_id)
    if run is None or run.task is None:
        raise ValueError(f"No agent run state found for {run_id}.")
    if task_id is not None and run.legacy_task_id != task_id:
        raise ValueError(f"Agent run {run_id} does not belong to task {task_id}.")
    return await fill_agent_run_task_form(
        task_id=run.legacy_task_id,
        agent_run_id=run.id,
        db=db,
        enqueue_async=False,
    )


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
        run_id=run.id,
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
    try:
        result = apply_review_queue_decision(
            db,
            task=run.task,
            proposal_id=proposal_id,
            decision=request.decision,
            edited_value=request.edited_value,
            reviewer_note=request.reviewer_note,
            run_id=run_id,
            require_proposal=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    db.commit()
    return result.decision
