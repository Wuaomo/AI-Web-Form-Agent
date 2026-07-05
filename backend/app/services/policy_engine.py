"""Deterministic policy evaluation for risky workflow actions."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.workflow_constants import (
    POLICY_DECISION_ALLOW,
    POLICY_DECISION_BLOCK,
    POLICY_DECISION_REVIEW_REQUIRED,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RISK_TYPE_DESTRUCTIVE_ACTION,
    RISK_TYPE_EXTERNAL_NAVIGATION,
    RISK_TYPE_LOW_CONFIDENCE_MAPPING,
    RISK_TYPE_MEMORY_WRITE,
    RISK_TYPE_OTP_FIELD,
    RISK_TYPE_PASSWORD_FIELD,
    RISK_TYPE_PAYMENT_FIELD,
    RISK_TYPE_SUBMIT_ACTION,
    RISK_TYPE_TERMS_CONSENT,
)


@dataclass(frozen=True)
class PolicyDecision:
    """A deterministic policy result for one workflow action."""

    decision: str
    risk_type: str
    risk_level: str
    reason: str


def _normalized_text(*values: str | None) -> str:
    return " ".join(str(value or "") for value in values).lower()


def evaluate_field_action(
    *,
    label: str | None,
    name: str | None,
    field_type: str | None,
    selector: str | None,
    confidence: float | None = None,
) -> PolicyDecision:
    """Evaluate whether a field can be safely filled."""

    normalized = _normalized_text(label, name, field_type, selector)

    if any(token in normalized for token in ("password", "passcode")):
        return PolicyDecision(
            decision=POLICY_DECISION_BLOCK,
            risk_type=RISK_TYPE_PASSWORD_FIELD,
            risk_level=RISK_LEVEL_HIGH,
            reason="Password-like fields are blocked by policy.",
        )
    if any(token in normalized for token in ("otp", "2fa", "one-time code", "verification code")):
        return PolicyDecision(
            decision=POLICY_DECISION_BLOCK,
            risk_type=RISK_TYPE_OTP_FIELD,
            risk_level=RISK_LEVEL_HIGH,
            reason="OTP and verification code fields are blocked by policy.",
        )
    if any(token in normalized for token in ("payment", "card", "billing", "cvv", "credit")):
        return PolicyDecision(
            decision=POLICY_DECISION_BLOCK,
            risk_type=RISK_TYPE_PAYMENT_FIELD,
            risk_level=RISK_LEVEL_HIGH,
            reason="Payment-related fields are blocked by policy.",
        )
    if any(token in normalized for token in ("delete", "remove", "purchase", "cancel subscription")):
        return PolicyDecision(
            decision=POLICY_DECISION_BLOCK,
            risk_type=RISK_TYPE_DESTRUCTIVE_ACTION,
            risk_level=RISK_LEVEL_HIGH,
            reason="Destructive actions are blocked by policy.",
        )
    if any(token in normalized for token in ("terms", "privacy", "consent", "agreement")):
        return PolicyDecision(
            decision=POLICY_DECISION_REVIEW_REQUIRED,
            risk_type=RISK_TYPE_TERMS_CONSENT,
            risk_level=RISK_LEVEL_MEDIUM,
            reason="Consent-like fields require review before execution.",
        )
    if confidence is not None and confidence < 0.75:
        return PolicyDecision(
            decision=POLICY_DECISION_REVIEW_REQUIRED,
            risk_type=RISK_TYPE_LOW_CONFIDENCE_MAPPING,
            risk_level=RISK_LEVEL_MEDIUM,
            reason="Low-confidence mappings require human review.",
        )
    return PolicyDecision(
        decision=POLICY_DECISION_ALLOW,
        risk_type="NONE",
        risk_level=RISK_LEVEL_LOW,
        reason="No elevated risk was detected for this field.",
    )


def evaluate_submit_action() -> PolicyDecision:
    """Final submission always requires approval."""

    return PolicyDecision(
        decision=POLICY_DECISION_REVIEW_REQUIRED,
        risk_type=RISK_TYPE_SUBMIT_ACTION,
        risk_level=RISK_LEVEL_HIGH,
        reason="Final submission always requires approval.",
    )


def evaluate_memory_write(*, profile_key: str, value: str, field_label: str | None) -> PolicyDecision:
    """Evaluate whether a profile memory write is safe."""

    normalized = _normalized_text(profile_key, value, field_label)

    if any(token in normalized for token in ("password", "token", "secret", "otp", "verification code", "api key")):
        return PolicyDecision(
            decision=POLICY_DECISION_BLOCK,
            risk_type=RISK_TYPE_MEMORY_WRITE,
            risk_level=RISK_LEVEL_HIGH,
            reason="Sensitive credentials must not be written to profile memory.",
        )
    if any(token in normalized for token in ("terms", "privacy", "consent", "agreement")):
        return PolicyDecision(
            decision=POLICY_DECISION_REVIEW_REQUIRED,
            risk_type=RISK_TYPE_TERMS_CONSENT,
            risk_level=RISK_LEVEL_MEDIUM,
            reason="Consent-like profile writes require review.",
        )
    return PolicyDecision(
        decision=POLICY_DECISION_ALLOW,
        risk_type=RISK_TYPE_MEMORY_WRITE,
        risk_level=RISK_LEVEL_LOW,
        reason="Profile write is low risk.",
    )


def evaluate_navigation(*, source_url: str, target_url: str) -> PolicyDecision:
    """Evaluate whether navigation stays within the same origin."""

    source = urlparse(source_url)
    target = urlparse(target_url)
    if source.scheme and target.scheme and (
        source.scheme != target.scheme or source.netloc != target.netloc
    ):
        return PolicyDecision(
            decision=POLICY_DECISION_REVIEW_REQUIRED,
            risk_type=RISK_TYPE_EXTERNAL_NAVIGATION,
            risk_level=RISK_LEVEL_MEDIUM,
            reason="Navigation to a different origin requires review.",
        )
    return PolicyDecision(
        decision=POLICY_DECISION_ALLOW,
        risk_type=RISK_TYPE_EXTERNAL_NAVIGATION,
        risk_level=RISK_LEVEL_LOW,
        reason="Navigation remains within the same origin.",
    )
