"""Execution Verification Agent - Validates that form filling was executed correctly.

This agent analyzes verification results and task state to verify:
- Field values were correctly filled
- Verification results are consistent
- No unexpected errors occurred
- Form state matches expected outcomes
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


def run_execution_verification_review(db: Session, task: Task, review_input: dict) -> dict:
    """Run execution verification review and return a structured decision."""

    issues = []
    warnings = []
    items = []

    verification_results = (
        db.query(FieldVerificationResult)
        .filter(FieldVerificationResult.task_id == task.id)
        .all()
    )

    if not verification_results:
        warning_text = "No verification results found for this task"
        warnings.append(warning_text)
        items.append({"type": "warning", "message": warning_text})

    failed_results = [r for r in verification_results if r.status == VERIFICATION_STATUS_FAILED]
    verified_results = [r for r in verification_results if r.status == VERIFICATION_STATUS_VERIFIED]
    skipped_results = [r for r in verification_results if r.status == VERIFICATION_STATUS_SKIPPED]

    if failed_results:
        for result in failed_results:
            issue_text = f"Field verification failed: selector={result.selector}, reason={result.reason}"
            issues.append(issue_text)
            items.append({"type": "issue", "message": issue_text, "selector": result.selector, "reason": result.reason})

    if skipped_results:
        for result in skipped_results:
            if result.reason == "SENSITIVE_FIELD_SKIPPED":
                warning_text = f"Sensitive field skipped: selector={result.selector}"
                warnings.append(warning_text)
                items.append({"type": "warning", "message": warning_text, "selector": result.selector, "reason": result.reason})
            else:
                warning_text = f"Field verification skipped: selector={result.selector}, reason={result.reason}"
                warnings.append(warning_text)
                items.append({"type": "warning", "message": warning_text, "selector": result.selector, "reason": result.reason})

    fields = review_input.get("form_fields", [])
    fillable_fields = [f for f in fields if f.get("field_type") not in {"button", "file", "submit", "reset", "image"}]
    mapped_fields = [f for f in fillable_fields if f.get("mapped_profile_key")]

    if verification_results and len(verified_results) < len(mapped_fields):
        missing_verification = len(mapped_fields) - len(verified_results)
        warning_text = f"{missing_verification} mapped field(s) not verified"
        warnings.append(warning_text)
        items.append({"type": "warning", "message": warning_text, "missing_count": missing_verification})

    if issues:
        decision = AGENT_DECISION_BLOCK
    elif warnings:
        decision = AGENT_DECISION_REVIEW_REQUIRED
    else:
        decision = AGENT_DECISION_PASS

    verification_count = len(verification_results)
    verified_count = len(verified_results)
    confidence_score = 0.5 if verification_count == 0 else min(1.0, verified_count / max(1, verification_count))

    if decision == AGENT_DECISION_PASS:
        summary = f"All {verified_count} fields verified successfully"
    elif decision == AGENT_DECISION_BLOCK:
        summary = f"Verification failed: {len(failed_results)} field(s) failed"
    else:
        summary = f"Verification review recommended: {len(warnings)} warnings"

    return {
        "decision": decision,
        "summary": summary,
        "items": items,
        "issues": issues,
        "warnings": warnings,
        "confidence": confidence_score,
        "verification_summary": {
            "total": verification_count,
            "verified": verified_count,
            "failed": len(failed_results),
            "skipped": len(skipped_results),
        },
        "role": "EXECUTION_VERIFICATION",
        "model": None,
        "provider": None,
    }