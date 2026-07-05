"""Tests for approval gate persistence helpers."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Profile, Task
from app.services.approval_gate_service import (
    approve_request,
    create_approval_request,
    has_pending_approval,
    latest_approved_request_for_action,
    latest_approved_request,
    reject_request,
)
from app.services.policy_engine import evaluate_submit_action


def make_session() -> Session:
    """Create an isolated in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def create_task(session: Session) -> Task:
    """Create one task fixture for approval service tests."""

    profile = Profile(profile_name="Approval profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    return task


def test_create_and_approve_request_updates_status() -> None:
    """Verify review-required requests can be approved and queried."""

    session = make_session()
    task = create_task(session)

    request = create_approval_request(
        session,
        task_id=task.id,
        step_name="submit_form",
        policy_decision=evaluate_submit_action(),
        proposed_action={"action": "submit_form"},
    )
    session.commit()

    assert has_pending_approval(session, task_id=task.id, step_name="submit_form") is True

    approve_request(session, request.id)
    session.commit()

    assert latest_approved_request(session, task_id=task.id, step_name="submit_form").id == request.id


def test_reject_request_marks_request_rejected() -> None:
    """Verify a pending request can be rejected once."""

    session = make_session()
    task = create_task(session)
    request = create_approval_request(
        session,
        task_id=task.id,
        step_name="fill_field:1",
        policy_decision=evaluate_submit_action(),
        proposed_action={"action": "fill_field"},
    )
    session.commit()

    reject_request(session, request.id)
    session.commit()

    session.refresh(request)
    assert request.status == "REJECTED"


def test_latest_approved_request_for_action_requires_exact_payload_match() -> None:
    """Verify approved requests only match the exact proposed action snapshot."""

    session = make_session()
    task = create_task(session)
    request = create_approval_request(
        session,
        task_id=task.id,
        step_name="submit_form",
        policy_decision=evaluate_submit_action(),
        proposed_action={"action": "submit_form", "fields": [{"field_id": 1, "mapped_value": "a"}]},
    )
    session.commit()
    approve_request(session, request.id)
    session.commit()

    matched = latest_approved_request_for_action(
        session,
        task_id=task.id,
        step_name="submit_form",
        proposed_action={"action": "submit_form", "fields": [{"field_id": 1, "mapped_value": "a"}]},
    )
    not_matched = latest_approved_request_for_action(
        session,
        task_id=task.id,
        step_name="submit_form",
        proposed_action={"action": "submit_form", "fields": [{"field_id": 1, "mapped_value": "b"}]},
    )

    assert matched is not None
    assert matched.id == request.id
    assert not_matched is None
