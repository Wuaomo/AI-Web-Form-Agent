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
    fields = review_input.get("form_fields", [])

    required_fields = [f for f in fields if f.get("required")]
    mapped_required_fields = [f for f in required_fields if f.get("mapped_profile_key")]
    
    if len(mapped_required_fields) < len(required_fields):
        missing_count = len(required_fields) - len(mapped_required_fields)
        issues.append(f"{missing_count} required field(s) not mapped")

    for field in fields:
        confidence = field.get("confidence")
        if confidence is not None and confidence < 0.75:
            label = field.get("label") or field.get("selector", "unknown field")
            warnings.append(f"Low confidence mapping ({confidence:.2f}) for: {label}")

        mapped_key = field.get("mapped_profile_key")
        if mapped_key:
            mapped_value = field.get("mapped_value")
            if mapped_value is None or mapped_value == "":
                label = field.get("label") or field.get("selector", "unknown field")
                if field.get("required"):
                    issues.append(f"Required field has empty mapped value: {label}")
                else:
                    warnings.append(f"Optional field has empty mapped value: {label}")

    profile_keys_used = [f["mapped_profile_key"] for f in fields if f.get("mapped_profile_key")]
    duplicate_keys = [k for k in set(profile_keys_used) if profile_keys_used.count(k) > 1]
    if duplicate_keys:
        issues.append(f"Duplicate profile key mappings: {', '.join(duplicate_keys)}")

    if issues:
        decision = AGENT_DECISION_BLOCK if any("required" in issue.lower() for issue in issues) else AGENT_DECISION_REVIEW_REQUIRED
    elif warnings:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    return {
        "decision": decision,
        "issues": issues,
        "warnings": warnings,
        "confidence": min(1.0, max(0.5, 0.95 - len(issues) * 0.1 - len(warnings) * 0.05)),
        "role": "MAPPING_CRITIC",
        "model": None,
        "provider": None,
    }