"""Tests for job queue service to ensure deterministic job management behavior."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Profile, Task, utc_now
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
    JOB_STATUS_RETRY_SCHEDULED,
)


@pytest.fixture
def db_session(tmp_path):
    """Create a temporary database session for tests."""

    db_path = tmp_path / "job_queue_test.db"
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


def test_enqueue_job_creates_pending_job(db_session):
    """Verify enqueue_job creates a PENDING job with correct attributes."""

    from app.services.job_queue import enqueue_job

    db, task_id = db_session

    job = enqueue_job(
        db=db,
        job_type=JOB_TYPE_ANALYZE_FORM,
        task_id=task_id,
        payload={"url": "https://example.com/form"},
        priority=100,
        max_attempts=3,
    )

    db.commit()

    assert job is not None
    assert job.task_id == task_id
    assert job.job_type == JOB_TYPE_ANALYZE_FORM
    assert job.status == JOB_STATUS_PENDING
    assert job.priority == 100
    assert job.payload == {"url": "https://example.com/form"}
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.locked_by is None
    assert job.locked_at is None
    assert job.next_run_at is None


def test_claim_next_job_locks_oldest_pending_job(db_session):
    """Verify claim_next_job locks the oldest pending job and increments attempts."""

    from app.services.job_queue import enqueue_job, claim_next_job

    db, task_id = db_session

    job1 = enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, priority=100)
    job2 = enqueue_job(db=db, job_type=JOB_TYPE_MAP_FIELDS, task_id=task_id, priority=100)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")

    db.commit()

    assert claimed is not None
    assert claimed.id == job1.id
    assert claimed.status == JOB_STATUS_RUNNING
    assert claimed.locked_by == "worker-1"
    assert claimed.locked_at is not None
    assert claimed.attempts == 1


def test_claim_next_job_respects_allowed_job_types(db_session):
    """Verify claim_next_job only claims jobs of allowed types."""

    from app.services.job_queue import enqueue_job, claim_next_job

    db, task_id = db_session

    enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, priority=100)
    enqueue_job(db=db, job_type=JOB_TYPE_MAP_FIELDS, task_id=task_id, priority=100)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1", allowed_job_types={JOB_TYPE_MAP_FIELDS})

    db.commit()

    assert claimed is not None
    assert claimed.job_type == JOB_TYPE_MAP_FIELDS


def test_locked_jobs_not_claimed_by_another_worker(db_session):
    """Verify locked jobs are not claimed by another worker."""

    from app.services.job_queue import enqueue_job, claim_next_job

    db, task_id = db_session

    enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, priority=100)
    db.commit()

    claim_next_job(db=db, worker_id="worker-1")
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-2")

    assert claimed is None


def test_mark_job_succeeded_updates_status(db_session):
    """Verify mark_job_succeeded updates job status to SUCCEEDED."""

    from app.services.job_queue import enqueue_job, claim_next_job, mark_job_succeeded

    db, task_id = db_session

    job = enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")
    db.commit()

    mark_job_succeeded(db=db, job=claimed)
    db.commit()

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED


def test_mark_job_failed_with_retry_schedules_retry(db_session):
    """Verify mark_job_failed with retry=True schedules a retry."""

    from app.services.job_queue import enqueue_job, claim_next_job, mark_job_failed

    db, task_id = db_session

    job = enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, max_attempts=3)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")
    db.commit()

    mark_job_failed(db=db, job=claimed, error_reason="TEST_ERROR", error_message="test failure", retry=True)
    db.commit()

    db.refresh(job)
    assert job.status == JOB_STATUS_RETRY_SCHEDULED
    assert job.attempts == 1
    assert job.error_reason == "TEST_ERROR"
    assert job.error_message == "test failure"
    assert job.next_run_at is not None
    assert job.locked_by is None
    assert job.locked_at is None


def test_mark_job_failed_retry_exhausts_after_max_attempts(db_session):
    """Verify mark_job_failed marks job as FAILED after max attempts."""

    from app.services.job_queue import enqueue_job, claim_next_job, mark_job_failed
    from sqlalchemy import update

    db, task_id = db_session

    job = enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, max_attempts=2)
    job_id = job.id
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")
    assert claimed is not None
    db.commit()

    mark_job_failed(db=db, job=claimed, error_reason="TEST_ERROR", error_message="test failure", retry=True)
    db.commit()

    from app.models import Job
    db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(next_run_at=utc_now() - timedelta(seconds=1))
    )
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")
    assert claimed is not None
    db.commit()

    mark_job_failed(db=db, job=claimed, error_reason="TEST_ERROR", error_message="test failure", retry=True)
    db.commit()

    db.refresh(job)
    assert job.status == JOB_STATUS_FAILED
    assert job.attempts == 2
    assert job.next_run_at is None


def test_mark_job_failed_without_retry_immediate_failure(db_session):
    """Verify mark_job_failed with retry=False marks job as FAILED immediately."""

    from app.services.job_queue import enqueue_job, claim_next_job, mark_job_failed

    db, task_id = db_session

    job = enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, max_attempts=3)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")
    db.commit()

    mark_job_failed(db=db, job=claimed, error_reason="TEST_ERROR", error_message="test failure", retry=False)
    db.commit()

    db.refresh(job)
    assert job.status == JOB_STATUS_FAILED
    assert job.attempts == 1
    assert job.next_run_at is None


def test_record_worker_heartbeat_creates_new(db_session):
    """Verify record_worker_heartbeat creates a new heartbeat record."""

    from app.services.job_queue import record_worker_heartbeat

    db, _ = db_session

    heartbeat = record_worker_heartbeat(db=db, worker_id="worker-1", current_job_id=None, status="running")

    db.commit()

    assert heartbeat is not None
    assert heartbeat.worker_id == "worker-1"
    assert heartbeat.current_job_id is None
    assert heartbeat.status == "running"
    assert heartbeat.last_seen_at is not None


def test_record_worker_heartbeat_updates_existing(db_session):
    """Verify record_worker_heartbeat updates an existing heartbeat."""

    from app.services.job_queue import record_worker_heartbeat

    db, _ = db_session

    heartbeat = record_worker_heartbeat(db=db, worker_id="worker-1", current_job_id=None, status="running")
    db.commit()

    original_id = heartbeat.id

    updated = record_worker_heartbeat(db=db, worker_id="worker-1", current_job_id=123, status="busy")
    db.commit()

    assert updated.id == original_id
    assert updated.current_job_id == 123
    assert updated.status == "busy"


def test_claim_next_job_skips_retry_scheduled_until_time(db_session):
    """Verify claim_next_job skips jobs with next_run_at in the future."""

    from app.services.job_queue import enqueue_job, claim_next_job, mark_job_failed

    db, task_id = db_session

    job = enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id, max_attempts=3)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-1")
    db.commit()

    mark_job_failed(db=db, job=claimed, error_reason="TEST_ERROR", error_message="test failure", retry=True)
    db.commit()

    job.next_run_at = utc_now() + timedelta(hours=1)
    db.commit()

    claimed = claim_next_job(db=db, worker_id="worker-2")

    assert claimed is None
