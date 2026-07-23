"""Tests for the LangGraph security questionnaire runtime."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.agent_runtime.security_questionnaire_graph import (
    SUPPORTED_WORKFLOWS,
    build_security_questionnaire_graph,
    run_until_review,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session."""

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


def _make_task(session: Session, workflow_type: str = "security_questionnaire") -> Task:
    """Build a task with profile and a couple fields for graph tests."""

    profile = Profile(
        profile_name="Demo",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/security",
        profile_id=profile.id,
        workflow_type=workflow_type,
        workflow_status="MAPPING_READY",
    )
    session.add(task)
    session.flush()

    field1 = FormField(
        task_id=task.id,
        label="Do you encrypt data at rest?",
        field_type="radio",
        selector="#encrypt-at-rest",
        required=True,
    )
    field2 = FormField(
        task_id=task.id,
        label="Your full name",
        field_type="text",
        selector="#full-name",
        required=True,
    )
    session.add_all([field1, field2])
    session.flush()

    return task


def test_only_security_questionnaire_is_supported() -> None:
    """Verify only security_questionnaire is in the supported set."""

    assert "security_questionnaire" in SUPPORTED_WORKFLOWS
    assert "form_fill" not in SUPPORTED_WORKFLOWS
    assert "vendor_onboarding" not in SUPPORTED_WORKFLOWS


def test_run_until_review_rejects_unsupported_workflow(session: Session) -> None:
    """Verify form_fill raises ValueError for the graph runtime."""

    task = _make_task(session, workflow_type="form_fill")

    with pytest.raises(ValueError, match="security_questionnaire"):
        run_until_review(session, task=task)


def test_build_graph_has_all_required_nodes() -> None:
    """Verify the graph contains all required nodes."""

    graph = build_security_questionnaire_graph()

    assert graph is not None
    graph_nodes = graph.get_graph().nodes
    required_nodes = [
        "start",
        "analyze_page",
        "extract_questions",
        "retrieve_reviewed_memory",
        "retrieve_policy_sources",
        "suggest_answers",
        "policy_check",
        "apply_review_decision",
        "fill_browser",
        "verify_result",
        "finish",
        "fail",
    ]
    for node_name in required_nodes:
        assert node_name in graph_nodes, (
            f"Node '{node_name}' not found in graph"
        )


def test_run_until_review_stops_before_fill(session: Session) -> None:
    """Verify the graph interrupts at review and never calls fill_browser."""

    task = _make_task(session)

    fill_called = {"count": 0}

    def fake_fill(state, config):
        fill_called["count"] += 1
        return state

    with patch(
        "app.services.agent_runtime.security_questionnaire_graph._fill_browser_node",
        side_effect=fake_fill,
    ):
        result = run_until_review(session, task=task)

    assert fill_called["count"] == 0
    assert result["interrupt_at"] == "review"
    assert result["status"] == "AWAITING_REVIEW"


def test_run_until_review_produces_suggestions(session: Session) -> None:
    """Verify suggestions are populated before the review interrupt."""

    task = _make_task(session)

    result = run_until_review(session, task=task)

    assert result["suggestions"]
    assert len(result["suggestions"]) >= 2
    for suggestion in result["suggestions"]:
        assert isinstance(suggestion, dict)
        assert suggestion["answer_status"] in {
            "suggested",
            "unsupported",
            "requires_user_input",
            "sensitive_blocked",
        }


def test_graph_does_not_bypass_policy_engine(session: Session) -> None:
    """Verify policy_check runs and produces a policy_result."""

    task = _make_task(session)
    result = run_until_review(session, task=task)

    assert result["policy_result"] is not None
    assert isinstance(result["policy_result"], dict)
    assert "total" in result["policy_result"]
    assert "decisions" in result["policy_result"]


def test_suggestions_include_policy_source_ids(session: Session) -> None:
    """Verify suggestions carry source_ids and memory_ids lists."""

    task = _make_task(session)
    result = run_until_review(session, task=task)

    for s in result["suggestions"]:
        assert "source_ids" in s
        assert "memory_ids" in s
        assert "safety_flags" in s
        assert isinstance(s["source_ids"], list)
        assert isinstance(s["memory_ids"], list)
        assert isinstance(s["safety_flags"], list)


def test_graph_state_includes_all_required_keys(session: Session) -> None:
    """Verify the final state has all required keys at the review interrupt."""

    task = _make_task(session)
    result = run_until_review(session, task=task)

    required_keys = [
        "task_id",
        "workflow_type",
        "target_url",
        "profile_id",
        "extracted_fields",
        "memory_hits",
        "policy_sources",
        "suggestions",
        "policy_result",
        "review_request_id",
        "review_decision",
        "browser_execution_id",
        "verification_result",
        "submit_approval_request_id",
        "status",
        "error",
        "interrupt_at",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"
