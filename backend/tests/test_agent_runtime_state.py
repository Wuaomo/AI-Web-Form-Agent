"""Tests for graph-ready WorkflowState generation."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.agent_runtime_state import build_workflow_state, compact_field


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for workflow state tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_build_workflow_state_returns_minimal_task_state(session: Session) -> None:
    """Verify build_workflow_state produces the required minimal state from a task."""

    profile = Profile(
        profile_name="Demo",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com",
        profile_id=profile.id,
        workflow_type="security_questionnaire",
        workflow_status="MAPPING_READY",
    )
    session.add(task)
    session.flush()

    state = build_workflow_state(task)

    assert state["task_id"] == task.id
    assert state["workflow_type"] == "security_questionnaire"
    assert state["target_url"] == "https://example.com"
    assert state["profile_id"] == profile.id
    assert state["status"] == "MAPPING_READY"
    assert state["extracted_fields"] == []


def test_build_workflow_state_omits_sensitive_values(session: Session) -> None:
    """Verify sensitive mapped values never enter the state output."""

    profile = Profile(profile_name="Demo")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com",
        profile_id=profile.id,
        workflow_type="security_questionnaire",
        workflow_status="MAPPING_READY",
    )
    session.add(task)
    session.flush()

    field = FormField(
        task_id=task.id,
        label="Password",
        field_type="password",
        selector="#password",
        mapped_value="secret",
    )
    session.add(field)
    session.flush()

    state = build_workflow_state(task)

    assert state["extracted_fields"][0]["label"] == "Password"
    assert "secret" not in str(state)


def test_compact_field_includes_mapped_value_for_safe_fields(session: Session) -> None:
    """Verify non-sensitive fields keep their mapped_value in compact output."""

    profile = Profile(profile_name="Demo")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com",
        profile_id=profile.id,
        workflow_type="form_fill",
        workflow_status="MAPPING_READY",
    )
    session.add(task)
    session.flush()

    field = FormField(
        task_id=task.id,
        label="Full Name",
        field_type="text",
        selector="#name",
        mapped_value="Ada Lovelace",
        mapped_profile_key="full_name",
        confidence=0.95,
        required=True,
    )
    session.add(field)
    session.flush()

    item = compact_field(field)

    assert item["mapped_value"] == "Ada Lovelace"
    assert item["mapped_profile_key"] == "full_name"
    assert item["confidence"] == 0.95
    assert item["required"] is True


def test_build_workflow_state_includes_all_required_keys(session: Session) -> None:
    """Verify the state dict contains every key required by the runtime contract."""

    profile = Profile(profile_name="Demo")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com",
        profile_id=profile.id,
        workflow_type="security_questionnaire",
        workflow_status="CREATED",
    )
    session.add(task)
    session.flush()

    state = build_workflow_state(task)

    required_keys = {
        "task_id",
        "workflow_type",
        "target_url",
        "profile_id",
        "extracted_fields",
        "suggestions",
        "policy_result",
        "review_request_id",
        "verification_result",
        "status",
        "error",
    }
    assert required_keys.issubset(state.keys())


def test_build_workflow_state_falls_back_to_legacy_status(session: Session) -> None:
    """Verify status uses workflow_status when present, falling back to legacy status."""

    profile = Profile(profile_name="Demo")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com",
        profile_id=profile.id,
        workflow_type="form_fill",
        workflow_status="",
        status="CREATED",
    )
    session.add(task)
    session.flush()

    state = build_workflow_state(task)

    assert state["status"] == "CREATED"
