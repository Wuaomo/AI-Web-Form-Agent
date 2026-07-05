"""Tests for workflow state transition helpers."""

import pytest

from app.models import Task
from app.services.workflow_state_service import (
    InvalidWorkflowTransition,
    can_transition,
    set_workflow_status,
    sync_legacy_status,
)
from app.workflow_constants import (
    WORKFLOW_STATUS_ANALYZING,
    WORKFLOW_STATUS_COMPLETED,
    WORKFLOW_STATUS_CREATED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_MAPPING_READY,
)


def test_can_transition_allows_created_to_analyzing() -> None:
    """Verify a documented happy-path transition is allowed."""

    assert can_transition(WORKFLOW_STATUS_CREATED, WORKFLOW_STATUS_ANALYZING) is True


def test_can_transition_rejects_created_to_completed() -> None:
    """Verify a documented invalid transition is rejected."""

    assert can_transition(WORKFLOW_STATUS_CREATED, WORKFLOW_STATUS_COMPLETED) is False


def test_set_workflow_status_updates_workflow_and_legacy_status() -> None:
    """Verify workflow status writes stay synchronized with legacy status."""

    task = Task(
        url="https://example.com/form",
        profile_id=1,
        status=WORKFLOW_STATUS_CREATED,
        workflow_status=WORKFLOW_STATUS_CREATED,
    )

    set_workflow_status(task, WORKFLOW_STATUS_ANALYZING, reason="unit_test")

    assert task.workflow_status == WORKFLOW_STATUS_ANALYZING
    assert task.status == WORKFLOW_STATUS_ANALYZING


def test_set_workflow_status_uses_legacy_status_when_workflow_status_missing() -> None:
    """Verify legacy rows can still transition before workflow_status is hydrated."""

    task = Task(
        url="https://example.com/form",
        profile_id=1,
        status=WORKFLOW_STATUS_FAILED,
        workflow_status="",
    )

    set_workflow_status(task, WORKFLOW_STATUS_MAPPING_READY, reason="legacy_retry")

    assert task.workflow_status == WORKFLOW_STATUS_MAPPING_READY
    assert task.status == WORKFLOW_STATUS_MAPPING_READY


def test_invalid_transition_raises_error() -> None:
    """Verify invalid transitions fail loudly."""

    task = Task(
        url="https://example.com/form",
        profile_id=1,
        status=WORKFLOW_STATUS_CREATED,
        workflow_status=WORKFLOW_STATUS_CREATED,
    )

    with pytest.raises(InvalidWorkflowTransition):
        set_workflow_status(task, WORKFLOW_STATUS_COMPLETED, reason="skip_ahead")


def test_sync_legacy_status_copies_workflow_status() -> None:
    """Verify explicit synchronization updates the legacy field."""

    task = Task(
        url="https://example.com/form",
        profile_id=1,
        status=WORKFLOW_STATUS_CREATED,
        workflow_status=WORKFLOW_STATUS_MAPPING_READY,
    )

    sync_legacy_status(task)

    assert task.status == WORKFLOW_STATUS_MAPPING_READY
