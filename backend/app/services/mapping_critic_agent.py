"""Mapping Critic Agent - Reviews field-to-profile mappings for accuracy and completeness.

This agent analyzes form field mappings to identify potential issues such as:
- Low confidence mappings
- Missing required fields
- Incorrect profile key assignments
- Duplicate mappings
- Suspicious value mappings

The agent cannot modify mappings directly - it only provides review recommendations.
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

ISSUE_TYPES = {
    "REQUIRED_UNMAPPED": "REQUIRED_UNMAPPED",
    "LOW_CONFIDENCE": "LOW_CONFIDENCE",
    "EMPTY_MAPPED_VALUE": "EMPTY_MAPPED_VALUE",
    "DUPLICATE_KEY": "DUPLICATE_KEY",
}


def run_mapping_critic_review(db: Session, task: Task, review_input: dict) -> dict:
    """Run mapping critic review and return a structured decision.

    Agent Input:
        - Extracted fields
        - Proposed mappings
        - Required status
        - Confidence scores

    Agent Output JSON:
        {
            "decision": "REVIEW_REQUIRED",
            "summary": "Two required fields need attention.",
            "items": [
                {
                    "field_id": 1,
                    "issue": "LOW_CONFIDENCE",
                    "message": "The name field confidence is below threshold."
                }
            ]
        }
    """

    items = []
    fields = review_input.get("form_fields", [])

    for field in fields:
        field_id = field.get("id")
        label = field.get("label") or field.get("selector", "unknown field")
        required = field.get("required", False)
        mapped_key = field.get("mapped_profile_key")
        confidence = field.get("confidence")
        mapped_value = field.get("mapped_value")

        if required and not mapped_key:
            items.append({
                "field_id": field_id,
                "issue": ISSUE_TYPES["REQUIRED_UNMAPPED"],
                "message": f"Required field '{label}' is not mapped to any profile key.",
            })

        if confidence is not None and confidence < 0.75:
            items.append({
                "field_id": field_id,
                "issue": ISSUE_TYPES["LOW_CONFIDENCE"],
                "message": f"The '{label}' field confidence ({confidence:.2f}) is below threshold.",
                "confidence": confidence,
            })

        if mapped_key:
            if mapped_value is None or mapped_value == "":
                if required:
                    items.append({
                        "field_id": field_id,
                        "issue": ISSUE_TYPES["EMPTY_MAPPED_VALUE"],
                        "message": f"Required field '{label}' has an empty mapped value.",
                    })

    profile_keys_used = [f["mapped_profile_key"] for f in fields if f.get("mapped_profile_key")]
    duplicate_keys = [k for k in set(profile_keys_used) if profile_keys_used.count(k) > 1]
    if duplicate_keys:
        for key in duplicate_keys:
            fields_with_key = [f for f in fields if f.get("mapped_profile_key") == key]
            for field in fields_with_key:
                field_id = field.get("id")
                label = field.get("label") or field.get("selector", "unknown field")
                items.append({
                    "field_id": field_id,
                    "issue": ISSUE_TYPES["DUPLICATE_KEY"],
                    "message": f"Field '{label}' maps to duplicate profile key '{key}'.",
                    "duplicate_key": key,
                })

    if items:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    issue_count = len(items)
    if decision == AGENT_DECISION_PASS:
        summary = "All field mappings are valid and complete."
    else:
        summary = f"{issue_count} field(s) need attention."

    return {
        "decision": decision,
        "summary": summary,
        "items": items,
        "role": "MAPPING_CRITIC",
        "model": None,
        "provider": None,
    }