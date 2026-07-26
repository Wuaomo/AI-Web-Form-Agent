"""Tests for the AgentStep presentation model and timeline service."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    ActionLog,
    Profile,
    Task,
    WorkflowSpan,
    WORKFLOW_STATUS_CREATED,
    WORKFLOW_TYPE_FORM_FILL,
)
from app.services.agent_step_timeline import build_agent_steps_for_task
from app.workflow_constants import SPAN_STATUS_FAILED, SPAN_STATUS_SUCCESS


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for tests."""

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


@pytest.fixture
def task_with_plan(session):
    """Create a task with a persisted workflow plan."""

    profile = Profile(profile_name="Test")
    session.add(profile)
    session.flush()

    plan = {
        "workflow_type": WORKFLOW_TYPE_FORM_FILL,
        "goal": "Fill form",
        "steps": [
            {
                "step_id": "open_url",
                "tool": "open_url",
                "reason": "Open the target URL",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "extract_form",
                "tool": "extract_form",
                "reason": "Extract form fields",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "fill_form",
                "tool": "fill_form",
                "reason": "Fill mapped fields",
                "requires_approval": False,
                "status": "PENDING",
            },
        ],
    }

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        workflow_type=WORKFLOW_TYPE_FORM_FILL,
        workflow_status=WORKFLOW_STATUS_CREATED,
        workflow_plan=plan,
    )
    session.add(task)
    session.flush()
    return task


def test_build_agent_steps_returns_plan_steps_without_trace(session, task_with_plan):
    """Verify agent steps are returned even when no trace spans exist."""

    steps = build_agent_steps_for_task(session, task_with_plan)

    assert len(steps) == 3
    assert steps[0].step_id == "open_url"
    assert steps[0].tool == "open_url"
    assert steps[0].goal == "Open the target URL"
    assert steps[0].status == "PENDING"
    assert steps[0].input_summary is None
    assert steps[0].output_summary is None
    assert steps[0].error is None


def test_build_agent_steps_includes_trace_status(session, task_with_plan):
    """Verify agent steps reflect span status when trace data exists."""

    span = WorkflowSpan(
        task_id=task_with_plan.id,
        phase="browser",
        name="open_url",
        status=SPAN_STATUS_SUCCESS,
        input={"url": "https://example.com/form", "task_id": task_with_plan.id},
        output={"page_opened": True},
    )
    session.add(span)
    session.flush()

    steps = build_agent_steps_for_task(session, task_with_plan)

    open_step = next(s for s in steps if s.step_id == "open_url")
    assert open_step.status == SPAN_STATUS_SUCCESS
    assert open_step.input_summary is not None
    assert "url=https://example.com/form" in open_step.input_summary


def test_build_agent_steps_includes_failed_step_error(session, task_with_plan):
    """Verify failed steps include error message and recovery hint."""

    span = WorkflowSpan(
        task_id=task_with_plan.id,
        phase="browser",
        name="open_url",
        status=SPAN_STATUS_FAILED,
        input={"url": "https://example.com/form"},
        error_message="Network timeout connecting to URL",
    )
    session.add(span)
    session.flush()

    steps = build_agent_steps_for_task(session, task_with_plan)

    open_step = next(s for s in steps if s.step_id == "open_url")
    assert open_step.status == SPAN_STATUS_FAILED
    assert open_step.error == "Network timeout connecting to URL"
    assert open_step.recovery_hint is not None


def test_build_agent_steps_uses_log_status_when_no_span(session, task_with_plan):
    """Verify action log status is used when no matching span exists."""

    log = ActionLog(
        task_id=task_with_plan.id,
        step=1,
        action="extract_form",
        message="Extracted 5 fields",
        status="SUCCESS",
    )
    session.add(log)
    session.flush()

    steps = build_agent_steps_for_task(session, task_with_plan)

    extract_step = next(s for s in steps if s.step_id == "extract_form")
    assert extract_step.status == "SUCCESS"


def test_build_agent_steps_redacts_sensitive_content(session, task_with_plan):
    """Verify sensitive values are redacted from summaries."""

    span = WorkflowSpan(
        task_id=task_with_plan.id,
        phase="browser",
        name="fill_form",
        status=SPAN_STATUS_SUCCESS,
        input={"password": "secret123", "task_id": task_with_plan.id},
        output={"password_field": "secret123"},
    )
    session.add(span)
    session.flush()

    steps = build_agent_steps_for_task(session, task_with_plan)

    fill_step = next(s for s in steps if s.step_id == "fill_form")
    assert fill_step.input_summary == "[REDACTED]"
    assert fill_step.output_summary == "[REDACTED]"


def test_build_agent_steps_includes_evidence_types(session, task_with_plan):
    """Verify evidence list includes verification and approval when available."""

    span = WorkflowSpan(
        task_id=task_with_plan.id,
        phase="browser",
        name="fill_form",
        status=SPAN_STATUS_SUCCESS,
        screenshot_id=1,
        output={"filled_count": 3},
    )
    session.add(span)
    session.flush()

    steps = build_agent_steps_for_task(session, task_with_plan)

    fill_step = next(s for s in steps if s.step_id == "fill_form")
    assert "screenshot" in fill_step.evidence
    assert "trace_output" in fill_step.evidence


def test_build_agent_steps_includes_timestamps(session, task_with_plan):
    """Verify started_at is populated when span exists."""

    span = WorkflowSpan(
        task_id=task_with_plan.id,
        phase="browser",
        name="open_url",
        status=SPAN_STATUS_SUCCESS,
    )
    session.add(span)
    session.flush()

    steps = build_agent_steps_for_task(session, task_with_plan)

    open_step = next(s for s in steps if s.step_id == "open_url")
    assert open_step.started_at is not None


def test_build_agent_steps_empty_plan_returns_empty_list(session):
    """Verify empty or missing plan returns empty step list."""

    profile = Profile(profile_name="Test")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        workflow_type=WORKFLOW_TYPE_FORM_FILL,
        workflow_status=WORKFLOW_STATUS_CREATED,
        workflow_plan={},
    )
    session.add(task)
    session.flush()

    steps = build_agent_steps_for_task(session, task)

    assert len(steps) == 0