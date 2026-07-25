"""Deterministic reliability detection for browser workflow execution.

Detects repeating failures, stalled progress, verification mismatches, and
other reliability signals without automatic recovery. Instead, outputs
structured signals that workflows can use to enter review/block states.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionLog, ApprovalRequest, Task, WorkflowSpan
from app.workflow_constants import (
    SPAN_STATUS_FAILED,
    WORKFLOW_STATUS_BLOCKED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_REVIEWING,
    WORKFLOW_STATUS_WAITING_APPROVAL,
)

MAX_REPEAT_FAILURES = 3
MAX_STALL_DURATION = timedelta(minutes=5)
MAX_SAME_ACTION_REPEATS = 5


@dataclass(frozen=True)
class ReliabilitySignal:
    """Structured reliability signal for workflow decision making."""

    signal_type: str
    failure_reason: str
    recovery_hint: str
    recommended_next_state: str
    evidence: dict[str, object]


def _count_recent_failures_for_selector(
    db: Session,
    task_id: int,
    selector: str,
    window: timedelta = timedelta(minutes=10),
) -> int:
    """Count recent failures mentioning a specific selector."""

    cutoff = datetime.now(timezone.utc) - window
    statement = (
        select(ActionLog)
        .where(ActionLog.task_id == task_id)
        .where(ActionLog.status == "FAILED")
        .where(ActionLog.created_at >= cutoff)
    )
    # Filter by selector in message since ActionLog doesn't have a selector field
    logs = list(db.scalars(statement))
    return sum(1 for log in logs if selector in (log.message or ""))


def _count_recent_action_repeats(
    db: Session,
    task_id: int,
    action: str,
    window: timedelta = timedelta(minutes=10),
) -> int:
    """Count recent repeats of the same action."""

    cutoff = datetime.now(timezone.utc) - window
    statement = (
        select(ActionLog)
        .where(ActionLog.task_id == task_id)
        .where(ActionLog.action == action)
        .where(ActionLog.created_at >= cutoff)
    )
    return len(list(db.scalars(statement)))


def _check_for_stalled_progress(
    db: Session,
    task_id: int,
) -> Optional[ReliabilitySignal]:
    """Detect when workflow has made no progress recently."""

    statement = (
        select(WorkflowSpan)
        .where(WorkflowSpan.task_id == task_id)
        .order_by(WorkflowSpan.created_at.desc())
        .limit(1)
    )
    latest_span = db.scalar(statement)

    if latest_span is None:
        return None

    time_since_last_activity = datetime.now(timezone.utc) - latest_span.created_at
    if time_since_last_activity > MAX_STALL_DURATION:
        return ReliabilitySignal(
            signal_type="PROGRESS_STALLED",
            failure_reason="Workflow has made no progress in over 5 minutes",
            recovery_hint="Check if the browser is still running, or restart the workflow",
            recommended_next_state=WORKFLOW_STATUS_BLOCKED,
            evidence={
                "last_activity_at": latest_span.created_at.isoformat(),
                "latest_span_name": latest_span.name,
                "latest_span_status": latest_span.status,
            },
        )

    return None


def _check_for_repeated_selector_failures(
    db: Session,
    task_id: int,
    selector: str,
) -> Optional[ReliabilitySignal]:
    """Detect repeated failures on the same selector."""

    failure_count = _count_recent_failures_for_selector(db, task_id, selector)
    if failure_count >= MAX_REPEAT_FAILURES:
        return ReliabilitySignal(
            signal_type="REPEATED_SELECTOR_FAILURE",
            failure_reason=f"Selector '{selector}' has failed {failure_count} times recently",
            recovery_hint="Verify the selector is still valid on the page, or update the field mapping",
            recommended_next_state=WORKFLOW_STATUS_REVIEWING,
            evidence={
                "selector": selector,
                "failure_count": failure_count,
            },
        )

    return None


def _check_for_repeated_action_without_progress(
    db: Session,
    task_id: int,
    action: str,
) -> Optional[ReliabilitySignal]:
    """Detect when the same action repeats without meaningful progress."""

    repeat_count = _count_recent_action_repeats(db, task_id, action)
    if repeat_count >= MAX_SAME_ACTION_REPEATS:
        return ReliabilitySignal(
            signal_type="REPEATED_ACTION_NO_PROGRESS",
            failure_reason=f"Action '{action}' has repeated {repeat_count} times without progress",
            recovery_hint="The workflow may be stuck in a loop; review the plan or adjust the action parameters",
            recommended_next_state=WORKFLOW_STATUS_BLOCKED,
            evidence={
                "action": action,
                "repeat_count": repeat_count,
            },
        )

    return None


def _check_for_playwright_timeout(
    error_message: str,
) -> Optional[ReliabilitySignal]:
    """Detect Playwright timeout errors."""

    timeout_keywords = {"timeout", "TimeoutError", "waiting for"}
    if any(keyword in error_message.lower() for keyword in timeout_keywords):
        return ReliabilitySignal(
            signal_type="PLAYWRIGHT_TIMEOUT",
            failure_reason=f"Playwright timeout occurred: {error_message}",
            recovery_hint="Increase timeout settings, ensure the element is visible, or add explicit waits",
            recommended_next_state=WORKFLOW_STATUS_REVIEWING,
            evidence={
                "error_message": error_message,
            },
        )

    return None


def _check_for_verification_mismatch(
    task_id: int,
    verification_results: list[dict],
) -> Optional[ReliabilitySignal]:
    """Detect verification mismatches after fill."""

    failed_count = sum(1 for r in verification_results if r["status"] == "FAILED")
    if failed_count > 0:
        failed_selectors = [r["selector"] for r in verification_results if r["status"] == "FAILED"]
        return ReliabilitySignal(
            signal_type="VERIFICATION_MISMATCH",
            failure_reason=f"{failed_count} field(s) failed verification after fill",
            recovery_hint="Review the failed fields and correct the mappings before retrying",
            recommended_next_state=WORKFLOW_STATUS_REVIEWING,
            evidence={
                "failed_count": failed_count,
                "failed_selectors": failed_selectors,
            },
        )

    return None


def _check_for_missing_approval(
    db: Session,
    task_id: int,
    step_name: str,
) -> Optional[ReliabilitySignal]:
    """Detect when a required approval gate is missing."""

    approval_required_steps = {"submit_form", "fill_form", "memory_write"}

    if step_name not in approval_required_steps:
        return None

    statement = (
        select(ApprovalRequest)
        .where(ApprovalRequest.task_id == task_id)
        .where(ApprovalRequest.step_name == step_name)
        .where(ApprovalRequest.status == "APPROVED")
    )
    approved = db.scalar(statement)

    if approved is None:
        return ReliabilitySignal(
            signal_type="MISSING_APPROVAL",
            failure_reason=f"Approval required for '{step_name}' but not yet granted",
            recovery_hint="Request and obtain approval before proceeding with this action",
            recommended_next_state=WORKFLOW_STATUS_WAITING_APPROVAL,
            evidence={
                "step_name": step_name,
            },
        )

    return None


def _check_for_url_stagnation(
    db: Session,
    task_id: int,
    expected_url: str,
) -> Optional[ReliabilitySignal]:
    """Detect when the page URL hasn't changed as expected."""

    statement = (
        select(ActionLog)
        .where(ActionLog.task_id == task_id)
        .where(ActionLog.action == "goto")
        .order_by(ActionLog.created_at.desc())
        .limit(3)
    )
    recent_gotos = list(db.scalars(statement))

    if len(recent_gotos) >= 2:
        # Check if the same URL was navigated to repeatedly (from message)
        urls = set()
        for log in recent_gotos:
            if log.message and expected_url in log.message:
                urls.add(expected_url)
            elif log.message:
                # Extract URL from message if possible
                urls.add(log.message)
        if len(urls) == 1 and expected_url in urls:
            return ReliabilitySignal(
                signal_type="URL_STAGNATION",
                failure_reason=f"URL has not changed from '{expected_url}' after multiple navigation attempts",
                recovery_hint="Verify the URL is correct and the page is loading properly",
                recommended_next_state=WORKFLOW_STATUS_REVIEWING,
                evidence={
                    "current_url": expected_url,
                    "navigation_attempts": len(recent_gotos),
                },
            )

    return None


