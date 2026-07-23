"""Tests for the rules-first SuggestionProvider."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.suggestion_provider import suggest_answers


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for suggestion provider tests."""

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


def _make_setup(session: Session, *, workflow_type: str = "security_questionnaire") -> tuple[Task, Profile, list[FormField]]:
    """Build a task, profile, and one basic field for testing."""

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

    field = FormField(
        task_id=task.id,
        label="Full name",
        field_type="text",
        selector="#full-name",
        required=True,
    )
    session.add(field)
    session.flush()

    return task, profile, [field]


def test_suggest_answers_rules_mode_requires_no_provider(session: Session) -> None:
    """Verify rules mode works without any LLM provider or API key."""

    task, profile, fields = _make_setup(session)

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    assert suggestions
    assert suggestions[0].answer_status in {
        "suggested",
        "requires_user_input",
        "unsupported",
    }


def test_suggest_answers_returns_unsupported_when_no_evidence(session: Session) -> None:
    """Verify an unknown question returns unsupported without inventing a value."""

    task, profile, fields = _make_setup(session)
    fields[0].label = "Describe your quantum key escrow program"
    fields[0].field_type = "textarea"
    fields[0].selector = "#quantum-escrow"
    fields[0].name = "quantum_escrow"
    session.flush()

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    assert suggestions
    first = suggestions[0]
    assert first.answer_status in {"unsupported", "requires_user_input"}
    assert first.suggested_value in (None, "")


def test_suggest_answers_returns_suggestion_for_known_profile_field(session: Session) -> None:
    """Verify a profile-mappable field gets a suggested answer with source context."""

    task, profile, fields = _make_setup(session)
    fields[0].label = "Your email address"
    fields[0].field_type = "email"
    session.flush()

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    assert suggestions
    first = suggestions[0]
    assert first.answer_status == "suggested"
    assert first.suggested_value == "ada@example.com"
    assert "email" in (first.mapped_profile_key or "").lower()
    assert first.confidence > 0.0


def test_suggest_answers_preserves_all_list_fields(session: Session) -> None:
    """Verify source_ids, memory_ids, and safety_flags are always present."""

    task, profile, fields = _make_setup(session)

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    for suggestion in suggestions:
        assert isinstance(suggestion.source_ids, list)
        assert isinstance(suggestion.memory_ids, list)
        assert isinstance(suggestion.safety_flags, list)


def test_suggest_answers_does_not_write_to_fields(session: Session) -> None:
    """Verify the provider is read-only and never modifies FormField rows."""

    task, profile, fields = _make_setup(session)
    original_value = fields[0].mapped_value
    original_key = fields[0].mapped_profile_key

    suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    session.refresh(fields[0])
    assert fields[0].mapped_value == original_value
    assert fields[0].mapped_profile_key == original_key


def test_suggest_answers_skips_sensitive_fields(session: Session) -> None:
    """Verify password / sensitive fields return sensitive_blocked without a value."""

    task, profile, fields = _make_setup(session)
    fields[0].label = "Password"
    fields[0].field_type = "password"
    session.flush()

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    assert suggestions
    first = suggestions[0]
    assert first.answer_status == "sensitive_blocked"
    assert first.suggested_value is None
    assert any("password" in flag.lower() for flag in first.safety_flags)


def test_suggest_answers_includes_policy_source_for_questionnaire(session: Session) -> None:
    """Verify security questionnaire workflow includes policy source evidence."""

    task, profile, fields = _make_setup(session, workflow_type="security_questionnaire")
    fields[0].label = "Do you encrypt data at rest?"
    fields[0].field_type = "radio"
    fields[0].options = [
        {"label": "Yes", "value": "yes"},
        {"label": "No", "value": "no"},
    ]
    session.flush()

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    assert suggestions
    first = suggestions[0]
    assert first.answer_status == "suggested"
    assert first.source_ids


def test_suggest_answers_llm_mode_falls_back_to_rules(session: Session) -> None:
    """Verify mode='llm' falls back to rules gracefully (no LangChain yet)."""

    task, profile, fields = _make_setup(session)

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="llm",
    )

    assert suggestions
    assert all(
        s.answer_status in {"suggested", "unsupported", "requires_user_input", "sensitive_blocked"}
        for s in suggestions
    )
