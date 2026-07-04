"""Execution Verification Agent - Validates that form filling was executed correctly.

This agent analyzes verification results and task state to verify:
- Field values were correctly filled
- Verification results are consistent
- No unexpected errors occurred
- Form state matches expected outcomes

Input:
    - Verification results from Phase 5
    - Screenshot metadata
    - Action logs

Output:
    - PASS when all required fields verified
    - REVIEW_REQUIRED when optional fields fail
    - BLOCK when required fields fail or page navigated unexpectedly
"""

import logging

from sqlalchemy.orm import Session

from app.agent_constants import (
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
    AGENT_DECISION_BLOCK,
)
from app.models import Task, FieldVerificationResult
from app.models import (
    VERIFICATION_STATUS_VERIFIED,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_SKIPPED,
)

logger = logging.getLogger(__name__)

ISSUE_TYPES = {
    "REQUIRED_FIELD_FAILED": "REQUIRED_FIELD_FAILED",
    "OPTIONAL_FIELD_FAILED": "OPTIONAL_FIELD_FAILED",
    "UNEXPECTED_NAVIGATION": "UNEXPECTED_NAVIGATION",
    "MISSING_VERIFICATION": "MISSING_VERIFICATION",
    "SENSITIVE_FIELD_SKIPPED": "SENSITIVE_FIELD_SKIPPED",
}


def run_execution_verification_review(db: Session, task: Task, review_input: dict) -> dict:
    """Run execution verification review and return a structured decision.

    Rules:
        - PASS when all required fields verified
        - REVIEW_REQUIRED when optional fields fail
        - BLOCK when required fields fail or page navigated unexpectedly
    """

    items = []
    required_fields_failed = False
    unexpected_navigation = False

    verification_results = (
        db.query(FieldVerificationResult)
        .filter(FieldVerificationResult.task_id == task.id)
        .all()
    )

    fields = review_input.get("form_fields", [])
    field_map = {f.get("selector"): f for f in fields}

    failed_results = [r for r in verification_results if r.status == VERIFICATION_STATUS_FAILED]
    verified_results = [r for r in verification_results if r.status == VERIFICATION_STATUS_VERIFIED]
    skipped_results = [r for r in verification_results if r.status == VERIFICATION_STATUS_SKIPPED]

    for result in failed_results:
        field_info = field_map.get(result.selector)
        field_label = field_info.get("label") if field_info else result.selector
        field_required = field_info.get("required", False) if field_info else False

        if field_required:
            required_fields_failed = True
            items.append({
                "field_id": field_info.get("id") if field_info else None,
                "selector": result.selector,
                "issue": ISSUE_TYPES["REQUIRED_FIELD_FAILED"],
                "message": f"Required field '{field_label}' verification failed: {result.reason}",
                "reason": result.reason,
            })
        else:
            items.append({
                "field_id": field_info.get("id") if field_info else None,
                "selector": result.selector,
                "issue": ISSUE_TYPES["OPTIONAL_FIELD_FAILED"],
                "message": f"Optional field '{field_label}' verification failed: {result.reason}",
                "reason": result.reason,
            })

    for result in skipped_results:
        if result.reason == "SENSITIVE_FIELD_SKIPPED":
            field_info = field_map.get(result.selector)
            field_label = field_info.get("label") if field_info else result.selector
            items.append({
                "field_id": field_info.get("id") if field_info else None,
                "selector": result.selector,
                "issue": ISSUE_TYPES["SENSITIVE_FIELD_SKIPPED"],
                "message": f"Sensitive field '{field_label}' was skipped for security.",
                "reason": result.reason,
            })

    for result in failed_results:
        if result.reason == "PAGE_NAVIGATED_UNEXPECTEDLY":
            unexpected_navigation = True
            items.append({
                "field_id": None,
                "selector": result.selector,
                "issue": ISSUE_TYPES["UNEXPECTED_NAVIGATION"],
                "message": "Page navigated unexpectedly during verification.",
                "reason": result.reason,
            })

    fillable_fields = [f for f in fields if f.get("field_type") not in {"button", "file", "submit", "reset", "image"}]
    mapped_fields = [f for f in fillable_fields if f.get("mapped_profile_key")]

    if mapped_fields and len(verification_results) < len(mapped_fields):
        missing_verification = len(mapped_fields) - len(verification_results)
        items.append({
            "field_id": None,
            "selector": None,
            "issue": ISSUE_TYPES["MISSING_VERIFICATION"],
            "message": f"{missing_verification} mapped field(s) were not verified.",
            "missing_count": missing_verification,
        })

    if required_fields_failed or unexpected_navigation:
        decision = AGENT_DECISION_BLOCK
    elif items:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    verification_count = len(verification_results)
    verified_count = len(verified_results)
    confidence_score = 0.5 if verification_count == 0 else min(1.0, verified_count / max(1, verification_count))

    if decision == AGENT_DECISION_PASS:
        summary = f"All {verified_count} required fields verified successfully."
    elif decision == AGENT_DECISION_BLOCK:
        if unexpected_navigation:
            summary = "Blocked: Page navigated unexpectedly during verification."
        else:
            summary = f"Blocked: {sum(1 for i in items if i.get('issue') == 'REQUIRED_FIELD_FAILED')} required field(s) failed verification."
    else:
        summary = f"Review required: {len(items)} verification issues detected."

    return {
        "decision": decision,
        "summary": summary,
        "items": items,
        "role": "EXECUTION_VERIFICATION",
        "model": None,
        "provider": None,
    }