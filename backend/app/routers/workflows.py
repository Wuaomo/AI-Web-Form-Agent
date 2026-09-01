"""Workflow template and runtime API endpoints."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Task
from app.schemas import (
    WorkflowReviewRequest,
    WorkflowRuntimeState,
    WorkflowTemplateResponse,
)
from app.services.agent_runtime import (
    AgentPlanner,
    OpenAIStructuredPlannerAdapter,
    SUPPORTED_WORKFLOWS,
    build_default_tool_runtime,
    get_governed_runtime_state,
    get_runtime_state,
    register_configured_mcp_readonly_tools,
    register_configured_openapi_readonly_tools,
    resume_governed_runtime_from_review,
    start_governed_runtime,
    resume_from_review,
    start_runtime,
)
from app.services.agent_runtime.review_queue import (
    apply_review_decision_to_field_target,
    persist_review_decision,
    resolve_task_review_item_target,
)
from app.services.agent_runtime.schemas import ReviewDecision, RunMode
from app.services.agent_runtime.state_store import (
    restore_governed_runtime_state,
    save_governed_runtime_state,
)
from app.workflow_constants import (
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
    WORKFLOW_TYPE_VENDOR_ONBOARDING,
)
from app.workflow_templates import list_workflow_templates

router = APIRouter(prefix="/workflows", tags=["workflows"])


class GovernedReviewDecisionRequest(BaseModel):
    decision: Literal["approved", "edited", "rejected", "needs_more_evidence"]
    edited_value: Any = None
    reviewer_note: str | None = None


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


def _ensure_governed_workflow(task: Task) -> None:
    workflow_type = task.workflow_type or WORKFLOW_TYPE_FORM_FILL
    supported = {
        WORKFLOW_TYPE_FORM_FILL,
        WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
        WORKFLOW_TYPE_VENDOR_ONBOARDING,
    }
    if workflow_type not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Workflow type '{workflow_type}' is not supported by "
                f"the governed runtime. Supported: {sorted(supported)}"
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


def _to_governed_compact_state(raw_state: dict) -> dict:
    """Convert generic governed graph state into a safe compact response."""

    run = raw_state.get("run", {})
    return {
        "task_id": raw_state.get("task_id"),
        "workflow_type": raw_state.get("workflow_type", ""),
        "status": run.get("status", "FAILED"),
        "planner_mode": run.get("mode", raw_state.get("planner_mode")),
        "pending_review_count": _governed_pending_review_count(raw_state),
        "interrupt_at": raw_state.get("interrupt_at"),
        "plan": raw_state.get("plan", {}),
        "current_tool_call": raw_state.get("current_tool_call"),
        "governance_decision": raw_state.get("governance_decision"),
        "tool_result_count": len(raw_state.get("tool_results", [])),
        "tool_calls": _compact_governed_tool_calls(raw_state),
        "verification_result": raw_state.get("verification_result", {}),
        "error": raw_state.get("error"),
    }


def _compact_governed_tool_calls(raw_state: dict) -> list[dict[str, object]]:
    """Return summary-only tool call history without raw tool outputs."""

    steps_by_id = {
        step.get("step_id"): step
        for step in raw_state.get("plan", {}).get("steps", [])
        if step.get("step_id")
    }
    calls: list[dict[str, object]] = []

    for result in raw_state.get("tool_results", []):
        tool_call_id = str(result.get("tool_call_id", ""))
        plan_step_id = _plan_step_id_from_tool_call_id(tool_call_id, steps_by_id)
        step = steps_by_id.get(plan_step_id, {})
        governance = result.get("governance_decision") or {}
        calls.append(
            {
                "tool_call_id": tool_call_id,
                "plan_step_id": plan_step_id,
                "tool_name": step.get("tool_name") or "",
                "status": result.get("status"),
                "governance_decision": governance.get("decision"),
                "error": result.get("error"),
                "evidence_count": len(result.get("evidence_items") or []),
                "proposal_count": len(result.get("created_proposals") or []),
                "verification_candidate_count": len(
                    result.get("verification_candidates") or []
                ),
            }
        )

    current = raw_state.get("current_tool_call") or {}
    current_id = current.get("id")
    if current_id and all(call["tool_call_id"] != current_id for call in calls):
        governance = raw_state.get("governance_decision") or {}
        calls.append(
            {
                "tool_call_id": current_id,
                "plan_step_id": current.get("plan_step_id"),
                "tool_name": current.get("tool_name"),
                "status": current.get("status"),
                "governance_decision": governance.get("decision"),
                "error": current.get("error"),
                "evidence_count": 0,
                "proposal_count": 0,
                "verification_candidate_count": 0,
            }
        )

    return calls


def _governed_pending_review_count(raw_state: dict) -> int:
    raw_count = (raw_state.get("run") or {}).get("pending_review_count")
    if isinstance(raw_count, int) and not isinstance(raw_count, bool):
        return raw_count

    proposal_count = sum(
        1
        for result in raw_state.get("tool_results", [])
        if isinstance(result, dict)
        for proposal in result.get("created_proposals", [])
        if isinstance(proposal, dict) and proposal.get("status") == "PENDING"
    )
    if proposal_count:
        return proposal_count
    return 1 if raw_state.get("interrupt_at") in {"review", "approval"} else 0


def _plan_step_id_from_tool_call_id(
    tool_call_id: str,
    steps_by_id: dict[str, dict],
) -> str | None:
    for step_id in steps_by_id:
        if tool_call_id.endswith(f":{step_id}"):
            return step_id
    return None


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


@router.post(
    "/{task_id}/governed/start",
    status_code=status.HTTP_200_OK,
)
async def start_governed_workflow(
    task_id: int,
    planner_mode: RunMode = "deterministic",
    db: Session = Depends(get_db),
) -> dict:
    """Start the generic governed runtime for one task."""

    task = _get_task_or_404(db, task_id)
    _ensure_governed_workflow(task)
    if planner_mode == "llm_structured":
        if not config.OPENAI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="llm_structured planner is not configured",
            )

    runtime = build_default_tool_runtime()
    try:
        await register_configured_mcp_readonly_tools(runtime)
        register_configured_openapi_readonly_tools(runtime)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    planner = None
    if planner_mode == "llm_structured":
        planner = AgentPlanner(
            runtime=runtime,
            structured_adapter=OpenAIStructuredPlannerAdapter(
                api_key=config.OPENAI_API_KEY,
                model=config.OPENAI_MODEL,
            ),
        )

    raw_state = await start_governed_runtime(
        {
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "goal": task.description or "Complete the requested browser workflow.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "workflow_type": task.workflow_type or WORKFLOW_TYPE_FORM_FILL,
            "planner_mode": planner_mode,
            "available_tools": runtime.list_tool_metadata(),
        },
        runtime=runtime,
        planner=planner,
        metadata={"db": db, "task_id": task.id},
    )
    save_governed_runtime_state(db, task=task, raw_state=raw_state)
    return _to_governed_compact_state(raw_state)


@router.get(
    "/{task_id}/governed",
    status_code=status.HTTP_200_OK,
)
def get_governed_workflow_state(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get the latest compact state for the generic governed runtime."""

    task = _get_task_or_404(db, task_id)
    _ensure_governed_workflow(task)

    raw_state = get_governed_runtime_state(f"task-{task.id}")
    if raw_state is None:
        raw_state = restore_governed_runtime_state(db, task=task)
        if raw_state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No governed runtime state found for task {task_id}. "
                    f"Call POST /workflows/{task_id}/governed/start first."
                ),
            )

    return _to_governed_compact_state(raw_state)


