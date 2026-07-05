"""Tests for approval request API endpoints."""

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Profile, Task
from app.routers.approvals import router as approvals_router
from app.services.approval_gate_service import create_approval_request
from app.services.policy_engine import evaluate_submit_action


def build_environment() -> tuple[TestClient, Session]:
    """Build an isolated approval API environment."""

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
    app.include_router(approvals_router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def create_task(session: Session) -> Task:
    """Create a task for approval API tests."""

    profile = Profile(profile_name="Approval API profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    return task


def test_list_approvals_returns_created_requests() -> None:
    """Verify GET /approvals lists persisted requests."""

    client, session = build_environment()
    task = create_task(session)
    create_approval_request(
        session,
        task_id=task.id,
        step_name="submit_form",
        policy_decision=evaluate_submit_action(),
        proposed_action={"action": "submit_form"},
    )
    session.commit()

    response = client.get("/approvals")

    assert response.status_code == 200
    assert response.json()[0]["step_name"] == "submit_form"


def test_approve_endpoint_resolves_pending_request() -> None:
    """Verify POST /approvals/{id}/approve updates request status."""

    client, session = build_environment()
    task = create_task(session)
    request = create_approval_request(
        session,
        task_id=task.id,
        step_name="submit_form",
        policy_decision=evaluate_submit_action(),
        proposed_action={"action": "submit_form"},
    )
    session.commit()

    response = client.post(f"/approvals/{request.id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
