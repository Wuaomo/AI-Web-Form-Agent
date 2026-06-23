"""Integration tests for the task submission confirmation endpoint."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ActionLog, Profile, Task
from app.routers.tasks import router as tasks_router


@pytest.fixture
def test_environment() -> Generator[tuple[TestClient, Session], None, None]:
    """Provide an isolated API client and in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    test_app = FastAPI()
    test_app.include_router(tasks_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_task(session: Session, task_status: str) -> Task:
    """Create a task and its required profile for an endpoint test."""

    profile = Profile(profile_name=f"{task_status} profile")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        status=task_status,
    )
    session.add(task)
    session.commit()
    return task


def test_confirm_submit_completes_waiting_task_and_records_log(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    assert response.json() == {"task_id": task.id, "status": "COMPLETED"}

    session.refresh(task)
    assert task.status == "COMPLETED"

    log = session.scalar(
        select(ActionLog).where(ActionLog.task_id == task.id)
    )
    assert log is not None
    assert log.step == 1
    assert log.action == "confirm_submit"
    assert log.message == "User confirmed submission"
    assert log.status == "SUCCESS"


def test_confirm_submit_rejects_task_not_waiting_for_approval(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "CREATED")

    response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json() == {"detail": "Task is not waiting for approval"}

    session.refresh(task)
    assert task.status == "CREATED"
    assert session.scalar(
        select(ActionLog).where(ActionLog.task_id == task.id)
    ) is None
