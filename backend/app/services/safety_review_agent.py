"""Safety Review Agent - Checks for sensitive data handling and security concerns.

This agent analyzes form fields and mappings to identify potential security issues.

Blocked Tokens:
    password, otp, payment, card, billing, delete, purchase, submit -> BLOCK
    consent, terms, privacy -> REVIEW_REQUIRED

The agent never weakens existing backend safety rules.
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

BLOCKED_TOKENS = {
    "password", "otp", "payment", "card", "billing", "delete", "purchase", "submit"
}

REVIEW_REQUIRED_TOKENS = {
    "consent", "terms", "privacy"
}

ISSUE_TYPES = {
    "BLOCKED_FIELD": "BLOCKED_FIELD",
    "REVIEW_REQUIRED_FIELD": "REVIEW_REQUIRED_FIELD",
}


def run_safety_review(db: Session, task: Task, review_input: dict) -> dict:
    """Run safety review and return a structured decision.

    Agent Input:
        - Extracted fields
        - Mapped values metadata
        - Field labels, types, selectors, options

    Rules:
        - Payment/delete/purchase/submit fields produce BLOCK
        - Password/OTP fields produce BLOCK
        - Consent/terms/privacy fields produce REVIEW_REQUIRED
        - Normal profile fields produce PASS

    Agent Output JSON:
        {
            "decision": "BLOCK",
            "summary": "Security risks detected.",
            "items": [
                {
                    "field_id": 1,
                    "issue": "BLOCKED_FIELD",
                    "message": "Password field detected."
                }
            ]
        }
    """

    items = []
    fields = review_input.get("form_fields", [])
    has_blocked_field = False

    for field in fields:
        field_id = field.get("id")
        field_type = (field.get("field_type") or "").lower()
        label = (field.get("label") or "").lower()
        name = (field.get("name") or "").lower()
        placeholder = (field.get("placeholder") or "").lower()
        selector = (field.get("selector") or "").lower()

        display_label = field.get("label") or field.get("name") or field.get("selector", "unknown field")
        all_text = " ".join([label, name, placeholder, selector])

        field_has_blocked_token = False
        for token in BLOCKED_TOKENS:
            if token in all_text or token in field_type:
                items.append({
                    "field_id": field_id,
                    "issue": ISSUE_TYPES["BLOCKED_FIELD"],
                    "message": f"Blocked field detected: '{display_label}' contains sensitive token '{token}'.",
                    "token": token,
                })
                field_has_blocked_token = True
                has_blocked_field = True
                break

        if not field_has_blocked_token:
            for token in REVIEW_REQUIRED_TOKENS:
                if token in all_text or token in field_type:
                    items.append({
                        "field_id": field_id,
                        "issue": ISSUE_TYPES["REVIEW_REQUIRED_FIELD"],
                        "message": f"Review required: '{display_label}' contains consent-related token '{token}'.",
                        "token": token,
                    })
                    break

    if has_blocked_field:
        decision = AGENT_DECISION_BLOCK
    elif items:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    item_count = len(items)
    if decision == AGENT_DECISION_PASS:
        summary = "No security issues detected."
    elif decision == AGENT_DECISION_BLOCK:
        summary = f"Security risks detected: {item_count} blocked field(s)."
    else:
        summary = f"Security review recommended: {item_count} field(s) need attention."

    return {
        "decision": decision,
        "summary": summary,
        "items": items,
        "role": "SAFETY_REVIEW",
        "model": None,
        "provider": None,
    }