"""Tests for lexical retrieval scoring over workflow memory items."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import WorkflowMemoryItem
from app.services.retrieval_service import (
    jaccard_similarity,
    search_similar_field_mappings,
    tokenize,
)
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_tokenize_lowercases_words() -> None:
    assert tokenize("GitHub URL") == {"github", "url"}


def test_jaccard_similarity_basic() -> None:
    assert jaccard_similarity("github url", "github profile url") == pytest.approx(2 / 3)


def test_search_similar_field_mappings_ranks_by_score_and_filters_low_values(session: Session) -> None:
    session.add_all(
        [
            WorkflowMemoryItem(
                memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
                workflow_type="form_fill",
                source_domain="example.com",
                field_signature="sig1",
                field_text="label: GitHub\nname: github_url\ntype: url\noptions: []",
                mapped_profile_key="github",
                success_count=3,
            ),
            WorkflowMemoryItem(
                memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
                workflow_type="form_fill",
                source_domain="other.com",
                field_signature="sig2",
                field_text="label: Phone\nname: phone\ntype: tel\noptions: []",
                mapped_profile_key="phone",
                success_count=1,
            ),
        ]
    )
    session.commit()

    results = search_similar_field_mappings(
        session,
        field_text="label: GitHub\nname: github_profile\ntype: url\noptions: []",
        workflow_type="form_fill",
        source_domain="example.com",
        limit=5,
    )

    assert results
    assert results[0]["mapped_profile_key"] == "github"
    assert results[0]["source_domain"] == "example.com"
    assert results[0]["success_count"] == 3

    low_results = search_similar_field_mappings(
        session,
        field_text="label: Completely unrelated\nname: random\ntype: text\noptions: []",
        workflow_type="form_fill",
        source_domain="example.com",
        limit=5,
    )
    assert low_results == []


def test_search_similar_field_mappings_ignores_non_confirmed_memory_types(session: Session) -> None:
    session.add_all(
        [
            WorkflowMemoryItem(
                memory_type="successful_run",
                workflow_type="form_fill",
                source_domain="example.com",
                field_signature="sig_non_confirmed",
                field_text="label: GitHub\nname: github_url\ntype: url\noptions: []",
                mapped_profile_key="github",
                success_count=50,
            ),
            WorkflowMemoryItem(
                memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
                workflow_type="form_fill",
                source_domain="example.com",
                field_signature="sig_confirmed",
                field_text="label: GitHub\nname: github_url\ntype: url\noptions: []",
                mapped_profile_key="github",
                success_count=1,
            ),
        ]
    )
    session.commit()

    results = search_similar_field_mappings(
        session,
        field_text="label: GitHub\nname: github_profile\ntype: url\noptions: []",
        workflow_type="form_fill",
        source_domain="example.com",
        limit=5,
    )

    assert len(results) == 1
    assert results[0]["success_count"] == 1
