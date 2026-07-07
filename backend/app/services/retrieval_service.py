"""Lexical retrieval utilities for workflow memory items."""

from __future__ import annotations

import re

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
        results.append(
            {
                "mapped_profile_key": item.mapped_profile_key,
                "field_text": item.field_text,
                "score": round(score, 4),
                "source_domain": item.source_domain,
                "success_count": item.success_count,
            }
        )

    results.sort(key=lambda entry: float(entry["score"]), reverse=True)
    return results[: max(0, int(limit))]