@router.post(
    "/{task_id}/governed/review-items/{proposal_id}/decision",
    response_model=ReviewDecision,
)
async def apply_governed_review_item_decision(
    task_id: int,
    proposal_id: str,
    request: GovernedReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecision:
    """Persist a governed proposal review decision."""

    task = _get_task_or_404(db, task_id)
    _ensure_governed_workflow(task)
    target = resolve_task_review_item_target(db, task=task, proposal_id=proposal_id)
    if target is None or target.proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    if request.decision == "edited" and request.edited_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="edited_value is required for edited decisions",
        )

    decision = ReviewDecision(
        id=f"decision-{proposal_id}",
        proposal_id=proposal_id,
        decision=request.decision,
        edited_value=request.edited_value,
        reviewer_note=request.reviewer_note,
    )
    apply_review_decision_to_field_target(
        target,
        decision=request.decision,
        edited_value=request.edited_value,
    )
    persist_review_decision(db, decision=decision)
    db.flush()
    raw_state = get_governed_runtime_state(
        f"task-{task.id}"
    ) or restore_governed_runtime_state(db, task=task)
    if (
        request.decision in {"approved", "edited", "rejected"}
        and target.proposal is not None
        and target.proposal.run.pending_review_count == 0
        and raw_state is not None
        and raw_state.get("current_tool_call") is not None
        and raw_state.get("interrupt_at") == "review"
    ):
        raw_state = await resume_governed_runtime_from_review(
            f"task-{task.id}",
            runtime=build_default_tool_runtime(),
            metadata={"db": db, "task_id": task.id},
            state=raw_state,
        )
        save_governed_runtime_state(db, task=task, raw_state=raw_state)
    db.commit()
    return decision


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
