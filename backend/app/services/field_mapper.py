"""Rule-based mapping from extracted form fields to profile values."""

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import FormField, Task

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": (
        "full name",
        "fullname",
        "your name",
        "applicant name",
        "candidate name",
        "contact name",
        "name",
    ),
    "email": ("email address", "e mail", "email"),
    "university": (
        "university",
        "college",
        "school",
        "institution",
        "alma mater",
    ),
    "major": (
        "field of study",
        "area of study",
        "degree major",
        "major",
        "specialization",
        "specialisation",
    ),
    "phone": (
        "phone number",
        "mobile number",
        "telephone number",
        "cell number",
        "phone",
        "mobile",
        "telephone",
        "tel",
    ),
    "linkedin": ("linkedin profile", "linkedin url", "linkedin"),
    "github": ("github profile", "github url", "github"),
    "self_intro": (
        "self introduction",
        "self intro",
        "personal introduction",
        "personal statement",
        "about yourself",
        "about you",
        "biography",
        "introduction",
        "bio",
    ),
}

TYPE_MATCHES = {
    "email": "email",
    "tel": "phone",
    "telephone": "phone",
}


def _normalize(value: str | None) -> str:
    """Turn labels and selectors into comparable lowercase words."""

    if not value:
        return ""
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", value).lower().split())


def _source_scores(field: FormField) -> Iterable[tuple[str, float]]:
    """Yield normalized field metadata with a reliability score."""

    sources = (
        (field.label, 0.98),
        (field.placeholder, 0.94),
        (field.selector, 0.90),
    )
    for value, score in sources:
        normalized = _normalize(value)
        if normalized:
            yield normalized, score


def _alias_score(text: str, alias: str, base_score: float) -> float | None:
    """Score one alias while treating the generic word 'name' cautiously."""

    if text == alias:
        return base_score
    if alias == "name":
        return None
    if f" {alias} " in f" {text} ":
        return max(base_score - 0.06, 0.0)
    return None


def _match_profile_key(field: FormField) -> tuple[str, float] | None:
    """Return the best profile key and confidence for one form field."""

    normalized_type = _normalize(field.field_type)
    if normalized_type in TYPE_MATCHES:
        return TYPE_MATCHES[normalized_type], 0.99

    best_match: tuple[str, float] | None = None
    for text, base_score in _source_scores(field):
        for profile_key, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                score = _alias_score(text, alias, base_score)
                if score is None:
                    continue
                if best_match is None or score > best_match[1]:
                    best_match = (profile_key, score)

    return best_match


def _map_fields(task_id: int, db: Session) -> list[FormField]:
    """Apply mapping rules using an existing database session."""

    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task_id)
            .order_by(FormField.id)
        )
    )

    for field in fields:
        match = _match_profile_key(field)
        if match is None:
            field.mapped_profile_key = None
            field.mapped_value = None
            field.confidence = None
            continue

        profile_key, confidence = match
        profile_value = getattr(task.profile, profile_key)
        if profile_value is None or profile_value == "":
            field.mapped_profile_key = None
            field.mapped_value = None
            field.confidence = None
            continue

        field.mapped_profile_key = profile_key
        field.mapped_value = profile_value
        field.confidence = confidence

    db.commit()
    return fields


def map_fields_by_rules(
    task_id: int,
    db: Session | None = None,
) -> list[FormField]:
    """Map and save all extracted fields for a task without using an LLM."""

    if db is not None:
        return _map_fields(task_id, db)

    with SessionLocal() as session:
        fields = _map_fields(task_id, session)
        for field in fields:
            session.expunge(field)
        return fields
