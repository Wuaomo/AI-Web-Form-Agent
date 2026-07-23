"""Read-only retriever for reviewed workflow memory.

Wraps the existing ``WorkflowMemoryItem`` table with safety filtering so
sensitive, one-time, or stale items are either excluded or flagged for
review-only use. This module never writes to the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkflowMemoryItem
from app.services.retrieval_service import _is_stale, jaccard_similarity
from app.services.suggestion_types import MemoryHit
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING

SENSITIVE_TOKENS = {
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

MAX_HITS = 5
MIN_SCORE = 0.15


def _is_sensitive_item(item: WorkflowMemoryItem) -> bool:
    """Return True if the memory item may carry sensitive data."""

    text = " ".join(
        [
            (item.field_text or "").lower(),
            (item.mapped_profile_key or "").lower(),
        ]
    )
    return any(token in text for token in SENSITIVE_TOKENS)


def retrieve_reviewed_memory(
    db: Session,
    *,
    profile_id: int,
    workflow_type: str,
    query: str,
) -> list[MemoryHit]:
    """Retrieve reviewed, non-sensitive memory hits for a query.

    Parameters
    ----------
    db:
        Active database session (read-only — no writes are performed).
    profile_id:
        Profile ID to scope the search (reserved for future per-profile
        filtering; current memory model is global).
    workflow_type:
        Workflow type to filter memory items.
    query:
        Free-text query matched against ``field_text`` and
        ``mapped_profile_key`` via token-based Jaccard similarity.

    Returns
    -------
    list[MemoryHit]
        At most ``MAX_HITS`` items, sorted by score descending. Stale
        items are included with ``stale=True`` so callers can mark them
        as review-only. Sensitive items are excluded entirely.
    """

    stmt = select(WorkflowMemoryItem).where(
        WorkflowMemoryItem.workflow_type == workflow_type,
        WorkflowMemoryItem.memory_type == MEMORY_TYPE_CONFIRMED_MAPPING,
    )
    candidates = list(db.scalars(stmt))

    results: list[MemoryHit] = []

    for item in candidates:
        if _is_sensitive_item(item):
            continue

        combined_text = " ".join(
            [item.field_text or "", item.mapped_profile_key or ""]
        )
        score = jaccard_similarity(query, combined_text)
        if score < MIN_SCORE:
            continue

        reviewed_at = item.last_used_at or item.created_at
        stale = _is_stale(reviewed_at)

        results.append(
            MemoryHit(
                memory_id=str(item.id),
                profile_key=item.mapped_profile_key,
                matched_value=None,
                source_label=item.source_domain,
                match_score=round(score, 4),
                stale=stale,
            )
        )

    results.sort(key=lambda hit: hit.match_score, reverse=True)
    return results[:MAX_HITS]
