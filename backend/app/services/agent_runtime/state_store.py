"""SQLite persistence helpers for the governed runtime migration slice."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentPlan, AgentRun, Task
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

    db.commit()
    db.refresh(run)
    return run


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
        "current_tool_call": None,
        "governance_decision": None,
        "tool_results": [],
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


def _interrupt_for_status(status: str) -> str | None:
    if status == "WAITING_REVIEW":
        return "review"
    if status == "WAITING_APPROVAL":
        return "approval"
    return None


__all__ = [
    "restore_governed_runtime_state",
    "save_governed_runtime_state",
]
