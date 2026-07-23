"""Tests for the optional LangChain suggestion adapter."""

from collections.abc import Generator
from importlib import reload
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services import langchain_suggestion_adapter as adapter
from app.services.langchain_suggestion_adapter import (
    LangChainUnavailableError,
    is_available,
    suggest_answers_with_langchain,
)
from app.services.suggestion_provider import suggest_answers


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for adapter tests."""

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


def _make_setup(session: Session) -> tuple[Task, Profile, list[FormField]]:
    """Build a task, profile, and one field for testing."""

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
        workflow_type="security_questionnaire",
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


def test_is_available_returns_false_without_langchain() -> None:
    """Verify is_available returns False when LangChain is not installed."""

    with patch.dict("sys.modules", {"langchain": None}):
        assert is_available() is False


def test_suggest_answers_with_langchain_raises_when_unavailable() -> None:
    """Verify the adapter raises LangChainUnavailableError when not installed."""

    with patch.object(adapter, "is_available", return_value=False):
        with pytest.raises(LangChainUnavailableError):
            suggest_answers_with_langchain({"questions": []})


def test_langchain_adapter_validates_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLM output passes through AnswerSuggestion schema validation."""

    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(
        adapter,
        "_invoke_model",
        lambda payload: [
            {
                "question_id": "q1",
                "field_id": "f1",
                "suggested_value": None,
                "confidence": 0.7,
                "answer_status": "unsupported",
                "reason": "No source",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": [],
            }
        ],
    )

    result = suggest_answers_with_langchain({"questions": []})

    assert len(result) == 1
    assert result[0].answer_status == "unsupported"
    assert result[0].suggested_value is None


def test_langchain_adapter_rejects_invalid_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify schema-invalid LLM output is rejected, not silently accepted."""

    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(
        adapter,
        "_invoke_model",
        lambda payload: [
            {
                "question_id": "q1",
                "suggested_value": "Yes",
                "confidence": 1.5,
                "answer_status": "suggested",
                "reason": "Bad confidence",
            }
        ],
    )

    result = suggest_answers_with_langchain({"questions": []})

    assert result == []


def test_langchain_adapter_rejects_unsupported_with_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify unsupported status with a value is rejected by the validator."""

    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(
        adapter,
        "_invoke_model",
        lambda payload: [
            {
                "question_id": "q1",
                "field_id": "f1",
                "suggested_value": "Yes",
                "confidence": 0.5,
                "answer_status": "unsupported",
                "reason": "Has value but unsupported",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": [],
            }
        ],
    )

    result = suggest_answers_with_langchain({"questions": []})

    assert result == []


def test_suggestion_provider_falls_back_when_llm_unconfigured(session: Session) -> None:
    """Verify mode='llm' falls back to rules when LangChain is not available."""

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


def test_suggestion_provider_uses_langchain_when_available(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify mode='llm' uses LangChain output when available and valid."""

    task, profile, fields = _make_setup(session)

    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(
        adapter,
        "_invoke_model",
        lambda payload: [
            {
                "question_id": str(fields[0].id),
                "field_id": str(fields[0].id),
                "suggested_value": "Ada Lovelace",
                "mapped_profile_key": "full_name",
                "confidence": 0.95,
                "answer_status": "suggested",
                "reason": "LLM matched full_name from profile",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": [],
            }
        ],
    )

    suggestions = suggest_answers(
        session,
        task=task,
        fields=fields,
        profile=profile,
        mode="llm",
    )

    assert len(suggestions) == 1
    assert suggestions[0].answer_status == "suggested"
    assert suggestions[0].suggested_value == "Ada Lovelace"
    assert suggestions[0].confidence == 0.95
