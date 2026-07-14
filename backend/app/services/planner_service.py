"""Deterministic workflow plan generation and persistence helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.models import Task
from app.services.tool_registry import require_tool
from app.workflow_constants import (
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
    WORKFLOW_TYPE_VENDOR_ONBOARDING,
    WORKFLOW_TYPE_WEB_DATA_EXTRACT,
)


@dataclass(frozen=True)
class PlannedStep:
    """One deterministic planned workflow step."""

    step_id: str
    tool: str
    reason: str
    requires_approval: bool
    status: str = "PENDING"


@dataclass(frozen=True)
class WorkflowPlan:
    """A saved deterministic workflow plan."""

    workflow_type: str
    goal: str
    steps: list[PlannedStep]


def _planned_step(
    *,
    step_id: str,
    tool: str,
    reason: str,
    requires_approval: bool | None = None,
) -> PlannedStep:
    """Build one planned step while validating the referenced tool."""

    tool_definition = require_tool(tool)
    return PlannedStep(
        step_id=step_id,
        tool=tool_definition.name,
        reason=reason,
        requires_approval=(
            tool_definition.requires_approval
            if requires_approval is None
            else requires_approval
        ),
    )


def build_form_fill_plan(*, goal: str) -> WorkflowPlan:
    """Build the deterministic form-fill workflow plan."""

    steps = [
        _planned_step(
            step_id="open_url",
            tool="open_url",
            reason="Open the target page before extracting form structure.",
        ),
        _planned_step(
            step_id="extract_form",
            tool="extract_form",
            reason="Extract the form schema and candidate fields.",
        ),
        _planned_step(
            step_id="map_fields",
            tool="map_fields",
            reason="Map extracted fields to profile data or user-provided values.",
        ),
        _planned_step(
            step_id="review_mapping",
            tool="request_human_approval",
            reason="Let the user review and confirm the proposed mapping before fill.",
            requires_approval=True,
        ),
        _planned_step(
            step_id="fill_form",
            tool="fill_form",
            reason="Apply confirmed mapped values to the form.",
        ),
        _planned_step(
            step_id="verify_fields",
            tool="verify_fields",
            reason="Verify browser-side field values after fill.",
        ),
        _planned_step(
            step_id="submit_form",
            tool="submit_form",
            reason="Submit the completed form after final approval.",
        ),
    ]
    return WorkflowPlan(
        workflow_type=WORKFLOW_TYPE_FORM_FILL,
        goal=goal,
        steps=steps,
    )


def build_web_data_extract_plan(*, goal: str) -> WorkflowPlan:
    """Build the deterministic web_data_extract workflow plan."""

    steps = [
        _planned_step(
            step_id="open_url",
            tool="open_url",
            reason="Open the target page before extracting DOM structure.",
        ),
        _planned_step(
            step_id="extract_dom",
            tool="extract_dom",
            reason="Extract DOM structure, headings, text blocks, links, and tables.",
        ),
        _planned_step(
            step_id="capture_screenshot",
            tool="capture_screenshot",
            reason="Capture a screenshot for review and documentation.",
        ),
        _planned_step(
            step_id="save_result",
            tool="save_result",
            reason="Save the extraction result to persistent storage.",
        ),
    ]
    return WorkflowPlan(
        workflow_type=WORKFLOW_TYPE_WEB_DATA_EXTRACT,
        goal=goal,
        steps=steps,
    )


def build_job_research_summary_plan(*, goal: str) -> WorkflowPlan:
    """Build the deterministic job_research_summary workflow plan."""

    steps = [
        _planned_step(
            step_id="open_url",
            tool="open_url",
            reason="Open the target job page before extracting DOM structure.",
        ),
        _planned_step(
            step_id="extract_dom",
            tool="extract_dom",
            reason="Extract DOM structure, headings, text blocks, links, and tables.",
        ),
        _planned_step(
            step_id="summarize_page",
            tool="summarize_page",
            reason="Summarize page content into a structured research summary.",
        ),
        _planned_step(
            step_id="save_result",
            tool="save_result",
            reason="Save the research summary to persistent storage.",
        ),
    ]
    return WorkflowPlan(
        workflow_type=WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
        goal=goal,
        steps=steps,
    )


def build_security_questionnaire_plan(*, goal: str) -> WorkflowPlan:
    """Build the deterministic security_questionnaire workflow plan."""

    form_plan = build_form_fill_plan(goal=goal)
    return WorkflowPlan(
        workflow_type=WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
        goal=goal,
        steps=form_plan.steps,
    )


def build_vendor_onboarding_plan(*, goal: str) -> WorkflowPlan:
    """Build the deterministic vendor_onboarding workflow plan."""

    form_plan = build_form_fill_plan(goal=goal)
    return WorkflowPlan(
        workflow_type=WORKFLOW_TYPE_VENDOR_ONBOARDING,
        goal=goal,
        steps=form_plan.steps,
    )


def build_plan(*, workflow_type: str, goal: str) -> WorkflowPlan:
    """Build a deterministic saved plan for one supported workflow type."""

    if workflow_type == WORKFLOW_TYPE_FORM_FILL:
        return build_form_fill_plan(goal=goal)
    if workflow_type == WORKFLOW_TYPE_WEB_DATA_EXTRACT:
        return build_web_data_extract_plan(goal=goal)
    if workflow_type == WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY:
        return build_job_research_summary_plan(goal=goal)
    if workflow_type == WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE:
        return build_security_questionnaire_plan(goal=goal)
    if workflow_type == WORKFLOW_TYPE_VENDOR_ONBOARDING:
        return build_vendor_onboarding_plan(goal=goal)
    raise ValueError(f"Unsupported workflow type for planning: {workflow_type}")


def plan_to_dict(plan: WorkflowPlan) -> dict[str, object]:
    """Convert a workflow plan into a stable JSON-ready dictionary."""

    return {
        "workflow_type": plan.workflow_type,
        "goal": plan.goal,
        "steps": [asdict(step) for step in plan.steps],
    }


def save_plan(db: Session, task: Task, plan: WorkflowPlan) -> None:
    """Persist one workflow plan directly on the task row."""

    task.workflow_plan = plan_to_dict(plan)
    db.add(task)
    db.flush()


def resolve_plan_goal(*, description: str | None, url: str) -> str:
    """Resolve a deterministic user-facing goal string for saved plans."""

    if description and description.strip():
        return description.strip()
    return f"Complete the form workflow for {url}."
