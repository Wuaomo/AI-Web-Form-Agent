"""Presentation model that unifies plan, trace, and execution data into agent-readable steps."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActionLog,
    ApprovalRequest,
    FieldVerificationResult,
    Screenshot,
    Task,
    TaskCheckpoint,
    WorkflowSpan,
)
from app.services.tool_registry import get_tool
from app.schemas import AgentStepResponse

SENSITIVE_PATTERNS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "otp",
    "credit",
    "card",
    "cvv",
    "ssn",
    "bank",
    "account",
}


def _redact_sensitive_content(text: str | None) -> str | None:
    """Redact sensitive values from text summaries."""

    if text is None:
        return None

    lowered = text.lower()
    for pattern in SENSITIVE_PATTERNS:
        if pattern in lowered:
            return "[REDACTED]"

    return text


def _summarize_span_input(span: WorkflowSpan) -> str | None:
    """Build a safe summary of span input data."""

    input_data = span.input
    if not input_data:
        return None

    # Check for sensitive keys first
    for key in input_data:
        if any(pattern in key.lower() for pattern in SENSITIVE_PATTERNS):
            return "[REDACTED]"

    parts: list[str] = []
    if "url" in input_data:
        parts.append(f"url={input_data['url']}")
    if "task_id" in input_data:
        parts.append(f"task_id={input_data['task_id']}")
    if "mode" in input_data:
        parts.append(f"mode={input_data['mode']}")
    if "field_count" in input_data:
        parts.append(f"field_count={input_data['field_count']}")

    return "; ".join(parts) if parts else None


def _summarize_span_output(span: WorkflowSpan) -> str | None:
    """Build a safe summary of span output data."""

    output_data = span.output
    if not output_data:
        return None

    # Check for sensitive keys first
    for key in output_data:
        if any(pattern in key.lower() for pattern in SENSITIVE_PATTERNS):
            return "[REDACTED]"

    parts: list[str] = []
    if "field_count" in output_data:
        parts.append(f"field_count={output_data['field_count']}")
    if "mapped_count" in output_data:
        parts.append(f"mapped_count={output_data['mapped_count']}")
    if "login_required" in output_data:
        parts.append(f"login_required={output_data['login_required']}")
    if "step_count" in output_data:
        parts.append(f"step_count={output_data['step_count']}")
    if "heading_count" in output_data:
        parts.append(f"heading_count={output_data['heading_count']}")
    if "link_count" in output_data:
        parts.append(f"link_count={output_data['link_count']}")
    if "cache_hit" in output_data:
        parts.append(f"cache_hit={output_data['cache_hit']}")

    return "; ".join(parts) if parts else None


def _build_evidence_list(
    span: WorkflowSpan | None,
    verifications: list[FieldVerificationResult],
    approvals: list[ApprovalRequest],
) -> list[str]:
    """Build a list of evidence types collected for this step."""

    evidence: set[str] = set()

    if span:
        if span.screenshot_id:
            evidence.add("screenshot")
        if span.output:
            evidence.add("trace_output")

    if verifications:
        evidence.add("verification_results")

    if approvals:
        evidence.add("approval_request")

    return sorted(evidence)


def _find_span_for_step(
    spans: list[WorkflowSpan],
    step_id: str,
    tool_name: str,
) -> WorkflowSpan | None:
    """Find the best-matching workflow span for a plan step."""

    # Try exact name match first
    for span in spans:
        if span.name == step_id:
            return span

    # Try tool name match
    for span in spans:
        if tool_name in span.name:
            return span

    return None


def _find_logs_for_step(
    logs: list[ActionLog],
    step_id: str,
    tool_name: str,
) -> list[ActionLog]:
    """Find action logs related to a plan step."""

    related: list[ActionLog] = []
    for log in logs:
        if step_id.replace("_", "") in log.action.replace("_", ""):
            related.append(log)
        elif tool_name.replace("_", "") in log.action.replace("_", ""):
            related.append(log)
    return related


def _build_page_intake_step(checkpoint: TaskCheckpoint) -> AgentStepResponse:
    """Build a timeline step from the persisted page intake checkpoint."""

    output = checkpoint.output
    evidence = [
        str(item.get("text"))
        for item in output.get("evidence", [])
        if isinstance(item, dict) and item.get("text")
    ]
    confidence = float(output.get("confidence") or 0)
    detected_fields = output.get("detected_fields", [])
    field_count = len(detected_fields) if isinstance(detected_fields, list) else 0
    workflow = output.get("recommended_workflow", "unknown")
    return AgentStepResponse(
        step_id="page_intake",
        tool="page_intake",
        goal="Understand page and choose workflow",
        status=checkpoint.status,
        output_summary=f"recommended={workflow}; confidence={confidence:.2f}; fields={field_count}",
        error=checkpoint.error_message,
        recovery_hint=(
            "Review the page manually and retry intake."
            if checkpoint.status == "FAILED"
            else None
        ),
        evidence=evidence,
        started_at=checkpoint.created_at,
        finished_at=checkpoint.updated_at,
    )


def build_agent_steps_for_task(db: Session, task: Task) -> list[AgentStepResponse]:
    """Return a unified timeline of workflow steps for one task.

    Aggregates plan, trace spans, action logs, verification results,
    approval requests, and screenshots into a consistent view.

    Missing trace/screenshot data does not block returning plan steps.
    Sensitive values are redacted from summaries.
    """

    plan = task.workflow_plan
    plan_steps = plan.get("steps", [])

    spans = list(
        db.scalars(
            select(WorkflowSpan)
            .where(WorkflowSpan.task_id == task.id)
            .order_by(WorkflowSpan.created_at, WorkflowSpan.id)
        )
    )

    logs = list(
        db.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step, ActionLog.created_at)
        )
    )

    verifications = list(
        db.scalars(
            select(FieldVerificationResult)
            .where(FieldVerificationResult.task_id == task.id)
            .order_by(FieldVerificationResult.created_at)
        )
    )

    approvals = list(
        db.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.task_id == task.id)
            .order_by(ApprovalRequest.created_at)
        )
    )

    page_intake_checkpoint = db.scalar(
        select(TaskCheckpoint)
        .where(
            TaskCheckpoint.task_id == task.id,
            TaskCheckpoint.stage == "PAGE_INTAKE",
        )
        .order_by(TaskCheckpoint.created_at.desc(), TaskCheckpoint.id.desc())
    )

    screenshots_by_stage: dict[str, Screenshot] = {}
    for screenshot in db.scalars(
        select(Screenshot).where(Screenshot.task_id == task.id)
    ):
        screenshots_by_stage[screenshot.stage] = screenshot

    agent_steps: list[AgentStepResponse] = []

    if page_intake_checkpoint is not None:
        agent_steps.append(_build_page_intake_step(page_intake_checkpoint))

    for plan_step in plan_steps:
        step_id = plan_step["step_id"]
        tool_name = plan_step["tool"]
        tool = get_tool(tool_name)

        span = _find_span_for_step(spans, step_id, tool_name)
        step_logs = _find_logs_for_step(logs, step_id, tool_name)

        # Determine status
        if span:
            status = span.status
        elif step_logs:
            # Use the last log status
            status = step_logs[-1].status
        else:
            status = "PENDING"

        # Build error message
        error: str | None = None
        if span and span.error_message:
            error = span.error_message
        elif step_logs:
            failed_log = next((log for log in reversed(step_logs) if log.status == "FAILED"), None)
            if failed_log and failed_log.message:
                error = failed_log.message

        # Build input/output summaries
        input_summary = _redact_sensitive_content(_summarize_span_input(span)) if span else None
        output_summary = _redact_sensitive_content(_summarize_span_output(span)) if span else None

        # Get recovery hint from tool registry
        recovery_hint = tool.recovery_hint if tool and tool.recovery_hint else None

        # Build evidence list
        evidence = _build_evidence_list(span, verifications, approvals)

        # Find screenshot
        screenshot_id: int | None = None
        if span and span.screenshot_id:
            screenshot_id = span.screenshot_id
        else:
            # Try matching by stage name
            stage_map = {
                "open_url": "page_opened",
                "extract_form": "extracted",
                "fill_form": "filled",
                "verify_fields": "verified",
                "submit_form": "submitted",
            }
            stage_name = stage_map.get(tool_name)
            if stage_name and stage_name in screenshots_by_stage:
                screenshot_id = screenshots_by_stage[stage_name].id

        # Determine timestamps
        started_at: datetime | None = None
        finished_at: datetime | None = None
        if span:
            started_at = span.created_at
            finished_at = span.created_at  # WorkflowSpan doesn't have separate finished_at

        agent_steps.append(
            AgentStepResponse(
                step_id=step_id,
                tool=tool_name,
                goal=plan_step.get("reason", ""),
                status=status,
                input_summary=input_summary,
                output_summary=output_summary,
                error=error,
                recovery_hint=recovery_hint,
                evidence=evidence,
                screenshot_id=screenshot_id,
                started_at=started_at,
                finished_at=finished_at,
            )
        )

    return agent_steps
