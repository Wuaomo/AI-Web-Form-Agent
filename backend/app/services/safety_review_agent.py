"""Safety Review Agent - Checks for sensitive data handling and security concerns.

This agent analyzes form fields and mappings to identify potential security issues such as:
- Sensitive field types (password, OTP, credit card)
- Potential PII exposure
- Suspicious data patterns
- Security risks in form submissions
"""

import logging

from sqlalchemy.orm import Session

from app.agent_constants import (
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
    AGENT_DECISION_BLOCK,
)
from app.models import Task

logger = logging.getLogger(__name__)

SENSITIVE_FIELD_PATTERNS = {
    "password", "passwd", "pwd", "secret", "token", "otp",
    "credit", "card", "cvv", "ssn", "bank", "account", "routing",
    "social security", "national id", "tax id", "driver license",
}

SENSITIVE_FIELD_TYPES = {"password", "creditcard", "ssn"}


def run_safety_review(db: Session, task: Task, review_input: dict) -> dict:
    """Run safety review and return a structured decision."""

    issues = []
    warnings = []
    fields = review_input.get("form_fields", [])

    for field in fields:
        field_type = (field.get("field_type") or "").lower()
        label = (field.get("label") or "").lower()
        name = (field.get("name") or "").lower()
        placeholder = (field.get("placeholder") or "").lower()
        selector = (field.get("selector") or "").lower()

        all_text = " ".join([label, name, placeholder, selector])

        for pattern in SENSITIVE_FIELD_PATTERNS:
            if pattern in all_text or pattern.replace(" ", "") in all_text:
                display_label = field.get("label") or field.get("name") or field.get("selector", "unknown field")
                if field_type in SENSITIVE_FIELD_TYPES or "password" in all_text or "credit" in all_text or "ssn" in all_text:
                    issues.append(f"Sensitive field detected: {display_label}")
                else:
                    warnings.append(f"Potentially sensitive field: {display_label}")
                break

        mapped_value = field.get("mapped_value")
        if mapped_value:
            if len(mapped_value) >= 16 and any(char.isdigit() for char in mapped_value) and any(char.isalpha() for char in mapped_value):
                if field_type == "password":
                    issues.append(f"Password value appears to be stored in profile")
                else:
                    warnings.append(f"Long complex value mapped to non-password field")

        memory_policy = field.get("profile_memory_policy", "auto")
        if memory_policy == "force_save" and any(pattern in all_text for pattern in SENSITIVE_FIELD_PATTERNS):
            issues.append(f"Sensitive field has force_save policy enabled")

    if issues:
        decision = AGENT_DECISION_BLOCK
    elif warnings:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    return {
        "decision": decision,
        "issues": issues,
        "warnings": warnings,
        "confidence": min(1.0, max(0.5, 0.95 - len(issues) * 0.15 - len(warnings) * 0.05)),
        "role": "SAFETY_REVIEW",
        "model": None,
        "provider": None,
    }