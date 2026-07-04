"""Tests for metrics event emission at workflow boundaries."""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Profile, Task, Job
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
    JOB_STATUS_RETRY_SCHEDULED,
)
from app.workflow_constants import (
    CHECKPOINT_SUCCESS,
    WORKFLOW_STAGE_ANALYSIS,
)


@pytest.fixture
def db_session(tmp_path):
    """Create a temporary database session for tests."""

    db_path = tmp_path / "metrics_events_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    yield session, task.id

    session.close()


def test_successful_job_emits_started_and_succeeded_events(db_session):
    """Verify execute_job emits job_started and job_succeeded events."""

    from app.services.job_worker import execute_job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
        locked_by="worker-test-1",
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze, \
         patch("app.services.job_worker.emit_metrics_event") as mock_emit:
        mock_analyze.return_value = None
        execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED

    event_types = [call.args[0]["event_type"] for call in mock_emit.call_args_list]
    assert "job_started" in event_types
    assert "job_succeeded" in event_types

    started_event = next(
        call.args[0] for call in mock_emit.call_args_list
        if call.args[0]["event_type"] == "job_started"
    )
    assert started_event["task_id"] == task_id
    assert started_event["job_id"] == job.id
    assert started_event["job_type"] == JOB_TYPE_ANALYZE_FORM
    assert started_event["worker_id"] == "worker-test-1"

    succeeded_event = next(
        call.args[0] for call in mock_emit.call_args_list
        if call.args[0]["event_type"] == "job_succeeded"
    )
    assert succeeded_event["task_id"] == task_id
    assert succeeded_event["job_id"] == job.id
    assert succeeded_event["job_type"] == JOB_TYPE_ANALYZE_FORM
    assert "duration_ms" in succeeded_event


def test_failed_job_emits_failed_event(db_session):
    """Verify execute_job emits job_failed event for non-retryable failures."""

    from app.services.job_worker import execute_job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
        locked_by="worker-test-1",
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze, \
         patch("app.services.job_worker.emit_metrics_event") as mock_emit:
        mock_analyze.side_effect = ValueError("permanent failure")
        execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_FAILED

    event_types = [call.args[0]["event_type"] for call in mock_emit.call_args_list]
    assert "job_started" in event_types
    assert "job_failed" in event_types

    failed_event = next(
        call.args[0] for call in mock_emit.call_args_list
        if call.args[0]["event_type"] == "job_failed"
    )
    assert failed_event["task_id"] == task_id
    assert failed_event["job_id"] == job.id
    assert failed_event["job_type"] == JOB_TYPE_ANALYZE_FORM
    assert "duration_ms" in failed_event


def test_retryable_job_emits_retry_scheduled_event(db_session):
    """Verify execute_job emits job_retry_scheduled event for retryable failures."""

    from app.services.job_worker import execute_job, RetryableError

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
        locked_by="worker-test-1",
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze, \
         patch("app.services.job_worker.emit_metrics_event") as mock_emit:
        mock_analyze.side_effect = RetryableError("temporary failure")
        execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_RETRY_SCHEDULED

    event_types = [call.args[0]["event_type"] for call in mock_emit.call_args_list]
    assert "job_retry_scheduled" in event_types


def test_checkpoint_write_emits_checkpoint_event(db_session):
    """Verify write_checkpoint emits checkpoint_written event."""

    from app.services.checkpoint_service import write_checkpoint

    db, task_id = db_session

    with patch("app.services.checkpoint_service.emit_metrics_event") as mock_emit:
        write_checkpoint(
            task_id=task_id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_SUCCESS,
            input_hash="test-hash",
            output={"field_count": 5},
            db=db,
        )

    mock_emit.assert_called_once()
    event = mock_emit.call_args.args[0]
    assert event["event_type"] == "checkpoint_written"
    assert event["task_id"] == task_id
    assert event["job_type"] == WORKFLOW_STAGE_ANALYSIS


def test_enqueue_job_emits_enqueued_event(db_session):
    """Verify enqueue_job emits job_enqueued event."""

    from app.services.job_queue import enqueue_job

    db, task_id = db_session

    with patch("app.services.job_queue.emit_metrics_event") as mock_emit:
        job = enqueue_job(
            db=db,
            job_type=JOB_TYPE_MAP_FIELDS,
            task_id=task_id,
            payload={"mode": "rules"},
        )

    mock_emit.assert_called_once()
    event = mock_emit.call_args.args[0]
    assert event["event_type"] == "job_enqueued"
    assert event["task_id"] == task_id
    assert event["job_id"] == job.id
    assert event["job_type"] == JOB_TYPE_MAP_FIELDS


def test_sidecar_failure_does_not_fail_job(db_session):
    """Verify sidecar failure does not propagate to job execution."""

    from app.services.job_worker import execute_job
    import requests

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
        locked_by="worker-test-1",
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze, \
         patch("app.services.metrics_sidecar_client.requests.post", side_effect=requests.exceptions.RequestException("sidecar down")), \
         patch("os.getenv", return_value="http://localhost:9100"):
        mock_analyze.return_value = None
        execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED


def test_events_include_task_and_job_ids(db_session):
    """Verify events include task_id and job_id when available."""

    from app.services.job_worker import execute_job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_MAP_FIELDS,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
        locked_by="worker-test-1",
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_map_stage") as mock_map, \
         patch("app.services.job_worker.emit_metrics_event") as mock_emit:
        mock_map.return_value = None
        execute_job(db=db, job=job)

    for call in mock_emit.call_args_list:
        event = call.args[0]
        assert event["task_id"] == task_id
        assert event["job_id"] == job.id
        assert event["job_type"] == JOB_TYPE_MAP_FIELDS
