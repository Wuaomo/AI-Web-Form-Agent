"""Tests for AnswerSuggestion, MemoryHit, and PolicySourceHit schemas."""

import pytest

from app.services.suggestion_types import (
    AnswerSuggestion,
    MemoryHit,
    PolicySourceHit,
    validate_answer_suggestion_payload,
)


def test_validate_answer_suggestion_payload_returns_suggestion() -> None:
    """Verify a well-formed payload produces an AnswerSuggestion."""

    suggestion = validate_answer_suggestion_payload(
        {
            "question_id": "q1",
            "field_id": "f1",
            "suggested_value": "Yes",
            "confidence": 0.9,
            "answer_status": "suggested",
            "reason": "Policy doc section 3.2",
            "source_ids": ["src-1"],
            "memory_ids": ["mem-1"],
            "safety_flags": [],
        }
    )

    assert isinstance(suggestion, AnswerSuggestion)
    assert suggestion.question_id == "q1"
    assert suggestion.suggested_value == "Yes"
    assert suggestion.confidence == 0.9
    assert suggestion.answer_status == "suggested"


def test_unsupported_suggestion_cannot_include_value() -> None:
    """Verify unsupported suggestions reject a non-null suggested_value."""

    with pytest.raises(ValueError):
        validate_answer_suggestion_payload(
            {
                "question_id": "q1",
                "field_id": "f1",
                "suggested_value": "Yes",
                "confidence": 0.5,
                "answer_status": "unsupported",
                "reason": "No source",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": [],
            }
        )


def test_sensitive_blocked_suggestion_cannot_include_value() -> None:
    """Verify sensitive_blocked suggestions reject a non-null suggested_value."""

    with pytest.raises(ValueError):
        validate_answer_suggestion_payload(
            {
                "question_id": "q1",
                "field_id": "f1",
                "suggested_value": "secret",
                "confidence": 0.0,
                "answer_status": "sensitive_blocked",
                "reason": "Password field",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": ["password"],
            }
        )


def test_confidence_must_be_between_zero_and_one() -> None:
    """Verify confidence above 1.0 is rejected."""

    with pytest.raises(ValueError):
        validate_answer_suggestion_payload(
            {
                "question_id": "q1",
                "field_id": None,
                "suggested_value": None,
                "confidence": 1.5,
                "answer_status": "requires_user_input",
                "reason": "Need user input",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": [],
            }
        )


def test_confidence_below_zero_is_rejected() -> None:
    """Verify negative confidence is rejected."""

    with pytest.raises(ValueError):
        validate_answer_suggestion_payload(
            {
                "question_id": "q1",
                "field_id": None,
                "suggested_value": None,
                "confidence": -0.1,
                "answer_status": "requires_user_input",
                "reason": "Need user input",
                "source_ids": [],
                "memory_ids": [],
                "safety_flags": [],
            }
        )


def test_unsupported_suggestion_with_null_value_is_valid() -> None:
    """Verify unsupported suggestions with null value pass validation."""

    suggestion = validate_answer_suggestion_payload(
        {
            "question_id": "q1",
            "field_id": "f1",
            "suggested_value": None,
            "confidence": 0.0,
            "answer_status": "unsupported",
            "reason": "No source",
            "source_ids": [],
            "memory_ids": [],
            "safety_flags": [],
        }
    )

    assert suggestion.answer_status == "unsupported"
    assert suggestion.suggested_value is None


def test_memory_hit_has_required_fields() -> None:
    """Verify MemoryHit stores profile key and source evidence."""

    hit = MemoryHit(
        memory_id="mem-1",
        profile_key="company_name",
        matched_value="Acme Corp",
        source_label="Previous vendor onboarding",
        match_score=0.88,
        stale=False,
    )

    assert hit.memory_id == "mem-1"
    assert hit.profile_key == "company_name"
    assert hit.match_score == 0.88
    assert hit.stale is False


def test_policy_source_hit_has_required_fields() -> None:
    """Verify PolicySourceHit stores document and section metadata."""

    hit = PolicySourceHit(
        source_id="src-1",
        document_name="security-policy.md",
        matched_section="Data Handling",
        match_score=0.92,
        excerpt="Sensitive data must be encrypted at rest.",
        needs_review=False,
    )

    assert hit.source_id == "src-1"
    assert hit.document_name == "security-policy.md"
    assert hit.matched_section == "Data Handling"
    assert hit.needs_review is False
