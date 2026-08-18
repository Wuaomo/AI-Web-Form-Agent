"""Tests for source-backed policy answer suggestions."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task, WorkflowMemoryItem
from app.services.policy_answer_retrieval import apply_policy_answer_suggestions, suggest_policy_answer
from app.workflow_constants import (
    MEMORY_TYPE_CONFIRMED_QUESTIONNAIRE_ANSWER,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
)


def test_suggest_policy_answer_returns_source_backed_match(tmp_path: Path) -> None:
    policy = tmp_path / "mock-security-policy.md"
    policy.write_text(
        "# Security Policy\n\n"
        "## Multi-Factor Authentication\n"
        "Answer: Yes. MFA is required for administrative access.\n",
        encoding="utf-8",
    )

    suggestion = suggest_policy_answer(
        "Do you enforce multi-factor authentication?",
        policy_paths=[policy],
    )

    assert suggestion is not None
    assert suggestion.answer == "Yes. MFA is required for administrative access."
    assert suggestion.source == "mock-security-policy.md"
    assert suggestion.matched_section == "Multi-Factor Authentication"
    assert suggestion.status == "needs_review"


def test_suggest_policy_answer_refuses_unsupported_question(tmp_path: Path) -> None:
    policy = tmp_path / "mock-security-policy.md"
    policy.write_text(
        "# Security Policy\n\n"
        "## Data Retention\n"
        "Answer: 90 days for standard workflow logs.\n",
        encoding="utf-8",
    )

    assert suggest_policy_answer("What is your office lunch policy?", policy_paths=[policy]) is None


def test_apply_policy_answer_suggestions_uses_reviewed_answer_memory() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        profile = Profile(profile_name="Questionnaire profile")
        session.add(profile)
        session.flush()
        task = Task(
            url="https://example.com/security",
            profile_id=profile.id,
            workflow_type=WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
        )
        session.add(task)
        session.flush()
        field = FormField(
            task_id=task.id,
            label="Is MFA required for admin users?",
            selector="#mfa",
            field_type="radio",
        )
        session.add(field)
        memory = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_QUESTIONNAIRE_ANSWER,
            workflow_type=WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
            field_signature="answer-sig-001",
            field_text="question: Do you require MFA for administrators?\nanswer: Yes",
            mapped_profile_key="reviewed_answer",
            value_kind="questionnaire_answer",
        )
        session.add(memory)
        session.commit()

        evidence = apply_policy_answer_suggestions(
            fields=[field],
            db=session,
            task=task,
            policy_paths=[],
        )

        assert field.mapped_value == "Yes"
        assert evidence[0]["source"] == "reviewed_answer_memory"
        assert evidence[0]["memory_id"] == str(memory.id)
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
