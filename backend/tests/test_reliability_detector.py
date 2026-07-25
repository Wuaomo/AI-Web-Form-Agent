"""Tests for the reliability detection service."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ActionLog, ApprovalRequest, Profile, Task, WorkflowSpan
from app.services.reliability_detector import (
    ReliabilitySignal,
    detect_reliability_signals,
    should_block_or_review,
)
from app.workflow_constants import (
    SPAN_STATUS_FAILED,
    WORKFLOW_STATUS_BLOCKED,
    WORKFLOW_STATUS_CREATED,
    WORKFLOW_STATUS_REVIEWING,
    WORKFLOW_STATUS_WAITING_APPROVAL,
    WORKFLOW_TYPE_FORM_FILL,
)


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
def task(session):
    """Create a task for testing."""

    profile = Profile(profile_name="Test")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        workflow_type=WORKFLOW_TYPE_FORM_FILL,
        workflow_status=WORKFLOW_STATUS_CREATED,
    )
    session.add(task)
    session.flush()
    return task


def test_detect_repeated_selector_failures(session, task):
    """Verify repeated failures on the same selector trigger a reliability signal."""

    # Add 3 failed action logs mentioning the same selector in message
    for i in range(3):
        log = ActionLog(
            task_id=task.id,
            step=i + 1,
            action="fill",
            status="FAILED",
            message=f"Selector '#email' failed - Attempt {i + 1}",
        )
        session.add(log)
    session.flush()

    signals = detect_reliability_signals(session, task.id, selector="#email")

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "REPEATED_SELECTOR_FAILURE"
    assert "3 times" in signal.failure_reason
    assert signal.recommended_next_state == WORKFLOW_STATUS_REVIEWING


def test_detect_repeated_action_no_progress(session, task):
    """Verify repeated actions without progress trigger a reliability signal."""

    # Add 5 repeated action logs
    for i in range(5):
        log = ActionLog(
            task_id=task.id,
            step=i + 1,
            action="goto",
            status="SUCCESS",
            message=f"Navigated {i + 1}",
        )
        session.add(log)
    session.flush()

    signals = detect_reliability_signals(session, task.id, action="goto")

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "REPEATED_ACTION_NO_PROGRESS"
    assert "5 times" in signal.failure_reason
    assert signal.recommended_next_state == WORKFLOW_STATUS_BLOCKED


def test_detect_playwright_timeout(session, task):
    """Verify Playwright timeout errors trigger a reliability signal."""

    signals = detect_reliability_signals(
        session,
        task.id,
        error_message="TimeoutError: waiting for selector '#submit' failed",
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "PLAYWRIGHT_TIMEOUT"
    assert "timeout" in signal.failure_reason.lower()
    assert signal.recommended_next_state == WORKFLOW_STATUS_REVIEWING


def test_detect_verification_mismatch(session, task):
    """Verify verification failures trigger a reliability signal."""

    verification_results = [
        {"selector": "#email", "status": "VERIFIED"},
        {"selector": "#password", "status": "FAILED"},
        {"selector": "#name", "status": "FAILED"},
    ]

    signals = detect_reliability_signals(
        session,
        task.id,
        verification_results=verification_results,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "VERIFICATION_MISMATCH"
    assert "2 field(s)" in signal.failure_reason
    assert signal.recommended_next_state == WORKFLOW_STATUS_REVIEWING


def test_detect_missing_approval(session, task):
    """Verify missing approval for risky steps triggers a reliability signal."""

    signals = detect_reliability_signals(session, task.id, step_name="submit_form")

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "MISSING_APPROVAL"
    assert "not yet granted" in signal.failure_reason
    assert signal.recommended_next_state == WORKFLOW_STATUS_WAITING_APPROVAL


def test_detect_missing_approval_with_existing_approval(session, task):
    """Verify existing approval suppresses the missing approval signal."""

    approval = ApprovalRequest(
        task_id=task.id,
        step_name="submit_form",
        status="APPROVED",
        reason="Approved for test",
        risk_type="submit",
        risk_level="HIGH",
        decision="APPROVE",
        proposed_action_json="{}",
    )
    session.add(approval)
    session.flush()

    signals = detect_reliability_signals(session, task.id, step_name="submit_form")

    assert len(signals) == 0


def test_detect_url_stagnation(session, task):
    """Verify repeated navigation to the same URL triggers a signal."""

    for i in range(3):
        log = ActionLog(
            task_id=task.id,
            step=i + 1,
            action="goto",
            status="SUCCESS",
            message=f"Navigated to https://example.com/form attempt {i + 1}",
        )
        session.add(log)
    session.flush()

    signals = detect_reliability_signals(
        session,
        task.id,
        expected_url="https://example.com/form",
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "URL_STAGNATION"
    assert "not changed" in signal.failure_reason
    assert signal.recommended_next_state == WORKFLOW_STATUS_REVIEWING


def test_no_signals_when_everything_ok(session, task):
    """Verify no signals are detected when conditions are normal."""

    signals = detect_reliability_signals(session, task.id)

    assert len(signals) == 0


def test_should_block_or_review_returns_correct_state(session, task):
    """Verify should_block_or_review returns correct stop decision and state."""

    for i in range(3):
        log = ActionLog(
            task_id=task.id,
            step=i + 1,
            action="fill",
            status="FAILED",
            message=f"Selector '#email' failed - Attempt {i + 1}",
        )
        session.add(log)
    session.flush()

    should_stop, recommended_state, reason = should_block_or_review(
        session,
        task.id,
        selector="#email",
    )

    assert should_stop is True
    assert recommended_state == WORKFLOW_STATUS_REVIEWING
    assert "3 times" in reason


def test_should_block_or_review_returns_false_when_no_signals(session, task):
    """Verify should_block_or_review returns False when no signals detected."""

    should_stop, recommended_state, reason = should_block_or_review(session, task.id)

    assert should_stop is False
    assert recommended_state == ""
    assert reason == ""


def test_multiple_signals_returns_most_severe(session, task):
    """Verify multiple signals returns the most severe one."""

    # Add both repeated selector failure and timeout
    for i in range(3):
        log = ActionLog(
            task_id=task.id,
            step=i + 1,
            action="fill",
            status="FAILED",
            message=f"Selector '#email' failed - Timeout",
        )
        session.add(log)
    session.flush()

    should_stop, recommended_state, reason = should_block_or_review(
        session,
        task.id,
        selector="#email",
        error_message="TimeoutError",
    )

    assert should_stop is True
    # REPEATED_SELECTOR_FAILURE should take priority over PLAYWRIGHT_TIMEOUT
    assert recommended_state == WORKFLOW_STATUS_REVIEWING


def test_ReliabilitySignal_is_immutable(session, task):
    """Verify ReliabilitySignal is immutable."""

    signal = ReliabilitySignal(
        signal_type="TEST",
        failure_reason="Test reason",
        recovery_hint="Test hint",
        recommended_next_state=WORKFLOW_STATUS_BLOCKED,
        evidence={"test": "data"},
    )

    with pytest.raises(AttributeError):
        signal.signal_type = "MODIFIED"