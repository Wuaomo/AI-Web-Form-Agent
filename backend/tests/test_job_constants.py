"""Tests for job constants to ensure stability and consistency."""

import pytest


def test_job_type_constants_exist_and_uppercase():
    """Verify all job type constants exist and are uppercase."""
    from app.job_constants import (
        JOB_TYPE_ANALYZE_FORM,
        JOB_TYPE_MAP_FIELDS,
        JOB_TYPE_FILL_FORM,
        JOB_TYPE_RUN_BENCHMARK,
    )

    job_types = [
        JOB_TYPE_ANALYZE_FORM,
        JOB_TYPE_MAP_FIELDS,
        JOB_TYPE_FILL_FORM,
        JOB_TYPE_RUN_BENCHMARK,
    ]

    for job_type in job_types:
        assert job_type.isupper(), f"Job type {job_type} is not uppercase"


def test_job_type_constants_are_unique():
    """Verify job type constants have unique values."""
    from app.job_constants import (
        JOB_TYPE_ANALYZE_FORM,
        JOB_TYPE_MAP_FIELDS,
        JOB_TYPE_FILL_FORM,
        JOB_TYPE_RUN_BENCHMARK,
    )

    job_types = [
        JOB_TYPE_ANALYZE_FORM,
        JOB_TYPE_MAP_FIELDS,
        JOB_TYPE_FILL_FORM,
        JOB_TYPE_RUN_BENCHMARK,
    ]

    assert len(job_types) == len(set(job_types)), "Job type constants are not unique"


def test_job_status_constants_exist_and_uppercase():
    """Verify all job status constants exist and are uppercase."""
    from app.job_constants import (
        JOB_STATUS_PENDING,
        JOB_STATUS_RUNNING,
        JOB_STATUS_SUCCEEDED,
        JOB_STATUS_FAILED,
        JOB_STATUS_CANCELLED,
        JOB_STATUS_RETRY_SCHEDULED,
    )

    statuses = [
        JOB_STATUS_PENDING,
        JOB_STATUS_RUNNING,
        JOB_STATUS_SUCCEEDED,
        JOB_STATUS_FAILED,
        JOB_STATUS_CANCELLED,
        JOB_STATUS_RETRY_SCHEDULED,
    ]

    for status in statuses:
        assert status.isupper(), f"Job status {status} is not uppercase"


def test_job_status_constants_are_unique():
    """Verify job status constants have unique values."""
    from app.job_constants import (
        JOB_STATUS_PENDING,
        JOB_STATUS_RUNNING,
        JOB_STATUS_SUCCEEDED,
        JOB_STATUS_FAILED,
        JOB_STATUS_CANCELLED,
        JOB_STATUS_RETRY_SCHEDULED,
    )

    statuses = [
        JOB_STATUS_PENDING,
        JOB_STATUS_RUNNING,
        JOB_STATUS_SUCCEEDED,
        JOB_STATUS_FAILED,
        JOB_STATUS_CANCELLED,
        JOB_STATUS_RETRY_SCHEDULED,
    ]

    assert len(statuses) == len(set(statuses)), "Job status constants are not unique"
