"""SQLite persistence helpers for the governed runtime migration slice."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentPlan, AgentRun, AgentToolCall, AgentToolResult, Task
from app.services.agent_runtime.review_queue import (
    persist_task_review_proposals,
    refresh_pending_review_count,
)
from app.services.agent_runtime.schemas import Proposal
from app.workflow_constants import WORKFLOW_TYPE_FORM_FILL


def save_governed_runtime_state(
    db: Session,
    *,
    task: Task,
    raw_state: dict[str, Any],
) -> AgentRun:
    """Double-write the current governed run and plan into SQLite."""

    run_payload = raw_state.get("run") or {}
    plan_payload = raw_state.get("plan") or {}
    run_id = (
        str(raw_state.get("run_id") or run_payload.get("id") or f"task-{task.id}")
    )
    workflow_hint = (
        raw_state.get("workflow_type")
        or run_payload.get("context", {}).get("workflow_type")
        or task.workflow_type
        or WORKFLOW_TYPE_FORM_FILL
    )

    run = db.get(AgentRun, run_id)
    if run is None:
        run = AgentRun(id=run_id, legacy_task_id=task.id)
        db.add(run)

    run.legacy_task_id = task.id
    run.goal = str(
        run_payload.get("goal")
        or raw_state.get("goal")
        or task.description
        or "Complete the requested browser workflow."
    )
    run.target_url = (
        run_payload.get("target_url") or raw_state.get("target_url") or task.url
    )
    run.profile_id = run_payload.get("profile_id") or raw_state.get("profile_id")
    run.workflow_hint = str(workflow_hint)
    run.status = str(run_payload.get("status") or "FAILED")
    run.mode = str(
        run_payload.get("mode") or raw_state.get("planner_mode") or "deterministic"
    )
    run.current_plan_id = plan_payload.get("id") or run_payload.get("current_plan_id")
    run.pending_review_count = (
        1 if raw_state.get("interrupt_at") in {"review", "approval"} else 0
    )
    run.final_result = run_payload.get("final_result") or {}
    run.error = run_payload.get("error") or raw_state.get("error")

    if plan_payload.get("id"):
        plan = db.get(AgentPlan, str(plan_payload["id"]))
        if plan is None:
            plan = AgentPlan(
                id=str(plan_payload["id"]),
                run_id=run_id,
                version=int(plan_payload.get("version") or 1),
                goal=run.goal,
                steps_json="[]",
                created_by=str(plan_payload.get("created_by") or run.mode),
            )
            db.add(plan)
        plan.run_id = run_id
        plan.version = int(plan_payload.get("version") or 1)
        plan.goal = str(plan_payload.get("goal") or run.goal)
        plan.steps = list(plan_payload.get("steps") or [])
        plan.created_by = str(plan_payload.get("created_by") or run.mode)

    _save_tool_calls_and_results(
        db,
        run_id=run_id,
        plan_payload=plan_payload,
        raw_state=raw_state,
    )
    _save_created_proposals(db, task=task, run_id=run_id, raw_state=raw_state)
    refresh_pending_review_count(db, run_id=run_id)

    db.commit()
    db.refresh(run)
    return run


def save_fill_form_runtime_state(
    db: Session,
    *,
    task: Task,
    tool_result: Any,
) -> AgentRun:
    """Persist compact runtime state for a legacy fill_form browser write."""

    return save_governed_runtime_state(
        db,
        task=task,
        raw_state={
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "workflow_type": task.workflow_type,
            "planner_mode": "deterministic",
            "run": {
                "id": f"task-{task.id}",
                "goal": task.description or "Fill reviewed fields.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "status": "WAITING_APPROVAL",
                "mode": "deterministic",
            },
            "plan": {
                "id": f"task-{task.id}:browser-write-plan:1",
                "version": 1,
                "goal": task.description or "Fill reviewed fields.",
                "steps": [
                    {
                        "step_id": "fill_form",
                        "tool_name": "fill_form",
                        "reason": "Fill reviewed browser fields.",
                        "input_json": {"task_id": task.id},
                        "risk_level": "medium",
                    }
                ],
                "created_by": "deterministic",
            },
            "tool_results": [tool_result.model_dump(mode="json")],
        },
    )


def restore_governed_runtime_state(
    db: Session,
    *,
    task: Task,
) -> dict[str, Any] | None:
    """Return a compact raw-state equivalent from persisted run/plan rows."""

    run = db.execute(
        select(AgentRun)
        .where(AgentRun.legacy_task_id == task.id)
        .order_by(AgentRun.updated_at.desc())
    ).scalars().first()
    if run is None:
        return None

    plan = _load_current_plan(db, run)
    tool_calls = _load_tool_calls(db, run, plan)
    current_tool_call = _current_tool_call_payload(tool_calls, run.status)
    return {
        "run_id": run.id,
        "task_id": task.id,
        "workflow_type": (
            run.workflow_hint or task.workflow_type or WORKFLOW_TYPE_FORM_FILL
        ),
        "planner_mode": run.mode,
        "interrupt_at": _interrupt_for_status(run.status),
        "run": {
            "id": run.id,
            "goal": run.goal,
            "target_url": run.target_url,
            "profile_id": run.profile_id,
            "status": run.status,
            "mode": run.mode,
            "context": {
                "task_id": task.id,
                "workflow_type": run.workflow_hint,
            },
            "current_plan_id": run.current_plan_id,
            "final_result": run.final_result,
            "error": run.error,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        },
        "plan": _plan_payload(plan),
        "current_tool_call": current_tool_call,
        "governance_decision": (
            current_tool_call.get("governance_decision")
            if current_tool_call
            else None
        ),
        "tool_results": [
            _tool_result_payload(call.result)
            for call in tool_calls
            if call.result is not None
        ],
        "verification_result": {},
        "error": run.error,
    }


def _load_current_plan(db: Session, run: AgentRun) -> AgentPlan | None:
    if run.current_plan_id:
        plan = db.get(AgentPlan, run.current_plan_id)
        if plan is not None:
            return plan
    return db.execute(
        select(AgentPlan)
        .where(AgentPlan.run_id == run.id)
        .order_by(AgentPlan.version.desc())
    ).scalars().first()


def _plan_payload(plan: AgentPlan | None) -> dict[str, Any]:
    if plan is None:
        return {}
    return {
        "id": plan.id,
        "run_id": plan.run_id,
        "version": plan.version,
        "goal": plan.goal,
        "steps": plan.steps,
        "created_by": plan.created_by,
        "created_at": plan.created_at,
    }


def _save_tool_calls_and_results(
    db: Session,
    *,
    run_id: str,
    plan_payload: dict[str, Any],
    raw_state: dict[str, Any],
) -> None:
    steps = _steps_by_id(plan_payload)
    saved_call_ids: set[str] = set()
    for result_payload in _dict_items(raw_state.get("tool_results")):
        call_id = str(result_payload.get("tool_call_id") or "")
        if not call_id:
            continue
        call_payload = _tool_call_from_result(
            run_id=run_id,
            result_payload=result_payload,
            steps=steps,
        )
        _upsert_tool_call(db, call_payload)
        _upsert_tool_result(db, call_id, result_payload)
        saved_call_ids.add(call_id)

    current = raw_state.get("current_tool_call")
    if not isinstance(current, dict):
        return
    current_id = str(current.get("id") or "")
    if not current_id or current_id in saved_call_ids:
        return
    _upsert_tool_call(
        db,
        {
            **current,
            "run_id": run_id,
            "governance_decision": raw_state.get("governance_decision") or {},
        },
    )


def _tool_call_from_result(
    *,
    run_id: str,
    result_payload: dict[str, Any],
    steps: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    call_id = str(result_payload["tool_call_id"])
    plan_step_id = _plan_step_id_from_tool_call_id(call_id, steps)
    step = steps.get(plan_step_id or "", {})
    governance = _dict_value(result_payload.get("governance_decision"))
    return {
        "id": call_id,
        "run_id": run_id,
        "plan_step_id": plan_step_id,
        "tool_name": step.get("tool_name") or "",
        "input_json": step.get("input_json") or {},
        "status": result_payload.get("status") or "FAILED",
        "risk_level": step.get("risk_level") or governance.get("risk_level") or "low",
        "governance_decision": governance,
        "error": result_payload.get("error"),
    }


def _upsert_tool_call(db: Session, payload: dict[str, Any]) -> AgentToolCall:
    call_id = str(payload["id"])
    call = db.get(AgentToolCall, call_id)
    if call is None:
        call = AgentToolCall(
            id=call_id,
            run_id=str(payload["run_id"]),
            tool_name=str(payload.get("tool_name") or ""),
            input_payload_json="{}",
            status=str(payload.get("status") or "PENDING"),
            risk_level=str(payload.get("risk_level") or "low"),
        )
        db.add(call)

    call.run_id = str(payload["run_id"])
    call.plan_step_id = (
        str(payload["plan_step_id"]) if payload.get("plan_step_id") else None
    )
    call.tool_name = str(payload.get("tool_name") or "")
    call.input_json = _dict_value(payload.get("input_json"))
    call.status = str(payload.get("status") or "PENDING")
    call.risk_level = str(payload.get("risk_level") or "low")
    call.governance_decision = _dict_value(payload.get("governance_decision"))
    call.error = payload.get("error")
    return call


def _upsert_tool_result(
    db: Session,
    tool_call_id: str,
    payload: dict[str, Any],
) -> AgentToolResult:
    result = db.get(AgentToolResult, tool_call_id)
    if result is None:
        result = AgentToolResult(
            tool_call_id=tool_call_id,
            status=str(payload.get("status") or "FAILED"),
            output_payload_json="{}",
            evidence_items_json="[]",
            created_proposals_json="[]",
            verification_candidates_json="[]",
        )
        db.add(result)

    result.status = str(payload.get("status") or "FAILED")
    result.output_json = _dict_value(payload.get("output_json"))
    result.evidence_items = _dict_items(payload.get("evidence_items"))
    result.created_proposals = _dict_items(payload.get("created_proposals"))
    result.verification_candidates = _dict_items(
        payload.get("verification_candidates")
    )
    result.error = payload.get("error")
    return result


def _save_created_proposals(
    db: Session,
    *,
    task: Task,
    run_id: str,
    raw_state: dict[str, Any],
) -> None:
    proposals = []
    for result in _dict_items(raw_state.get("tool_results")):
        result_evidence = _dict_items(result.get("evidence_items"))
        for proposal in _dict_items(result.get("created_proposals")):
            if not proposal.get("id"):
                continue
            evidence = _proposal_evidence_items(
                proposal=proposal,
                result_evidence=result_evidence,
                run_id=run_id,
            )
            proposals.append(
                Proposal.model_validate(
                    {
                        **proposal,
                        "run_id": str(proposal.get("run_id") or run_id),
                        "evidence": evidence,
                    }
                )
            )
    if proposals:
        persist_task_review_proposals(db, task=task, proposals=proposals)


def _proposal_evidence_items(
    *,
    proposal: dict[str, Any],
    result_evidence: list[dict[str, Any]],
    run_id: str,
) -> list[dict[str, Any]]:
    proposal_id = str(proposal["id"])
    return [
        {
            **evidence,
            "run_id": str(evidence.get("run_id") or run_id),
            "proposal_id": str(evidence.get("proposal_id") or proposal_id),
        }
        for evidence in [
            *_dict_items(proposal.get("evidence")),
            *[
                item
                for item in result_evidence
                if item.get("proposal_id") == proposal_id
            ],
        ]
    ]


def _load_tool_calls(
    db: Session,
    run: AgentRun,
    plan: AgentPlan | None,
) -> list[AgentToolCall]:
    calls = list(
        db.execute(
            select(AgentToolCall).where(AgentToolCall.run_id == run.id)
        ).scalars()
    )
    step_order = {
        step.get("step_id"): index
        for index, step in enumerate((plan.steps if plan else []))
        if step.get("step_id")
    }
    return sorted(
        calls,
        key=lambda call: (
            step_order.get(call.plan_step_id, len(step_order)),
            call.created_at,
            call.id,
        ),
    )


def _current_tool_call_payload(
    tool_calls: list[AgentToolCall],
    run_status: str,
) -> dict[str, Any] | None:
    if run_status not in {"WAITING_REVIEW", "WAITING_APPROVAL", "BLOCKED"}:
        return None
    for call in reversed(tool_calls):
        if call.result is None:
            return _tool_call_payload(call)
    return _tool_call_payload(tool_calls[-1]) if tool_calls else None


def _tool_call_payload(call: AgentToolCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "run_id": call.run_id,
        "plan_step_id": call.plan_step_id,
        "tool_name": call.tool_name,
        "input_json": call.input_json,
        "status": call.status,
        "risk_level": call.risk_level,
        "governance_decision": call.governance_decision,
        "started_at": call.started_at,
        "completed_at": call.completed_at,
        "error": call.error,
    }


def _tool_result_payload(result: AgentToolResult) -> dict[str, Any]:
    return {
        "tool_call_id": result.tool_call_id,
        "status": result.status,
        "governance_decision": result.tool_call.governance_decision,
        "output_json": result.output_json,
        "evidence_items": result.evidence_items,
        "created_proposals": result.created_proposals,
        "verification_candidates": result.verification_candidates,
        "error": result.error,
        "created_at": result.created_at,
    }


def _steps_by_id(plan_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(step["step_id"]): step
        for step in _dict_items(plan_payload.get("steps"))
        if step.get("step_id")
    }


def _plan_step_id_from_tool_call_id(
    tool_call_id: str,
    steps: dict[str, dict[str, Any]],
) -> str | None:
    for step_id in steps:
        if tool_call_id.endswith(f":{step_id}"):
            return step_id
    return None


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _interrupt_for_status(status: str) -> str | None:
    if status == "WAITING_REVIEW":
        return "review"
    if status == "WAITING_APPROVAL":
        return "approval"
    return None


__all__ = [
    "restore_governed_runtime_state",
    "save_fill_form_runtime_state",
    "save_governed_runtime_state",
]
