"""Tests for workflow constants to ensure stability and consistency."""

import pytest


def test_workflow_type_constants_exist_and_are_unique():
    """Verify workflow type constants exist and have unique stable values."""

    from app.workflow_constants import (
        WORKFLOW_TYPE_DATA_ENTRY,
        WORKFLOW_TYPE_FORM_FILL,
        WORKFLOW_TYPE_JOB_APPLICATION,
        WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
        WORKFLOW_TYPE_WEB_DATA_EXTRACT,
        WORKFLOW_TYPES,
    )

    workflow_types = {
        WORKFLOW_TYPE_FORM_FILL,
        WORKFLOW_TYPE_WEB_DATA_EXTRACT,
        WORKFLOW_TYPE_DATA_ENTRY,
        WORKFLOW_TYPE_JOB_APPLICATION,
        WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
    }

    assert WORKFLOW_TYPES == workflow_types
    assert len(workflow_types) == 5


def test_workflow_status_constants_exist_and_are_unique():
    """Verify workflow status constants are uppercase and unique."""

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

    statuses = [
        WORKFLOW_STATUS_CREATED,
        WORKFLOW_STATUS_PLANNED,
        WORKFLOW_STATUS_ANALYZING,
        WORKFLOW_STATUS_MAPPING_READY,
        WORKFLOW_STATUS_REVIEWING,
        WORKFLOW_STATUS_READY_TO_FILL,
        WORKFLOW_STATUS_FILLING,
        WORKFLOW_STATUS_VERIFYING,
        WORKFLOW_STATUS_WAITING_APPROVAL,
        WORKFLOW_STATUS_COMPLETED,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_BLOCKED,
        WORKFLOW_STATUS_LOGIN_REQUIRED,
        WORKFLOW_STATUS_LOGIN_IN_PROGRESS,
    ]

    assert len(statuses) == len(set(statuses))
    for status in statuses:
        assert status.isupper(), f"Workflow status {status} is not uppercase"


def test_span_constants_exist_and_are_unique():
    """Verify workflow span constants are present and stable."""

    from app.workflow_constants import (
        SPAN_PHASE_APPROVAL,
        SPAN_PHASE_BROWSER,
        SPAN_PHASE_EVALUATION,
        SPAN_PHASE_EXTRACTION,
        SPAN_PHASE_MAPPING,
        SPAN_PHASE_MEMORY,
        SPAN_PHASE_PLANNING,
        SPAN_PHASE_POLICY,
        SPAN_PHASE_VERIFICATION,
        SPAN_STATUS_FAILED,
        SPAN_STATUS_SKIPPED,
        SPAN_STATUS_STARTED,
        SPAN_STATUS_SUCCESS,
    )

    statuses = [
        SPAN_STATUS_STARTED,
        SPAN_STATUS_SUCCESS,
        SPAN_STATUS_FAILED,
        SPAN_STATUS_SKIPPED,
    ]
    phases = [
        SPAN_PHASE_PLANNING,
        SPAN_PHASE_POLICY,
        SPAN_PHASE_APPROVAL,
        SPAN_PHASE_BROWSER,
        SPAN_PHASE_EXTRACTION,
        SPAN_PHASE_MAPPING,
        SPAN_PHASE_VERIFICATION,
        SPAN_PHASE_EVALUATION,
        SPAN_PHASE_MEMORY,
    ]

    assert len(statuses) == len(set(statuses))
    assert len(phases) == len(set(phases))


def test_policy_and_approval_constants_exist_and_are_unique():
    """Verify policy and approval constants are present and stable."""

    from app.workflow_constants import (
        APPROVAL_STATUS_APPROVED,
        APPROVAL_STATUS_EXPIRED,
        APPROVAL_STATUS_PENDING,
        APPROVAL_STATUS_REJECTED,
        POLICY_DECISION_ALLOW,
        POLICY_DECISION_BLOCK,
        POLICY_DECISION_REVIEW_REQUIRED,
    )

    decisions = [
        POLICY_DECISION_ALLOW,
        POLICY_DECISION_REVIEW_REQUIRED,
        POLICY_DECISION_BLOCK,
    ]
    approval_statuses = [
        APPROVAL_STATUS_PENDING,
        APPROVAL_STATUS_APPROVED,
        APPROVAL_STATUS_REJECTED,
        APPROVAL_STATUS_EXPIRED,
    ]

    assert len(decisions) == len(set(decisions))
    assert len(approval_statuses) == len(set(approval_statuses))


