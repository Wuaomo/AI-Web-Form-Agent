"""Tests for deterministic workflow policy decisions."""

from app.services.policy_engine import (
    evaluate_field_action,
    evaluate_memory_write,
    evaluate_submit_action,
)


def test_evaluate_field_action_blocks_password_fields() -> None:
    """Verify password-like fields are always blocked."""

    result = evaluate_field_action(
        label="Password",
        name="password",
        field_type="password",
        selector="#password",
    )

    assert result.decision == "BLOCK"
    assert result.risk_type == "PASSWORD_FIELD"


def test_evaluate_field_action_requires_review_for_low_confidence() -> None:
    """Verify low-confidence fields require human review."""

    result = evaluate_field_action(
        label="First name",
        name="first_name",
        field_type="text",
        selector="#first-name",
        confidence=0.5,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.risk_type == "LOW_CONFIDENCE_MAPPING"


def test_evaluate_memory_write_blocks_sensitive_secret_values() -> None:
    """Verify sensitive memory writes are blocked."""

    result = evaluate_memory_write(
        profile_key="custom.secret_token",
        value="api key",
        field_label="Secret token",
    )

    assert result.decision == "BLOCK"
    assert result.risk_type == "MEMORY_WRITE"


def test_evaluate_submit_action_always_requires_review() -> None:
    """Verify final submit is always approval-gated."""

    result = evaluate_submit_action()

    assert result.decision == "REVIEW_REQUIRED"
    assert result.risk_type == "SUBMIT_ACTION"
