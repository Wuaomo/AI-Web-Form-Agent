"""Tests for workflow plan API endpoints and default persistence."""

from collections.abc import Generator
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Profile, Task
from app.routers.tasks import router as tasks_router


def build_environment() -> tuple[TestClient, Session]:
    """Build an isolated API environment for workflow plan tests."""

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
    app.include_router(tasks_router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def create_profile(session: Session) -> Profile:
    """Create a reusable profile for workflow plan tests."""

    profile = Profile(
        profile_name="Workflow plan profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.commit()
    return profile


def create_task(session: Session, *, workflow_plan_json: str | None = None) -> Task:
    """Create a task row directly for workflow plan endpoint tests."""

    profile = create_profile(session)
    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        description="Internship application",
        workflow_plan_json=workflow_plan_json,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_create_task_stores_default_plan() -> None:
    """Verify POST /tasks persists the deterministic default workflow plan."""

    client, session = build_environment()
    profile = create_profile(session)

    with patch("app.routers.tasks.safe_create_span", return_value=None), patch(
        "app.routers.tasks.safe_finish_span",
    ):
        response = client.post(
            "/tasks",
            json={
                "url": "https://example.com/form",
                "profile_id": profile.id,
                "description": "Internship application",
            },
        )

    assert response.status_code == 201
    task = session.get(Task, response.json()["id"])
    assert task is not None
    assert task.workflow_plan["workflow_type"] == "form_fill"
    assert task.workflow_plan["goal"] == "Internship application"

    session.close()


def test_get_task_plan_returns_saved_plan() -> None:
    """Verify GET /tasks/{id}/plan returns the persisted workflow plan."""

    client, session = build_environment()
    task = create_task(session)
    task.workflow_plan = {
        "workflow_type": "form_fill",
        "goal": "Internship application",
        "steps": [
            {
                "step_id": "open_url",
                "tool": "open_url",
                "reason": "Open the target page.",
                "requires_approval": False,
                "status": "PENDING",
            }
        ],
    }
    session.add(task)
    session.commit()

    response = client.get(f"/tasks/{task.id}/plan")

    assert response.status_code == 200
    assert response.json()["goal"] == "Internship application"
    session.close()


def test_get_task_plan_returns_404_when_plan_is_missing() -> None:
    """Verify GET /tasks/{id}/plan returns 404 when nothing was saved."""

    client, session = build_environment()
    task = create_task(session)

    response = client.get(f"/tasks/{task.id}/plan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow plan not found"
    session.close()


def test_get_task_plan_returns_500_for_malformed_saved_json() -> None:
    """Verify malformed saved plan JSON is surfaced as an error."""

    client, session = build_environment()
    task = create_task(session, workflow_plan_json="{broken json")

    response = client.get(f"/tasks/{task.id}/plan")

    assert response.status_code == 500
    assert response.json()["detail"] == "Invalid workflow plan JSON"
    session.close()


def test_post_task_plan_rebuilds_and_replaces_saved_plan() -> None:
    """Verify POST /tasks/{id}/plan rebuilds and overwrites the saved plan."""

    client, session = build_environment()
    task = create_task(session, workflow_plan_json="{broken json")

    with patch("app.routers.tasks.safe_create_span", return_value=None), patch(
        "app.routers.tasks.safe_finish_span",
    ):
        response = client.post(
            f"/tasks/{task.id}/plan",
            json={"goal": "Fill this internship application using my student profile."},
        )

    assert response.status_code == 200
    assert response.json()["goal"] == "Fill this internship application using my student profile."
    session.refresh(task)
    assert task.workflow_plan["goal"] == "Fill this internship application using my student profile."
    assert [step["step_id"] for step in task.workflow_plan["steps"]] == [
        "open_url",
        "extract_form",
        "map_fields",
        "review_mapping",
        "fill_form",
        "verify_fields",
        "submit_form",
    ]
    session.close()


def test_post_task_plan_rejects_whitespace_only_goal_without_overwriting() -> None:
    """Verify whitespace-only goals return 400 and keep the previous saved plan."""

    client, session = build_environment()
    task = create_task(session)
    task.workflow_plan = {
        "workflow_type": "form_fill",
        "goal": "Existing plan goal",
        "steps": [
            {
                "step_id": "open_url",
                "tool": "open_url",
                "reason": "Open the target page.",
                "requires_approval": False,
                "status": "PENDING",
            }
        ],
    }
    session.add(task)
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/plan",
        json={"goal": "   "},
    )

    assert response.status_code == 400
    session.refresh(task)
    assert task.workflow_plan["goal"] == "Existing plan goal"
    assert task.workflow_plan["steps"][0]["step_id"] == "open_url"
    session.close()
