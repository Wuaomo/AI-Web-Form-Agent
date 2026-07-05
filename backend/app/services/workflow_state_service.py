"""Helpers for validating and applying workflow state transitions."""

from app.models import Task
from app.workflow_constants import (
    WORKFLOW_STATUS_ANALYZING,
    WORKFLOW_STATUS_BLOCKED,
    WORKFLOW_STATUS_COMPLETED,
    WORKFLOW_STATUS_CREATED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_FILLING,
    WORKFLOW_STATUS_LOGIN_IN_PROGRESS,
    WORKFLOW_STATUS_LOGIN_REQUIRED,
    WORKFLOW_STATUS_MAPPING_READY,
    WORKFLOW_STATUS_PLANNED,
    WORKFLOW_STATUS_READY_TO_FILL,
    WORKFLOW_STATUS_REVIEWING,
    WORKFLOW_STATUS_VERIFYING,
    WORKFLOW_STATUS_WAITING_APPROVAL,
)


class InvalidWorkflowTransition(ValueError):
    """Raised when a workflow status change is not allowed."""


ALLOWED_TRANSITIONS = {
    WORKFLOW_STATUS_CREATED: {
        WORKFLOW_STATUS_PLANNED,
        WORKFLOW_STATUS_ANALYZING,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_PLANNED: {
        WORKFLOW_STATUS_ANALYZING,
        WORKFLOW_STATUS_BLOCKED,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_ANALYZING: {
        WORKFLOW_STATUS_MAPPING_READY,
        WORKFLOW_STATUS_LOGIN_REQUIRED,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_LOGIN_REQUIRED: {
        WORKFLOW_STATUS_LOGIN_IN_PROGRESS,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_LOGIN_IN_PROGRESS: {
        WORKFLOW_STATUS_ANALYZING,
        WORKFLOW_STATUS_LOGIN_REQUIRED,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_MAPPING_READY: {
        WORKFLOW_STATUS_REVIEWING,
        WORKFLOW_STATUS_READY_TO_FILL,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_REVIEWING: {
        WORKFLOW_STATUS_READY_TO_FILL,
        WORKFLOW_STATUS_MAPPING_READY,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_BLOCKED,
    },
    WORKFLOW_STATUS_READY_TO_FILL: {
        WORKFLOW_STATUS_FILLING,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_BLOCKED,
    },
    WORKFLOW_STATUS_FILLING: {
        WORKFLOW_STATUS_VERIFYING,
        WORKFLOW_STATUS_WAITING_APPROVAL,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_VERIFYING: {
        WORKFLOW_STATUS_WAITING_APPROVAL,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_BLOCKED,
    },
    WORKFLOW_STATUS_WAITING_APPROVAL: {
        WORKFLOW_STATUS_COMPLETED,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_BLOCKED,
    },
    WORKFLOW_STATUS_COMPLETED: set(),
    WORKFLOW_STATUS_FAILED: {
        WORKFLOW_STATUS_ANALYZING,
        WORKFLOW_STATUS_MAPPING_READY,
    },
    WORKFLOW_STATUS_BLOCKED: {
        WORKFLOW_STATUS_REVIEWING,
        WORKFLOW_STATUS_FAILED,
    },
}


def _current_status(task: Task) -> str:
    """Return the best current status for transition validation."""

    if task.status and task.workflow_status and task.status != task.workflow_status:
        return task.status
    return task.workflow_status or task.status or WORKFLOW_STATUS_CREATED


def can_transition(current_status: str, next_status: str) -> bool:
    """Return whether a workflow status change is allowed."""

    if current_status == next_status:
        return True
    return next_status in ALLOWED_TRANSITIONS.get(current_status, set())


def sync_legacy_status(task: Task) -> None:
    """Mirror workflow_status into the legacy task status field."""

    task.status = task.workflow_status or task.status or WORKFLOW_STATUS_CREATED


def set_workflow_status(task: Task, next_status: str, *, reason: str | None = None) -> None:
    """Validate and apply the next workflow status to a task."""

    current_status = _current_status(task)
    if not can_transition(current_status, next_status):
        detail = f"Invalid workflow transition: {current_status} -> {next_status}"
        if reason:
            detail = f"{detail} ({reason})"
        raise InvalidWorkflowTransition(detail)

    task.workflow_status = next_status
    sync_legacy_status(task)
