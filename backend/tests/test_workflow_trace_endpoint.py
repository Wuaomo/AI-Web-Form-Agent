"""Tests for read-only workflow trace endpoints."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Profile, Task
from app.routers.traces import router as traces_router
from app.services.workflow_trace_service import create_span


@pytest.fixture
def test_environment() -> Generator[tuple[TestClient, Session], None, None]:
    """Create an isolated app with the trace router mounted."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app = FastAPI()
    app.include_router(traces_router)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_get_task_trace_returns_404_for_missing_task(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify the endpoint returns 404 when the task does not exist."""

    client, _ = test_environment

    response = client.get("/tasks/999/trace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_get_task_trace_returns_ordered_spans(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify spans are returned oldest-first for one task."""

    client, session = test_environment
    profile = Profile(profile_name="Trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()

    create_span(session, task_id=task.id, phase="extraction", name="extract_form")
    create_span(session, task_id=task.id, phase="mapping", name="map_fields_llm")
    session.commit()

    response = client.get(f"/tasks/{task.id}/trace")

    assert response.status_code == 200
    payload = response.json()
    assert [span["name"] for span in payload] == ["extract_form", "map_fields_llm"]
