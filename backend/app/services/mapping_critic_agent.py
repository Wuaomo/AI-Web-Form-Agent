"""Mapping Critic Agent - Reviews field-to-profile mappings for accuracy and completeness.

This agent analyzes form field mappings to identify potential issues such as:
- Low confidence mappings
- Missing required fields
- Incorrect profile key assignments
- Duplicate mappings
- Suspicious value mappings
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


def run_mapping_critic_review(db: Session, task: Task, review_input: dict) -> dict:
    """Run mapping critic review and return a structured decision."""

    issues = []
    warnings = []
    items = []
    fields = review_input.get("form_fields", [])

    required_fields = [f for f in fields if f.get("required")]
    mapped_required_fields = [f for f in required_fields if f.get("mapped_profile_key")]
    
    if len(mapped_required_fields) < len(required_fields):
        missing_count = len(required_fields) - len(mapped_required_fields)
        issue_text = f"{missing_count} required field(s) not mapped"
        issues.append(issue_text)
        items.append({"type": "issue", "message": issue_text})

    for field in fields:
        confidence = field.get("confidence")
        if confidence is not None and confidence < 0.75:
            label = field.get("label") or field.get("selector", "unknown field")
            warning_text = f"Low confidence mapping ({confidence:.2f}) for: {label}"
            warnings.append(warning_text)
            items.append({"type": "warning", "message": warning_text, "field_label": label, "confidence": confidence})

        mapped_key = field.get("mapped_profile_key")
        if mapped_key:
            mapped_value = field.get("mapped_value")
            if mapped_value is None or mapped_value == "":
                label = field.get("label") or field.get("selector", "unknown field")
                if field.get("required"):
                    issue_text = f"Required field has empty mapped value: {label}"
                    issues.append(issue_text)
                    items.append({"type": "issue", "message": issue_text, "field_label": label})
                else:
                    warning_text = f"Optional field has empty mapped value: {label}"
                    warnings.append(warning_text)
                    items.append({"type": "warning", "message": warning_text, "field_label": label})

    profile_keys_used = [f["mapped_profile_key"] for f in fields if f.get("mapped_profile_key")]
    duplicate_keys = [k for k in set(profile_keys_used) if profile_keys_used.count(k) > 1]
    if duplicate_keys:
        issue_text = f"Duplicate profile key mappings: {', '.join(duplicate_keys)}"
        issues.append(issue_text)
        items.append({"type": "issue", "message": issue_text, "duplicate_keys": duplicate_keys})

    if issues:
        decision = AGENT_DECISION_BLOCK if any("required" in issue.lower() for issue in issues) else AGENT_DECISION_REVIEW_REQUIRED
    elif warnings:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    confidence_score = min(1.0, max(0.5, 0.95 - len(issues) * 0.1 - len(warnings) * 0.05))

    if decision == AGENT_DECISION_PASS:
        summary = "All field mappings are valid and complete"
    elif decision == AGENT_DECISION_BLOCK:
        summary = f"Critical mapping issues detected: {len(issues)} issues"
    else:
        summary = f"Mapping review recommended: {len(warnings)} warnings"

    return {
        "decision": decision,
        "summary": summary,
        "items": items,
        "issues": issues,
        "warnings": warnings,
        "confidence": confidence_score,
        "role": "MAPPING_CRITIC",
        "model": None,
        "provider": None,
    }