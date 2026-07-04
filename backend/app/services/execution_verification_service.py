"""Post-fill verification logic for form automation."""

import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    FormField,
    FieldVerificationResult,
    VERIFICATION_STATUS_VERIFIED,
    VERIFICATION_STATUS_PARTIAL,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_SKIPPED,
    VERIFICATION_REASON_VALUE_MISMATCH,
    VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED,
)

SENSITIVE_FIELD_PATTERNS = {"password", "passwd", "pwd", "secret", "token", "otp", "credit", "card", "cvv", "ssn", "bank", "account"}


def hash_verification_value(value: str | None) -> str | None:
    """Return a stable hash for a field value."""

    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compare_field_value(expected: str | None, actual: str | None) -> tuple[str, str | None]:
    """Return verification status and reason."""

    if expected is None or expected == "":
        return VERIFICATION_STATUS_SKIPPED, None

    if expected == actual:
        return VERIFICATION_STATUS_VERIFIED, None

    return VERIFICATION_STATUS_FAILED, VERIFICATION_REASON_VALUE_MISMATCH


def should_skip_verification(field: FormField) -> bool:
    """Return whether a field should be skipped for safety or type reasons."""

    field_type = (field.field_type or "").lower()
    if field_type in {"file", "button", "submit", "reset", "image"}:
        return True

    label_lower = (field.label or "").lower()
    name_lower = (field.name or "").lower()
    placeholder_lower = (field.placeholder or "").lower()

    for pattern in SENSITIVE_FIELD_PATTERNS:
        if pattern in label_lower or pattern in name_lower or pattern in placeholder_lower:
            return True

    if field_type == "password":
        return True

    return False


def save_verification_result(
    db: Session,
    task_id: int,
    field_id: int | None,
    selector: str,
    expected_value: str | None,
    actual_value: str | None,
    status: str,
    reason: str | None = None,
    message: str | None = None,
) -> FieldVerificationResult:
    """Persist a verification result to the database."""

    result = FieldVerificationResult(
        task_id=task_id,
        field_id=field_id,
        selector=selector,
        expected_value_hash=hash_verification_value(expected_value),
        actual_value_hash=hash_verification_value(actual_value),
        status=status,
        reason=reason,
        message=message,
    )
    db.add(result)
    db.flush()
    return result


def get_verification_results_for_task(db: Session, task_id: int) -> list[FieldVerificationResult]:
    """Return all verification results for a task."""

    return (
        db.query(FieldVerificationResult)
        .filter(FieldVerificationResult.task_id == task_id)
        .order_by(FieldVerificationResult.created_at)
        .all()
    )


def get_verification_summary_for_task(db: Session, task_id: int) -> dict[str, int]:
    """Return counts of verification statuses for a task."""

    results = get_verification_results_for_task(db, task_id)
    summary = {
        VERIFICATION_STATUS_VERIFIED: 0,
        VERIFICATION_STATUS_PARTIAL: 0,
        VERIFICATION_STATUS_FAILED: 0,
        VERIFICATION_STATUS_SKIPPED: 0,
    }
    for result in results:
        if result.status in summary:
            summary[result.status] += 1
    return summary