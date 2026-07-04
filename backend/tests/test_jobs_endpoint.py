"""Tests for jobs API endpoints to ensure proper job management and cancellation."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Profile, Task, Job, WorkerHeartbeat, utc_now
from app.routers.jobs import router as jobs_router
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_CANCELLED,
)


@pytest.fixture
def test_environment():
    """Provide an isolated API client and in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db():
        yield session

    test_app = FastAPI()
    test_app.include_router(jobs_router)
    test_app.dependency_overrides[get_db] = override_get_db

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    with TestClient(test_app) as client:
        yield client, session, task.id

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_list_jobs_newest_first(test_environment):
    """Verify GET /jobs returns jobs ordered newest first."""

    client, db, task_id = test_environment

    job1 = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_PENDING,
        attempts=0,
        max_attempts=3,
    )
    db.add(job1)
    db.commit()

    job2 = Job(
        task_id=task_id,
        job_type=JOB_TYPE_MAP_FIELDS,
        status=JOB_STATUS_PENDING,
        attempts=0,
        max_attempts=3,
    )
    db.add(job2)
    db.commit()

    response = client.get("/jobs")
    assert response.status_code == 200

    jobs = response.json()
    assert len(jobs) == 2
    assert jobs[0]["id"] == job2.id
    assert jobs[1]["id"] == job1.id


def test_list_tasks_jobs(test_environment):
    """Verify GET /tasks/{task_id}/jobs returns only task-specific jobs."""

    client, db, task_id = test_environment

    job1 = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_PENDING,
        attempts=0,
        max_attempts=3,
    )
    db.add(job1)

    job2 = Job(
        task_id=None,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_PENDING,
        attempts=0,
        max_attempts=3,
    )
    db.add(job2)
    db.commit()

    response = client.get(f"/tasks/{task_id}/jobs")
    assert response.status_code == 200

    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["id"] == job1.id


def test_get_job_detail_with_attempts(test_environment):
    """Verify GET /jobs/{job_id} returns job details with attempts."""

    client, db, task_id = test_environment

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_SUCCEEDED,
        attempts=2,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    response = client.get(f"/jobs/{job.id}")
    assert response.status_code == 200

    job_data = response.json()
    assert job_data["id"] == job.id
    assert job_data["job_type"] == JOB_TYPE_ANALYZE_FORM
    assert job_data["status"] == JOB_STATUS_SUCCEEDED
    assert job_data["attempts"] == 2


def test_cancel_pending_job(test_environment):
    """Verify POST /jobs/{job_id}/cancel cancels pending jobs."""

    client, db, task_id = test_environment

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_PENDING,
        attempts=0,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    response = client.post(f"/jobs/{job.id}/cancel")
    assert response.status_code == 200

    db.refresh(job)
    assert job.status == JOB_STATUS_CANCELLED


def test_cancel_running_job_rejected(test_environment):
    """Verify POST /jobs/{job_id}/cancel rejects running jobs."""

    client, db, task_id = test_environment

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
        locked_by="worker-1",
        locked_at=utc_now(),
    )
    db.add(job)
    db.commit()

    response = client.post(f"/jobs/{job.id}/cancel")
    assert response.status_code == 409

    db.refresh(job)
    assert job.status == JOB_STATUS_RUNNING


def test_cancel_succeeded_job_rejected(test_environment):
    """Verify POST /jobs/{job_id}/cancel rejects succeeded jobs."""

    client, db, task_id = test_environment

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_SUCCEEDED,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    response = client.post(f"/jobs/{job.id}/cancel")
    assert response.status_code == 409

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED


def test_get_workers_heartbeats(test_environment):
    """Verify GET /workers/heartbeats returns worker status."""

    client, db, _ = test_environment

    heartbeat = WorkerHeartbeat(
        worker_id="worker-1",
        hostname="test-host",
        current_job_id=None,
        status="idle",
        last_seen_at=utc_now(),
    )
    db.add(heartbeat)
    db.commit()

    response = client.get("/workers/heartbeats")
    assert response.status_code == 200

    heartbeats = response.json()
    assert len(heartbeats) == 1
    assert heartbeats[0]["worker_id"] == "worker-1"
    assert heartbeats[0]["status"] == "idle"


def test_get_job_not_found(test_environment):
    """Verify GET /jobs/{job_id} returns 404 for non-existent job."""

    client, _, _ = test_environment

    response = client.get("/jobs/999")
    assert response.status_code == 404
