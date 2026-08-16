"""Tests for user-managed knowledge sources."""

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import KnowledgeChunk, KnowledgeSource
from app.routers.knowledge_sources import router as knowledge_sources_router
from app.services.policy_doc_retriever import retrieve_policy_sources


def build_environment() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app = FastAPI()
    app.include_router(knowledge_sources_router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def test_upload_lists_and_retrieves_knowledge_source() -> None:
    client, session = build_environment()

    response = client.post(
        "/knowledge-sources",
        json={
            "filename": "security-policy.md",
            "content": (
                "# Security Policy\n\n"
                "## Multi-factor authentication\n"
                "Answer: Yes. Multi-factor authentication is required for all admin users.\n"
            ),
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Security Policy"
    assert created["chunk_count"] == 1

    list_response = client.get("/knowledge-sources")
    assert list_response.status_code == 200
    assert list_response.json()[0]["filename"] == "security-policy.md"

    hits = retrieve_policy_sources(
        "multi factor authentication required admin users",
        db=session,
        limit=5,
    )
    uploaded_hit = next(hit for hit in hits if hit.document_id.startswith("knowledge-"))
    assert uploaded_hit.title == "Security Policy"
    assert uploaded_hit.section == "Multi-factor authentication"

    session.close()


def test_delete_knowledge_source_removes_chunks() -> None:
    client, session = build_environment()
    create_response = client.post(
        "/knowledge-sources",
        json={
            "filename": "faq.txt",
            "content": "Security questionnaire answer guide.",
        },
    )
    source_id = create_response.json()["id"]

    response = client.delete(f"/knowledge-sources/{source_id}")

    assert response.status_code == 204
    assert session.query(KnowledgeSource).count() == 0
    assert session.query(KnowledgeChunk).count() == 0
    session.close()


def test_upload_rejects_unsupported_file_type() -> None:
    client, session = build_environment()

    response = client.post(
        "/knowledge-sources",
        json={"filename": "policy.pdf", "content": "Not supported yet."},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .md and .txt knowledge sources are supported."
    session.close()
