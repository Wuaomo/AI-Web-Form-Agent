"""Lexical retrieval utilities for workflow memory items."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkflowMemoryItem
from app.workflow_constants import (
    MEMORY_TYPE_CONFIRMED_MAPPING,
    WORKFLOW_TYPE_FORM_FILL,
)


STOP_TOKENS = {
    "label",
    "name",
    "placeholder",
    "type",
    "options",
    "required",
    "selector",
    "html",
    "id",
    "form",
    "section",
}

MEMORY_STALE_AFTER_DAYS = 90


def tokenize(text: str) -> set[str]:
    """Tokenize a free-form string into normalized words."""

    if not text:
        return set()
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return {token for token in tokens if token not in STOP_TOKENS}


def jaccard_similarity(a: str, b: str) -> float:
    """Return token-based Jaccard similarity between two strings."""

    tokens_a = tokenize(a)
    tokens_b = tokenize(b)
    if not tokens_a and not tokens_b:
        return 0.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _as_aware_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value) -> str | None:
    timestamp = _as_aware_utc(value)
    return timestamp.isoformat() if timestamp else None


def _is_stale(value) -> bool:
    timestamp = _as_aware_utc(value)
    if timestamp is None:
        return False
    age_days = (datetime.now(timezone.utc) - timestamp).days
    return age_days > MEMORY_STALE_AFTER_DAYS


def search_similar_field_mappings(
    db: Session,
    *,
    field_text: str,
    workflow_type: str = WORKFLOW_TYPE_FORM_FILL,
    source_domain: str | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    """Return best matching memory items for one field text query."""

    query = select(WorkflowMemoryItem).where(
        WorkflowMemoryItem.workflow_type == workflow_type,
        WorkflowMemoryItem.memory_type == MEMORY_TYPE_CONFIRMED_MAPPING,
    )
    candidates = list(db.scalars(query))
    results: list[dict[str, object]] = []

    for item in candidates:
        base_score = jaccard_similarity(field_text, item.field_text)
        score = base_score
        if source_domain and item.source_domain and item.source_domain == source_domain:
            score += 0.1
        score += min(0.1, float(item.success_count) * 0.01)
        if score < 0.15:
            continue
        reviewed_at = item.last_used_at or item.created_at
        stale = _is_stale(reviewed_at)
        results.append(
            {
                "mapped_profile_key": item.mapped_profile_key,
                "field_text": item.field_text,
                "score": round(score, 4),
                "source_domain": item.source_domain,
                "success_count": item.success_count,
                "source_type": "reviewed_memory",
                "source_id": item.id,
                "reviewed_at": _isoformat(item.created_at),
                "last_used_at": _isoformat(item.last_used_at),
                "stale": stale,
                "governance_status": (
                    "stale_review_recommended" if stale else "reviewed"
                ),
            }
        )

    results.sort(key=lambda entry: float(entry["score"]), reverse=True)
    return results[: max(0, int(limit))]
