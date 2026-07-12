"""Tests for workflow template API and task creation validation."""

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Profile
from app.routers.tasks import router as tasks_router
from app.routers.workflows import router as workflows_router


def build_environment() -> tuple[TestClient, Session]:
    """Build an isolated API environment for workflow template tests."""

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
    app.include_router(workflows_router)
    app.include_router(tasks_router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def create_profile(session: Session) -> Profile:
    """Create a reusable profile for task creation tests."""

    profile = Profile(
        profile_name="Workflow template profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.commit()
    return profile


def test_workflow_templates_endpoint_returns_static_templates() -> None:
    """Verify GET /workflows/templates returns enabled and disabled templates."""

    client, session = build_environment()

    response = client.get("/workflows/templates")

    assert response.status_code == 200
    payload = response.json()
    form_fill = next(template for template in payload if template["id"] == "form_fill")
    web_extract = next(
        template for template in payload if template["id"] == "web_data_extract"
    )
    assert form_fill["enabled"] is True
    assert web_extract["enabled"] is True
    session.close()


def test_create_task_uses_default_workflow_template() -> None:
    """Verify POST /tasks defaults to the enabled form-fill template."""

    client, session = build_environment()
    profile = create_profile(session)

    response = client.post(
        "/tasks",
        json={
            "url": "https://example.com/form",
            "profile_id": profile.id,
        },
    )

    assert response.status_code == 201
    assert response.json()["workflow_type"] == "form_fill"
    session.close()


def test_create_task_rejects_disabled_workflow_template() -> None:
    """Verify POST /tasks rejects disabled workflow templates."""

    client, session = build_environment()
    profile = create_profile(session)

    response = client.post(
        "/tasks",
        json={
            "url": "https://example.com/form",
            "profile_id": profile.id,
            "workflow_type": "data_entry",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Workflow template is not enabled: data_entry"
    session.close()
