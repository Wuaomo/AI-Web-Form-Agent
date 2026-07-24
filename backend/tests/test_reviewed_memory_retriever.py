"""Tests for the reviewed memory retriever."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import WorkflowMemoryItem
from app.services.reviewed_memory_retriever import retrieve_reviewed_memory
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for retriever tests."""

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


def _make_memory(
    db: Session,
    *,
    field_text: str = "label: Company Name",
    mapped_profile_key: str = "company_name",
    workflow_type: str = "security_questionnaire",
    last_used_at: datetime | None = None,
    field_signature: str = "sig-001",
) -> WorkflowMemoryItem:
    """Insert a WorkflowMemoryItem row for testing."""

    item = WorkflowMemoryItem(
        memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
        workflow_type=workflow_type,
        source_domain="example.com",
        field_signature=field_signature,
        field_text=field_text,
        mapped_profile_key=mapped_profile_key,
        value_kind="profile_value",
        confidence=1.0,
        success_count=1,
        last_used_at=last_used_at or datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    return item


def test_retrieve_reviewed_memory_returns_matching_hits(session: Session) -> None:
    """Verify the retriever returns items matching the query text."""

    _make_memory(session, field_text="label: Company Name", mapped_profile_key="company_name")

    hits = retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="company name",
    )

    assert len(hits) >= 1
    assert hits[0].profile_key == "company_name"
    assert hits[0].confidence > 0.0


def test_retrieve_reviewed_memory_skips_sensitive_items(session: Session) -> None:
    """Verify sensitive memory items are never returned."""

    _make_memory(
        session,
        field_text="label: Password",
        mapped_profile_key="password",
    )

    hits = retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="password",
    )

    assert "secret" not in str(hits)
    assert all("password" not in (hit.profile_key or "") for hit in hits)


def test_retrieve_reviewed_memory_skips_payment_items(session: Session) -> None:
    """Verify payment-related memory items are filtered out."""

    _make_memory(
        session,
        field_text="label: Credit Card Number",
        mapped_profile_key="card_number",
    )

    hits = retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="credit card",
    )

    assert all("card" not in (hit.profile_key or "") for hit in hits)


def test_retrieve_reviewed_memory_marks_stale_hits(session: Session) -> None:
    """Verify stale memory items are returned with stale=True."""

    old_date = datetime.now(timezone.utc) - timedelta(days=120)
    _make_memory(
        session,
        field_text="label: Encryption Standard",
        mapped_profile_key="encryption_standard",
        last_used_at=old_date,
    )

    hits = retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="encryption",
    )

    stale_hits = [hit for hit in hits if hit.stale]
    assert len(stale_hits) >= 1
    assert all(hit.stale for hit in stale_hits)


def test_retrieve_reviewed_memory_limits_to_five_results(session: Session) -> None:
    """Verify the retriever returns at most 5 hits."""

    for i in range(10):
        _make_memory(
            session,
            field_text=f"label: Encryption Standard {i}",
            mapped_profile_key=f"encryption_standard_{i}",
            field_signature=f"sig-{i:03d}",
        )

    hits = retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="encryption standard",
    )

    assert len(hits) <= 5


def test_retrieve_reviewed_memory_filters_by_workflow_type(session: Session) -> None:
    """Verify only items matching the workflow_type are returned."""

    _make_memory(
        session,
        field_text="label: Company Name",
        mapped_profile_key="company_name",
        workflow_type="vendor_onboarding",
    )

    hits = retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="company name",
    )

    assert len(hits) == 0


def test_retrieve_reviewed_memory_does_not_write(session: Session) -> None:
    """Verify the retriever is read-only and creates no new rows."""

    _make_memory(session, field_text="label: Company Name", mapped_profile_key="company_name")
    count_before = session.query(WorkflowMemoryItem).count()

    retrieve_reviewed_memory(
        session,
        profile_id=1,
        workflow_type="security_questionnaire",
        query="company name",
    )

    count_after = session.query(WorkflowMemoryItem).count()
    assert count_before == count_after
