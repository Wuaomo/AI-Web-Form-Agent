"""User-managed knowledge sources for retrieval-backed suggestions."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import KnowledgeChunk, KnowledgeSource
from app.schemas import KnowledgeSourceCreate, KnowledgeSourceResponse
from app.services.policy_answer_retrieval import _sections

router = APIRouter(prefix="/knowledge-sources", tags=["knowledge_sources"])

SUPPORTED_SUFFIXES = {".md", ".txt"}
MAX_CONTENT_CHARS = 200_000


def _title_from_content(filename: str, content: str) -> str:
    for line in content.splitlines():
        heading = re.match(r"^#\s+(.+)$", line.strip())
        if heading:
            return heading.group(1).strip()[:300]
    return Path(filename).stem[:300] or "Knowledge source"


def _chunks_from_content(content: str) -> list[tuple[str, str]]:
    sections = [
        (title.strip(), body.strip())
        for title, body in _sections(content)
        if title.strip() and body.strip()
    ]
    if sections:
        return sections
    cleaned = content.strip()
    return [("Document", cleaned)] if cleaned else []


def _to_response(source: KnowledgeSource, chunk_count: int | None = None) -> KnowledgeSourceResponse:
    return KnowledgeSourceResponse(
        id=source.id,
        title=source.title,
        filename=source.filename,
        content_type=source.content_type,
        chunk_count=chunk_count if chunk_count is not None else len(source.chunks),
        created_at=source.created_at,
    )


@router.get("", response_model=list[KnowledgeSourceResponse])
def list_knowledge_sources(db: Session = Depends(get_db)) -> list[KnowledgeSourceResponse]:
    """Return uploaded knowledge sources in newest-first order."""

    rows = (
        db.query(KnowledgeSource, func.count(KnowledgeChunk.id))
        .outerjoin(KnowledgeChunk)
        .group_by(KnowledgeSource.id)
        .order_by(KnowledgeSource.created_at.desc(), KnowledgeSource.id.desc())
        .all()
    )
    return [_to_response(source, chunk_count) for source, chunk_count in rows]


@router.post(
    "",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_source(
    payload: KnowledgeSourceCreate,
    db: Session = Depends(get_db),
) -> KnowledgeSourceResponse:
    """Store a browser-selected text or markdown file for retrieval."""

    suffix = Path(payload.filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .md and .txt knowledge sources are supported.",
        )
    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Knowledge source content cannot be empty.",
        )
    if len(content) > MAX_CONTENT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Knowledge source is too large for the local demo.",
        )

    chunks = _chunks_from_content(content)
    source = KnowledgeSource(
        title=_title_from_content(payload.filename, content),
        filename=Path(payload.filename).name,
        content_type="text/markdown" if suffix == ".md" else "text/plain",
    )
    source.chunks = [
        KnowledgeChunk(section_title=section_title, text=body)
        for section_title, body in chunks
    ]
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_response(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_source(source_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a knowledge source and its searchable chunks."""

    source = db.get(KnowledgeSource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found.",
        )
    db.delete(source)
    db.commit()
