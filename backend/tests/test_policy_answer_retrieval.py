"""Tests for source-backed policy answer suggestions."""

from pathlib import Path

from app.services.policy_answer_retrieval import suggest_policy_answer


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
