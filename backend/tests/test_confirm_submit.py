"""Integration tests for the task submission confirmation endpoint."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ActionLog, FormField, Profile, Task
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
    session.flush()
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        required=True,
        mapped_profile_key="email",
        mapped_value="user@example.com",
        confidence=1.0,
    )
    session.add(field)
    session.commit()
    return task


def test_confirm_submit_submits_waiting_task_and_records_logs(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    assert response.json() == {"task_id": task.id, "status": "COMPLETED"}
    submit_form.assert_awaited_once()

    session.refresh(task)
    assert task.status == "COMPLETED"

    logs = list(
        session.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step)
        )
    )
    assert len(logs) == 2
    assert logs[0].step == 1
    assert logs[0].action == "confirm_submit"
    assert logs[0].message == "User approved final form submission."
    assert logs[0].status == "STARTED"
    assert logs[1].step == 2
    assert logs[1].action == "submit_form"
    assert logs[1].message == "Submitted the reviewed form after user approval."
    assert logs[1].status == "SUCCESS"


def test_confirm_submit_rejects_task_not_waiting_for_approval(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "CREATED")

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json() == {"detail": "Task is not waiting for approval"}
    submit_form.assert_not_awaited()

    session.refresh(task)
    assert task.status == "CREATED"
    assert session.scalar(
        select(ActionLog).where(ActionLog.task_id == task.id)
    ) is None
