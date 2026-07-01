"""Tests for admin-only action trace endpoints."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base, get_db
from app.models import Profile, Task
from app.routers.admin import router as admin_router
from app.services.action_trace_service import record_action_trace


@pytest.fixture
def test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    monkeypatch.setattr(config, "ADMIN_API_TOKEN", "secret")

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    test_app = FastAPI()
    test_app.include_router(admin_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_admin_trace_endpoint_requires_token_when_configured(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    profile = Profile(profile_name="Admin trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    record_action_trace(
        session,
        task_id=task.id,
        phase="fill",
        action="fill",
        result="success",
        selector="#email",
    )

    rejected = client.get(f"/admin/tasks/{task.id}/traces")
    accepted = client.get(
        f"/admin/tasks/{task.id}/traces",
        headers={"X-Admin-Token": "secret"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()[0]["selector"] == "#email"

