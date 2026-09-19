"""Tests for async job enqueueing from task routes when ASYNC_JOBS_ENABLED."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import config
from app.models import FormField, Job, Profile, Task
from app.routers.tasks import router as tasks_router
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_TYPE_FILL_FORM,
    JOB_STATUS_PENDING,
)


@pytest.fixture
def async_env():
    """Provide an API client with ASYNC_JOBS_ENABLED turned on."""

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
    test_app.include_router(tasks_router)
    test_app.dependency_overrides[get_db] = override_get_db

    profile = Profile(
        profile_name="Async Profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="CREATED",
    )
    session.add(task)
    session.commit()

    original_flag = config.ASYNC_JOBS_ENABLED
    config.ASYNC_JOBS_ENABLED = True

    with TestClient(test_app) as client:
        yield client, session, task

    config.ASYNC_JOBS_ENABLED = original_flag
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_analyze_endpoint_creates_job(async_env):
    """Verify POST /tasks/{id}/analyze enqueues ANALYZE_FORM when async is enabled."""

    client, session, task = async_env

    response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    job_data = response.json()
    assert job_data["job_type"] == JOB_TYPE_ANALYZE_FORM
    assert job_data["status"] == JOB_STATUS_PENDING
    assert job_data["task_id"] == task.id

    job = session.scalar(select(Job).where(Job.task_id == task.id))
    assert job is not None
    assert job.job_type == JOB_TYPE_ANALYZE_FORM
    assert job.status == JOB_STATUS_PENDING


def test_map_endpoint_creates_job_with_mode_provider_payload(async_env):
    """Verify POST /tasks/{id}/map-fields enqueues MAP_FIELDS with mode/provider payload."""

    client, session, task = async_env

    field = FormField(
        task=task,
        label="Email",
        selector="#email",
        field_type="email",
        required=True,
    )
    session.add(field)
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/map-fields?mode=llm&provider=deepseek"
    )

    assert response.status_code == 200
    job_data = response.json()
    assert job_data["job_type"] == JOB_TYPE_MAP_FIELDS
    assert job_data["status"] == JOB_STATUS_PENDING
    assert job_data["task_id"] == task.id
    assert job_data["payload"]["mode"] == "llm"
    assert job_data["payload"]["provider"] == "deepseek"

    job = session.scalar(select(Job).where(Job.task_id == task.id))
    assert job is not None
    assert job.job_type == JOB_TYPE_MAP_FIELDS
    assert job.payload["mode"] == "llm"
    assert job.payload["provider"] == "deepseek"


@pytest.mark.parametrize("route_suffix", ["fill", "confirm-submit"])
def test_browser_write_task_routes_are_removed(async_env, route_suffix):
    """Verify legacy task browser-write routes are no longer public API."""

    client, session, task = async_env

    response = client.post(f"/tasks/{task.id}/{route_suffix}")

    assert response.status_code == 404

    job = session.scalar(select(Job).where(Job.task_id == task.id))
    assert job is None