def detect_reliability_signals(
    db: Session,
    task_id: int,
    *,
    selector: str | None = None,
    action: str | None = None,
    error_message: str | None = None,
    verification_results: list[dict] | None = None,
    step_name: str | None = None,
    expected_url: str | None = None,
) -> list[ReliabilitySignal]:
    """Run all reliability checks and return detected signals.

    Signals are deterministic and do not include any AI-driven recovery.
    Instead, they provide structured information for workflows to decide
    whether to enter review, block, or fail states.
    """

    signals: list[ReliabilitySignal] = []

    # Check for stalled progress (no recent activity)
    signal = _check_for_stalled_progress(db, task_id)
    if signal:
        signals.append(signal)

    # Check for repeated selector failures
    if selector:
        signal = _check_for_repeated_selector_failures(db, task_id, selector)
        if signal:
            signals.append(signal)

    # Check for repeated actions without progress
    if action:
        signal = _check_for_repeated_action_without_progress(db, task_id, action)
        if signal:
            signals.append(signal)

    # Check for Playwright timeout
    if error_message:
        signal = _check_for_playwright_timeout(error_message)
        if signal:
            signals.append(signal)

    # Check for verification mismatches
    if verification_results:
        signal = _check_for_verification_mismatch(task_id, verification_results)
        if signal:
            signals.append(signal)

    # Check for missing approval
    if step_name:
        signal = _check_for_missing_approval(db, task_id, step_name)
        if signal:
            signals.append(signal)

    # Check for URL stagnation
    if expected_url:
        signal = _check_for_url_stagnation(db, task_id, expected_url)
        if signal:
            signals.append(signal)

    return signals


def should_block_or_review(
    db: Session,
    task_id: int,
    *,
    selector: str | None = None,
    action: str | None = None,
    error_message: str | None = None,
    verification_results: list[dict] | None = None,
    step_name: str | None = None,
) -> tuple[bool, str, str]:
    """Quick check to determine if workflow should enter a review/block state.

    Returns: (should_stop, recommended_state, reason)
    """

    signals = detect_reliability_signals(
        db,
        task_id,
        selector=selector,
        action=action,
        error_message=error_message,
        verification_results=verification_results,
        step_name=step_name,
    )

    if not signals:
        return False, "", ""

    # Prioritize the most severe signal
    severity_order = [
        "REPEATED_SELECTOR_FAILURE",
        "REPEATED_ACTION_NO_PROGRESS",
        "PROGRESS_STALLED",
        "VERIFICATION_MISMATCH",
        "PLAYWRIGHT_TIMEOUT",
        "MISSING_APPROVAL",
        "URL_STAGNATION",
    ]

    for signal_type in severity_order:
        signal = next((s for s in signals if s.signal_type == signal_type), None)
        if signal:
            return True, signal.recommended_next_state, signal.failure_reason

    # Fallback to the first signal
    first_signal = signals[0]
    return True, first_signal.recommended_next_state, first_signal.failure_reason
