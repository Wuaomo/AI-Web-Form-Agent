"""Workflow template and runtime API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task
from app.schemas import (
    WorkflowReviewRequest,
    WorkflowRuntimeState,
    WorkflowTemplateResponse,
)
from app.services.agent_runtime import (
    SUPPORTED_WORKFLOWS,
    get_runtime_state,
    resume_from_review,
    start_runtime,
)
from app.workflow_templates import list_workflow_templates

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/templates", response_model=list[WorkflowTemplateResponse])
def list_templates() -> list[dict[str, object]]:
    """Return static workflow templates for UI selection."""

    return list_workflow_templates(include_disabled=True)


# ---------------------------------------------------------------------------
# Runtime endpoints (security_questionnaire only)
# ---------------------------------------------------------------------------


def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


def _ensure_supported_workflow(task: Task) -> None:
    workflow_type = task.workflow_type or "form_fill"
    if workflow_type not in SUPPORTED_WORKFLOWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Workflow type '{workflow_type}' is not supported by "
                f"the graph runtime. Supported: {sorted(SUPPORTED_WORKFLOWS)}"
            ),
        )


def _to_compact_state(raw_state: dict) -> dict:
    """Convert raw graph state into a compact, safe-for-API response.

    Filters out internal keys and redacts sensitive values from
    blocked fields.
    """
    suggestions = raw_state.get("suggestions", [])
    policy_decisions = {
        d.get("question_id"): d
        for d in raw_state.get("policy_result", {}).get("decisions", [])
    }

    safe_suggestions = []
    for s in suggestions:
        qid = s.get("question_id")
        decision = policy_decisions.get(qid, {})
        allowed = decision.get("allowed", True)

        suggested_value = s.get("suggested_value") or ""
        if not allowed:
            suggested_value = "[REDACTED]"

        safe_suggestions.append(
            {
                "field_id": int(s.get("field_id", 0)),
                "question_id": qid or "",
                "field_label": s.get("field_label", "")
                or s.get("suggestion_label", ""),
                "suggested_value": suggested_value,
                "confidence": float(s.get("confidence", 0.0)),
                "source": s.get("source", "rules"),
                "memory_source_ids": [
                    int(x) for x in (s.get("memory_source_ids") or [])
                ],
                "policy_source_ids": list(s.get("policy_source_ids") or []),
            }
        )

    policy_result = raw_state.get("policy_result", {})
    safe_policy_decisions = []
    for d in policy_result.get("decisions", []):
        safe_policy_decisions.append(
            {
                "question_id": d.get("question_id", ""),
                "decision": d.get("decision", ""),
                "allowed": bool(d.get("allowed", False)),
                "requires_review": bool(d.get("requires_review", False)),
                "reason": d.get("reason", ""),
                "risk_type": d.get("risk_type", ""),
                "risk_level": d.get("risk_level", ""),
            }
        )

    memory_hits = []
    for hit in raw_state.get("memory_hits", []):
        memory_hits.append(
            {
                "memory_id": hit.get("memory_id") or hit.get("id"),
                "field_label": hit.get("field_label"),
                "source_task_id": hit.get("source_task_id"),
                "reviewed_at": hit.get("reviewed_at"),
                "confidence": hit.get("confidence", 0.0),
            }
        )

    policy_sources = []
    for src in raw_state.get("policy_sources", []):
        policy_sources.append(
            {
                "document_id": src.get("document_id"),
                "title": src.get("title"),
                "section": src.get("section"),
                "snippet": src.get("snippet"),
                "relevance_score": src.get("relevance_score", 0.0),
            }
        )

    return {
        "task_id": raw_state.get("task_id"),
        "workflow_type": raw_state.get("workflow_type", ""),
        "status": raw_state.get("status", "PENDING"),
        "interrupt_at": raw_state.get("interrupt_at"),
        "current_node": raw_state.get("current_node"),
        "suggestions": safe_suggestions,
        "policy_result": {
            "total": policy_result.get("total", 0),
            "blocked": policy_result.get("blocked", 0),
            "decisions": safe_policy_decisions,
        },
        "memory_hits": memory_hits,
        "policy_sources": policy_sources,
        "error": raw_state.get("error"),
    }


@router.post(
    "/{task_id}/start",
    response_model=WorkflowRuntimeState,
    status_code=status.HTTP_200_OK,
)
def start_workflow(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Start the graph runtime for a task and run to the first interrupt.

    Only ``security_questionnaire`` workflows are supported.
    """

    task = _get_task_or_404(db, task_id)
    _ensure_supported_workflow(task)

    raw_state = start_runtime(db, task=task)
    return _to_compact_state(raw_state)


@router.get(
    "/{task_id}",
    response_model=WorkflowRuntimeState,
)
def get_workflow_state(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get the current compact runtime state for a task.

    Returns 404 if no runtime has been started for the task.
    """

    task = _get_task_or_404(db, task_id)
    _ensure_supported_workflow(task)

    raw_state = get_runtime_state(task_id)
    if raw_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No runtime state found for task {task_id}. "
                f"Call POST /workflows/{task_id}/start first."
            ),
        )

    return _to_compact_state(raw_state)


@router.post(
    "/{task_id}/review",
    response_model=WorkflowRuntimeState,
)
def review_workflow(
    task_id: int,
    body: WorkflowReviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Submit a review decision and resume the graph.

    Only works when the runtime is paused at the review gate.
    Does not expose a generic resume endpoint — review is the
    only way to advance past the review gate.
    """

    task = _get_task_or_404(db, task_id)
    _ensure_supported_workflow(task)

    raw_state = get_runtime_state(task_id)
    if raw_state is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No runtime state found for task {task_id}. "
                f"Call POST /workflows/{task_id}/start first."
            ),
        )

    if raw_state.get("interrupt_at") != "review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Runtime is not at review gate "
                f"(current: {raw_state.get('interrupt_at', 'unknown')})."
            ),
        )

    updated_state = resume_from_review(
        db,
        task=task,
        decision=body.decision,
        approvals=body.approvals,
    )

    return _to_compact_state(updated_state)
