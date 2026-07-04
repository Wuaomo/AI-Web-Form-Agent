"""Tests for agent review API endpoints."""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from app.agent_constants import (
    AGENT_ROLE_MAPPING_CRITIC,
    AGENT_ROLE_SAFETY_REVIEW,
    AGENT_ROLE_EXECUTION_VERIFICATION,
)
from app.database import Base, get_db
from app.routers.tasks import router as tasks_router


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
    test_app.include_router(tasks_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_task(test_environment):
    """Create a task for endpoint tests."""

    client, session = test_environment

    from app.models import Profile, Task

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    return task.id


def test_run_mapping_critic_via_endpoint(test_environment):
    """Verify that mapping critic can be run via POST endpoint."""

    client, session = test_environment
    task_id = create_task(test_environment)

    response = client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": [AGENT_ROLE_MAPPING_CRITIC]},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == AGENT_ROLE_MAPPING_CRITIC
    assert "decision" in data[0]
    assert "output" in data[0]
    assert "summary" in data[0]["output"]
    assert "items" in data[0]["output"]


def test_invalid_role_rejected(test_environment):
    """Verify that invalid agent role is rejected with 400."""

    client, session = test_environment
    task_id = create_task(test_environment)

    response = client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": ["INVALID_ROLE"]},
    )

    assert response.status_code == 400
    assert "Invalid agent role" in response.json()["detail"]


def test_reviews_listed_after_run(test_environment):
    """Verify that reviews can be listed via GET endpoint after running."""

    client, session = test_environment
    task_id = create_task(test_environment)

    client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": [AGENT_ROLE_SAFETY_REVIEW]},
    )

    response = client.get(f"/tasks/{task_id}/agent-reviews")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["role"] == AGENT_ROLE_SAFETY_REVIEW


def test_missing_task_returns_404(test_environment):
    """Verify that missing task returns 404."""

    client, session = test_environment

    response = client.get("/tasks/99999/agent-reviews")
    assert response.status_code == 404

    response = client.post(
        "/tasks/99999/agent-reviews",
        json={"roles": [AGENT_ROLE_MAPPING_CRITIC]},
    )
    assert response.status_code == 404


def test_run_all_roles_when_empty_list(test_environment):
    """Verify that all roles are run when roles list is empty."""

    client, session = test_environment
    task_id = create_task(test_environment)

    response = client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": []},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_run_multiple_roles(test_environment):
    """Verify that multiple roles can be run in sequence."""

    client, session = test_environment
    task_id = create_task(test_environment)

    response = client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": [AGENT_ROLE_MAPPING_CRITIC, AGENT_ROLE_SAFETY_REVIEW]},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_reviews_returns_newest_first(test_environment):
    """Verify that GET endpoint returns reviews newest first."""

    client, session = test_environment
    task_id = create_task(test_environment)

    response1 = client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": [AGENT_ROLE_MAPPING_CRITIC]},
    )
    data1 = response1.json()
    first_review_id = data1[0]["id"]

    response2 = client.post(
        f"/tasks/{task_id}/agent-reviews",
        json={"roles": [AGENT_ROLE_SAFETY_REVIEW]},
    )
    data2 = response2.json()
    second_review_id = data2[0]["id"]

    response = client.get(f"/tasks/{task_id}/agent-reviews")
    data = response.json()

    assert data[0]["id"] == second_review_id
    assert data[1]["id"] == first_review_id


def test_post_without_body_runs_all(test_environment):
    """Verify that POST without body runs all roles."""

    client, session = test_environment
    task_id = create_task(test_environment)

    response = client.post(f"/tasks/{task_id}/agent-reviews")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1