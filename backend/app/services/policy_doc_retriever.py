"""Local policy document retriever for source-evidence workflows.

Reads markdown fixtures from disk and returns ranked ``PolicySourceHit``
objects. No LLM, no embeddings, no API keys — pure token-overlap scoring.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.database import BACKEND_DIR
from app.services.policy_answer_retrieval import _sections
from app.services.retrieval_service import jaccard_similarity
from app.services.suggestion_types import PolicySourceHit

DEFAULT_POLICY_PATHS = [
    BACKEND_DIR / "examples" / "mock-security-policy.md",
]


def _document_id(path: Path) -> str:
    """Build a stable document identifier from a file path."""

    digest = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:12]
    return f"doc-{digest}"


def _source_id(document_id: str, section_title: str) -> str:
    """Build a stable source identifier from document + section."""

    raw = f"{document_id}::{section_title}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"src-{digest}"


def _snippet_from_body(body: str, max_chars: int = 240) -> str:
    """Extract a clean, readable snippet from a section body."""

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    text = " ".join(lines)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _document_title(path: Path) -> str:
    """Derive a human-readable title from the markdown file."""

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return path.stem

    for line in content.splitlines():
        heading = re.match(r"^#\s+(.+)$", line.strip())
        if heading:
            return heading.group(1).strip()
    return path.stem


def retrieve_policy_sources(
    query: str,
    *,
    limit: int = 3,
    policy_paths: list[Path] | None = None,
) -> list[PolicySourceHit]:
    """Retrieve ranked policy source hits for a query.

    Parameters
    ----------
    query:
        Free-text query (a question, field label, or keyword phrase).
    limit:
        Maximum number of hits to return (default 3).
    policy_paths:
        Markdown files to search. Defaults to the bundled
        ``mock-security-policy.md`` fixture.

    Returns
    -------
    list[PolicySourceHit]
        Hits sorted by score descending. Empty list when nothing matches.
    """

    hits: list[PolicySourceHit] = []

    for path in policy_paths or DEFAULT_POLICY_PATHS:
        if not path.exists():
            continue

        doc_id = _document_id(path)
        title = _document_title(path)

        for section_title, body in _sections(path.read_text(encoding="utf-8")):
            score = jaccard_similarity(query, f"{section_title}\n{body}")
            if score < 0.15:
                continue

            hits.append(
                PolicySourceHit(
                    source_id=_source_id(doc_id, section_title),
                    document_id=doc_id,
                    title=title,
                    section=section_title,
                    snippet=_snippet_from_body(body),
                    score=round(score, 4),
                )
            )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]
