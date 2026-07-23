"""Tests for local policy document retriever."""

from app.services.policy_doc_retriever import (
    PolicySourceHit,
    retrieve_policy_sources,
)


def test_retrieve_policy_sources_returns_source_metadata() -> None:
    """Verify the retriever returns hits with stable identifiers and a snippet."""

    hits = retrieve_policy_sources("Do you encrypt data at rest?", limit=3)

    assert hits
    assert hits[0].source_id
    assert hits[0].document_id
    assert hits[0].title
    assert hits[0].snippet
    assert 0 <= hits[0].score <= 1


def test_retrieve_policy_sources_returns_empty_for_unknown_question() -> None:
    """Verify an unknown query returns no hits."""

    assert retrieve_policy_sources("zzzz-not-a-policy-topic", limit=3) == []


def test_retrieve_policy_sources_respects_limit() -> None:
    """Verify the number of hits does not exceed the requested limit."""

    hits = retrieve_policy_sources("security", limit=2)

    assert len(hits) <= 2


def test_retrieve_policy_sources_have_stable_source_ids() -> None:
    """Verify source_id values are stable across calls for the same section."""

    hits_a = retrieve_policy_sources("encrypt data at rest", limit=3)
    hits_b = retrieve_policy_sources("encryption at rest", limit=3)

    assert hits_a[0].source_id == hits_b[0].source_id


def test_retrieve_policy_sources_returns_policy_source_hit_type() -> None:
    """Verify all returned items are PolicySourceHit instances."""

    hits = retrieve_policy_sources("MFA", limit=5)

    for hit in hits:
        assert isinstance(hit, PolicySourceHit)