def test_workflow_stage_constants_exist_and_uppercase():
    """Verify all workflow stage constants exist and are uppercase."""
    from app.workflow_constants import (
        WORKFLOW_STAGE_ANALYSIS,
        WORKFLOW_STAGE_MAPPING,
        WORKFLOW_STAGE_REVIEW,
        WORKFLOW_STAGE_FILL,
        WORKFLOW_STAGE_APPROVAL,
        WORKFLOW_STAGE_SUBMISSION,
    )

    stages = [
        WORKFLOW_STAGE_ANALYSIS,
        WORKFLOW_STAGE_MAPPING,
        WORKFLOW_STAGE_REVIEW,
        WORKFLOW_STAGE_FILL,
        WORKFLOW_STAGE_APPROVAL,
        WORKFLOW_STAGE_SUBMISSION,
    ]

    for stage in stages:
        assert stage.isupper(), f"Stage {stage} is not uppercase"


def test_workflow_stage_constants_are_unique():
    """Verify workflow stage constants have unique values."""
    from app.workflow_constants import (
        WORKFLOW_STAGE_ANALYSIS,
        WORKFLOW_STAGE_MAPPING,
        WORKFLOW_STAGE_REVIEW,
        WORKFLOW_STAGE_FILL,
        WORKFLOW_STAGE_APPROVAL,
        WORKFLOW_STAGE_SUBMISSION,
    )

    stages = [
        WORKFLOW_STAGE_ANALYSIS,
        WORKFLOW_STAGE_MAPPING,
        WORKFLOW_STAGE_REVIEW,
        WORKFLOW_STAGE_FILL,
        WORKFLOW_STAGE_APPROVAL,
        WORKFLOW_STAGE_SUBMISSION,
    ]

    assert len(stages) == len(set(stages)), "Workflow stage constants are not unique"


def test_checkpoint_status_constants_exist_and_uppercase():
    """Verify all checkpoint status constants exist and are uppercase."""
    from app.workflow_constants import (
        CHECKPOINT_SUCCESS,
        CHECKPOINT_FAILED,
        CHECKPOINT_SKIPPED,
    )

    statuses = [CHECKPOINT_SUCCESS, CHECKPOINT_FAILED, CHECKPOINT_SKIPPED]

    for status in statuses:
        assert status.isupper(), f"Checkpoint status {status} is not uppercase"


def test_checkpoint_status_constants_are_unique():
    """Verify checkpoint status constants have unique values."""
    from app.workflow_constants import (
        CHECKPOINT_SUCCESS,
        CHECKPOINT_FAILED,
        CHECKPOINT_SKIPPED,
    )

    statuses = [CHECKPOINT_SUCCESS, CHECKPOINT_FAILED, CHECKPOINT_SKIPPED]

    assert len(statuses) == len(set(statuses)), "Checkpoint status constants are not unique"


def test_failure_reason_constants_exist_and_uppercase():
    """Verify all failure reason constants exist and are uppercase."""
    from app.workflow_constants import (
        FAILURE_ANALYSIS_FAILED,
        FAILURE_LLM_MAPPING_FAILED,
        FAILURE_REQUIRED_FIELD_MISSING,
        FAILURE_BROWSER_FILL_FAILED,
        FAILURE_SELECTOR_NOT_FOUND,
        FAILURE_VALUE_VERIFICATION_FAILED,
        FAILURE_LOGIN_REQUIRED,
        FAILURE_SUBMISSION_REQUIRES_APPROVAL,
    )

    failures = [
        FAILURE_ANALYSIS_FAILED,
        FAILURE_LLM_MAPPING_FAILED,
        FAILURE_REQUIRED_FIELD_MISSING,
        FAILURE_BROWSER_FILL_FAILED,
        FAILURE_SELECTOR_NOT_FOUND,
        FAILURE_VALUE_VERIFICATION_FAILED,
        FAILURE_LOGIN_REQUIRED,
        FAILURE_SUBMISSION_REQUIRES_APPROVAL,
    ]

    for failure in failures:
        assert failure.isupper(), f"Failure reason {failure} is not uppercase"


def test_failure_reason_constants_are_unique():
    """Verify failure reason constants have unique values."""
    from app.workflow_constants import (
        FAILURE_ANALYSIS_FAILED,
        FAILURE_LLM_MAPPING_FAILED,
        FAILURE_REQUIRED_FIELD_MISSING,
        FAILURE_BROWSER_FILL_FAILED,
        FAILURE_SELECTOR_NOT_FOUND,
        FAILURE_VALUE_VERIFICATION_FAILED,
        FAILURE_LOGIN_REQUIRED,
        FAILURE_SUBMISSION_REQUIRES_APPROVAL,
    )

    failures = [
        FAILURE_ANALYSIS_FAILED,
        FAILURE_LLM_MAPPING_FAILED,
        FAILURE_REQUIRED_FIELD_MISSING,
        FAILURE_BROWSER_FILL_FAILED,
        FAILURE_SELECTOR_NOT_FOUND,
        FAILURE_VALUE_VERIFICATION_FAILED,
        FAILURE_LOGIN_REQUIRED,
        FAILURE_SUBMISSION_REQUIRES_APPROVAL,
    ]

    assert len(failures) == len(set(failures)), "Failure reason constants are not unique"
