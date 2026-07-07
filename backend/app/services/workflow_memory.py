"""SQLite-backed workflow memory persistence for confirmed safe mappings."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FormField, Task, WorkflowMemoryItem
from app.services.mapping_cache import field_signature
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING, WORKFLOW_TYPE_FORM_FILL

NON_FILLABLE_FIELD_TYPES = {"button", "file", "submit", "reset", "image"}

ONE_TIME_FIELD_TOKENS = {
    "captcha",
    "otp",
    "one time",
    "verification code",
    "verify code",
    "security code",
    "passcode",
    "token",
    "code",
}

ONE_TIME_FIELD_PHRASES = {
    "one-time password",
    "two-factor",
    "2fa",
    "auth code",
    "verification code",
}

SENSITIVE_FIELD_TOKENS = {
    "password",
    "passphrase",
    "otp",
    "one time",
    "verification code",
    "token",
    "secret",
    "api key",
    "credit card",
    "card number",
    "cvv",
    "cvc",
    "ssn",
    "social security",
    "bank",
    "payment",
    "consent",
    "terms",
    "agree",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", value).lower().split())


def build_field_memory_text(field: FormField) -> str:
    """Build a normalized non-sensitive field context string."""

    label = (field.label or "").strip()
    name = (field.name or "").strip()
    placeholder = (field.placeholder or "").strip()
    field_type = (field.field_type or "").strip()
    options = field.options

    return "\n".join(
        [
            f"label: {label}",
            f"name: {name}",
            f"placeholder: {placeholder}",
            f"type: {field_type}",
            f"options: {options}",
        ]
    ).strip()


def is_fillable_field(field: FormField) -> bool:
    """Return whether this field is eligible for automated fill/memory."""

    return _normalize_text(field.field_type) not in NON_FILLABLE_FIELD_TYPES


def is_one_time_field(field: FormField) -> bool:
    """Heuristic detection for ephemeral one-time fields."""

    content = " ".join(
        [
            _normalize_text(field.label),
            _normalize_text(field.name),
            _normalize_text(field.placeholder),
            _normalize_text(field.selector),
            _normalize_text(field.field_type),
        ]
    )
    if not content:
        return False
    if any(token in content for token in ONE_TIME_FIELD_TOKENS):
        return True
    return any(phrase in content for phrase in ONE_TIME_FIELD_PHRASES)


def is_sensitive_field(field: FormField) -> bool:
    """Heuristic detection for sensitive fields that must not be stored."""

    content = " ".join(
        [
            _normalize_text(field.label),
            _normalize_text(field.name),
            _normalize_text(field.placeholder),
            _normalize_text(field.selector),
            _normalize_text(field.field_type),
            _normalize_text(field.mapped_profile_key),
        ]
    )
    if not content:
        return False
    return any(token in content for token in SENSITIVE_FIELD_TOKENS)


def is_memory_eligible_field(field: FormField) -> bool:
    """Return whether a field is eligible for workflow memory features."""

    memory_policy = (field.profile_memory_policy or "auto").strip()
    if memory_policy in {"do_not_save", "never"}:
        return False
    if not is_fillable_field(field):
        return False
    if is_one_time_field(field):
        return False
    if is_sensitive_field(field):
        return False
    return True


def should_save_mapping_memory(field: FormField) -> bool:
    """Return whether the field's confirmed mapping should be persisted."""

    if not field.mapped_profile_key:
        return False
    return is_memory_eligible_field(field)


def _source_domain(task: Task) -> str | None:
    try:
        parsed = urlparse(task.url)
    except ValueError:
        return None
    return parsed.hostname


def save_confirmed_mapping_memory(
    db: Session,
    *,
    task: Task,
    field: FormField,
) -> WorkflowMemoryItem | None:
    """Persist one confirmed mapping to workflow memory."""

    if not should_save_mapping_memory(field):
        return None

    signature = field_signature(field)
    profile_key = field.mapped_profile_key or ""
    existing = db.scalar(
        select(WorkflowMemoryItem).where(
            WorkflowMemoryItem.memory_type == MEMORY_TYPE_CONFIRMED_MAPPING,
            WorkflowMemoryItem.field_signature == signature,
            WorkflowMemoryItem.mapped_profile_key == profile_key,
        )
    )
    if existing:
        existing.success_count += 1
        existing.last_used_at = utc_now()
        db.add(existing)
        return existing

    item = WorkflowMemoryItem(
        memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
        workflow_type=task.workflow_type or WORKFLOW_TYPE_FORM_FILL,
        source_domain=_source_domain(task),
        field_signature=signature,
        field_text=build_field_memory_text(field),
        mapped_profile_key=profile_key,
        success_count=1,
        last_used_at=utc_now(),
    )
    db.add(item)
    return item


def save_confirmed_mappings_for_task(
    db: Session,
    *,
    task: Task,
    fields: list[FormField],
) -> list[WorkflowMemoryItem]:
    """Persist all eligible confirmed mappings for a task."""

    saved: list[WorkflowMemoryItem] = []
    for field in fields:
        item = save_confirmed_mapping_memory(db, task=task, field=field)
        if item is not None:
            saved.append(item)
    return saved

