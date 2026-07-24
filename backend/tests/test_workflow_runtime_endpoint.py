"""Tests for workflow runtime API (start/get/review)."""

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import FormField, Profile, Task
from app.routers.workflows import router as workflows_router
from app.services.agent_runtime.security_questionnaire_graph import (
    _reset_runtime_for_tests,
)


def _clear_runtime_state() -> None:
    """Clear all in-memory graph state between tests."""

    _reset_runtime_for_tests()


def build_environment() -> tuple[TestClient, Session]:
    """Build an isolated API environment for workflow runtime tests."""

    _clear_runtime_state()

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
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def create_profile(session: Session) -> Profile:
    profile = Profile(
        profile_name="Runtime test profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.commit()
    return profile


def create_security_questionnaire_task(
    session: Session, profile: Profile
) -> Task:
    task = Task(
        url="https://example.com/security-questionnaire",
        profile_id=profile.id,
        workflow_type="security_questionnaire",
        status="READY",
        workflow_status="READY",
    )
    session.add(task)
    session.flush()

    field1 = FormField(
        task_id=task.id,
        label="What is your employee ID?",
        name="employee_id",
        field_type="text",
        selector="#employee_id",
    )
    field2 = FormField(
        task_id=task.id,
        label="What department do you work in?",
        name="department",
        field_type="text",
        selector="#department",
    )
    session.add_all([field1, field2])
    session.commit()
    session.refresh(task)
    return task


def create_form_fill_task(session: Session, profile: Profile) -> Task:
    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        workflow_type="form_fill",
        status="READY",
        workflow_status="READY",
    )
    session.add(task)
    session.commit()
    return task


# ---------------------------------------------------------------------------
# Start endpoint tests
# ---------------------------------------------------------------------------


def test_start_endpoint_runs_to_review_interrupt() -> None:
    """POST /workflows/{task_id}/start returns state paused at review."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.post(f"/workflows/{task.id}/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["workflow_type"] == "security_questionnaire"
    assert payload["interrupt_at"] == "review"
    assert payload["current_node"] == "apply_review_decision"
    assert len(payload["suggestions"]) > 0
    assert "policy_result" in payload
    session.close()


def test_start_endpoint_rejects_unsupported_workflow() -> None:
    """POST /workflows/{task_id}/start returns 400 for form_fill."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    response = client.post(f"/workflows/{task.id}/start")

    assert response.status_code == 400
    assert "security_questionnaire" in response.json()["detail"]
    session.close()


def test_start_endpoint_returns_404_for_missing_task() -> None:
    """POST /workflows/{task_id}/start returns 404 if task doesn't exist."""

    client, session = build_environment()

    response = client.post("/workflows/9999/start")

    assert response.status_code == 404
    session.close()


# ---------------------------------------------------------------------------
# Get endpoint tests
# ---------------------------------------------------------------------------


def test_get_endpoint_returns_compact_state() -> None:
    """GET /workflows/{task_id} returns compact runtime state."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    client.post(f"/workflows/{task.id}/start")

    response = client.get(f"/workflows/{task.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["interrupt_at"] == "review"
    assert "suggestions" in payload
    assert "policy_result" in payload
    session.close()


def test_get_endpoint_returns_404_when_no_runtime_state() -> None:
    """GET /workflows/{task_id} returns 404 if no runtime has been started."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.get(f"/workflows/{task.id}")

    assert response.status_code == 404
    session.close()


# ---------------------------------------------------------------------------
# Review endpoint tests
# ---------------------------------------------------------------------------


def test_review_endpoint_requires_prior_start() -> None:
    """POST /workflows/{task_id}/review returns 409 if not at review gate."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.post(
        f"/workflows/{task.id}/review",
        json={"decision": "approve_all", "approvals": []},
    )

    assert response.status_code == 409
    session.close()


def test_review_endpoint_advances_past_review_gate() -> None:
    """POST /workflows/{task_id}/review resumes graph past review."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    client.post(f"/workflows/{task.id}/start")

    response = client.post(
        f"/workflows/{task.id}/review",
        json={"decision": "approve_all", "approvals": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interrupt_at"] == "submit_approval"
    assert payload["status"] in ("AWAITING_SUBMIT_APPROVAL", "VERIFYING")
    session.close()


def test_review_endpoint_rejects_unsupported_workflow() -> None:
    """POST /workflows/{task_id}/review returns 400 for non-security workflows."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    response = client.post(
        f"/workflows/{task.id}/review",
        json={"decision": "approve_all", "approvals": []},
    )

    assert response.status_code == 400
    session.close()


# ---------------------------------------------------------------------------
# Security: no sensitive values in response
# ---------------------------------------------------------------------------


def test_response_does_not_leak_sensitive_values() -> None:
    """API response does not include raw sensitive field values."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.post(f"/workflows/{task.id}/start")

    assert response.status_code == 200
    payload = response.json()

    assert "memory_hits" in payload
    for hit in payload.get("memory_hits", []):
        assert "value" not in hit or hit.get("value") is None or hit.get("value") == ""

    assert "profile_values" not in payload
    session.close()


# ---------------------------------------------------------------------------
# No generic resume exposed
# ---------------------------------------------------------------------------


def test_no_generic_resume_endpoint_exists() -> None:
    """Generic /resume endpoint is not exposed — only /review."""

    client, session = build_environment()

    resume_response = client.post("/workflows/1/resume")
    assert resume_response.status_code == 404

    state_response = client.post("/workflows/1/state")
    assert state_response.status_code == 404

    session.close()
