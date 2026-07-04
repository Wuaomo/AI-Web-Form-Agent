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
    items = []
    fields = review_input.get("form_fields", [])

    for field in fields:
        field_type = (field.get("field_type") or "").lower()
        label = (field.get("label") or "").lower()
        name = (field.get("name") or "").lower()
        placeholder = (field.get("placeholder") or "").lower()
        selector = (field.get("selector") or "").lower()

        all_text = " ".join([label, name, placeholder, selector])
        display_label = field.get("label") or field.get("name") or field.get("selector", "unknown field")

        for pattern in SENSITIVE_FIELD_PATTERNS:
            if pattern in all_text or pattern.replace(" ", "") in all_text:
                if field_type in SENSITIVE_FIELD_TYPES or "password" in all_text or "credit" in all_text or "ssn" in all_text:
                    issue_text = f"Sensitive field detected: {display_label}"
                    issues.append(issue_text)
                    items.append({"type": "issue", "message": issue_text, "field_label": display_label, "pattern": pattern})
                else:
                    warning_text = f"Potentially sensitive field: {display_label}"
                    warnings.append(warning_text)
                    items.append({"type": "warning", "message": warning_text, "field_label": display_label, "pattern": pattern})
                break

        mapped_value = field.get("mapped_value")
        if mapped_value:
            if len(mapped_value) >= 16 and any(char.isdigit() for char in mapped_value) and any(char.isalpha() for char in mapped_value):
                if field_type == "password":
                    issue_text = f"Password value appears to be stored in profile"
                    issues.append(issue_text)
                    items.append({"type": "issue", "message": issue_text, "field_label": display_label})
                else:
                    warning_text = f"Long complex value mapped to non-password field"
                    warnings.append(warning_text)
                    items.append({"type": "warning", "message": warning_text, "field_label": display_label})

        memory_policy = field.get("profile_memory_policy", "auto")
        if memory_policy == "force_save" and any(pattern in all_text for pattern in SENSITIVE_FIELD_PATTERNS):
            issue_text = f"Sensitive field has force_save policy enabled"
            issues.append(issue_text)
            items.append({"type": "issue", "message": issue_text, "field_label": display_label, "policy": memory_policy})

    if issues:
        decision = AGENT_DECISION_BLOCK
    elif warnings:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    confidence_score = min(1.0, max(0.5, 0.95 - len(issues) * 0.15 - len(warnings) * 0.05))

    if decision == AGENT_DECISION_PASS:
        summary = "No security issues detected"
    elif decision == AGENT_DECISION_BLOCK:
        summary = f"Security risks detected: {len(issues)} critical issues"
    else:
        summary = f"Security review recommended: {len(warnings)} warnings"

    return {
        "decision": decision,
        "summary": summary,
        "items": items,
        "issues": issues,
        "warnings": warnings,
        "confidence": confidence_score,
        "role": "SAFETY_REVIEW",
        "model": None,
        "provider": None,
    }