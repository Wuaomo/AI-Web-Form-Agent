"""Tests for workflow constants to ensure stability and consistency."""

import pytest


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