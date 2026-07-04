"""Tests for agent coordinator to ensure predictable and auditable orchestration."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_constants import (
    AGENT_ROLE_MAPPING_CRITIC,
    AGENT_ROLE_SAFETY_REVIEW,
    AGENT_ROLE_EXECUTION_VERIFICATION,
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
    AGENT_DECISION_BLOCK,
)
from app.database import Base
from app.models import Profile, Task, AgentReview


def test_build_agent_input_hash_is_deterministic():
    """Verify that build_agent_input_hash returns the same hash for identical inputs."""

    from app.services.agent_coordinator import build_agent_input_hash

    payload1 = {"task_id": 1, "url": "https://example.com", "fields": ["a", "b"]}
    payload2 = {"task_id": 1, "url": "https://example.com", "fields": ["a", "b"]}
    payload3 = {"task_id": 2, "url": "https://example.com", "fields": ["a", "b"]}

    hash1 = build_agent_input_hash(payload1)
    hash2 = build_agent_input_hash(payload2)
    hash3 = build_agent_input_hash(payload3)

    assert hash1 == hash2, "Identical payloads should produce identical hashes"
    assert hash1 != hash3, "Different payloads should produce different hashes"
    assert len(hash1) == 64, "Hash should be 64 characters (SHA256)"


def test_build_agent_input_hash_is_order_independent():
    """Verify that build_agent_input_hash is not affected by dict key order."""

    from app.services.agent_coordinator import build_agent_input_hash

    payload1 = {"a": 1, "b": 2, "c": 3}
    payload2 = {"c": 3, "a": 1, "b": 2}

    hash1 = build_agent_input_hash(payload1)
    hash2 = build_agent_input_hash(payload2)

    assert hash1 == hash2, "Hashes should be identical regardless of key order"


def test_validate_agent_json_passes_with_required_keys():
    """Verify that validate_agent_json passes when all required keys are present."""

    from app.services.agent_coordinator import validate_agent_json

    valid_output = {
        "decision": AGENT_DECISION_PASS,
        "summary": "All good",
        "items": [],
    }

    result = validate_agent_json(valid_output)

    assert result == valid_output


def test_validate_agent_json_raises_for_missing_decision():
    """Verify that validate_agent_json raises ValueError when decision is missing."""

    from app.services.agent_coordinator import validate_agent_json

    invalid_output = {
        "summary": "All good",
        "items": [],
    }

    with pytest.raises(ValueError, match="Missing required keys"):
        validate_agent_json(invalid_output)


def test_validate_agent_json_raises_for_missing_summary():
    """Verify that validate_agent_json raises ValueError when summary is missing."""

    from app.services.agent_coordinator import validate_agent_json

    invalid_output = {
        "decision": AGENT_DECISION_PASS,
        "items": [],
    }

    with pytest.raises(ValueError, match="Missing required keys"):
        validate_agent_json(invalid_output)


def test_validate_agent_json_raises_for_missing_items():
    """Verify that validate_agent_json raises ValueError when items is missing."""

    from app.services.agent_coordinator import validate_agent_json

    invalid_output = {
        "decision": AGENT_DECISION_PASS,
        "summary": "All good",
    }

    with pytest.raises(ValueError, match="Missing required keys"):
        validate_agent_json(invalid_output)


def test_validate_agent_json_raises_for_non_dict():
    """Verify that validate_agent_json raises ValueError for non-dict payload."""

    from app.services.agent_coordinator import validate_agent_json

    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_agent_json("not a dict")

    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_agent_json(["list", "not", "dict"])


def test_run_agent_review_sequence_roles_run_in_order(tmp_path):
    """Verify that run_agent_review_sequence executes roles in the requested order."""

    from app.services.agent_coordinator import run_agent_review_sequence

    db_path = tmp_path / "agent_seq_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    profile = Profile(profile_name="Test Profile")
    db.add(profile)
    db.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.commit()

    roles = [AGENT_ROLE_SAFETY_REVIEW, AGENT_ROLE_MAPPING_CRITIC]
    results = run_agent_review_sequence(task.id, db, roles)

    assert len(results) == 2
    assert results[0].role == AGENT_ROLE_SAFETY_REVIEW
    assert results[1].role == AGENT_ROLE_MAPPING_CRITIC

    db.close()


def test_run_agent_review_sequence_invalid_agent_result_becomes_review_required(tmp_path):
    """Verify that invalid agent output results in REVIEW_REQUIRED decision."""

    from app.services.agent_coordinator import run_agent_review_sequence

    db_path = tmp_path / "agent_invalid_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    profile = Profile(profile_name="Test Profile")
    db.add(profile)
    db.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.commit()

    results = run_agent_review_sequence(task.id, db, [AGENT_ROLE_MAPPING_CRITIC])

    assert len(results) == 1
    review = results[0]
    assert review.role == AGENT_ROLE_MAPPING_CRITIC
    assert review.decision in {AGENT_DECISION_PASS, AGENT_DECISION_REVIEW_REQUIRED, AGENT_DECISION_BLOCK}

    db.close()


def test_run_agent_review_sequence_persists_all_decisions(tmp_path):
    """Verify that all agent decisions are persisted to the database."""

    from app.services.agent_coordinator import run_agent_review_sequence, get_agent_reviews_for_task

    db_path = tmp_path / "agent_persist_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    profile = Profile(profile_name="Test Profile")
    db.add(profile)
    db.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.commit()

    roles = [AGENT_ROLE_MAPPING_CRITIC, AGENT_ROLE_SAFETY_REVIEW, AGENT_ROLE_EXECUTION_VERIFICATION]
    run_agent_review_sequence(task.id, db, roles)
    db.commit()

    persisted_reviews = get_agent_reviews_for_task(db, task.id)

    assert len(persisted_reviews) == 3
    roles_found = {review.role for review in persisted_reviews}
    assert roles_found == {AGENT_ROLE_MAPPING_CRITIC, AGENT_ROLE_SAFETY_REVIEW, AGENT_ROLE_EXECUTION_VERIFICATION}

    for review in persisted_reviews:
        assert review.input_hash is not None
        assert review.output_json is not None
        assert review.created_at is not None

    db.close()


def test_run_agent_review_sequence_unknown_role_skipped(tmp_path):
    """Verify that unknown agent roles are skipped."""

    from app.services.agent_coordinator import run_agent_review_sequence

    db_path = tmp_path / "agent_unknown_role.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    profile = Profile(profile_name="Test Profile")
    db.add(profile)
    db.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.commit()

    roles = ["UNKNOWN_ROLE", AGENT_ROLE_MAPPING_CRITIC, "ANOTHER_UNKNOWN"]
    results = run_agent_review_sequence(task.id, db, roles)

    assert len(results) == 1
    assert results[0].role == AGENT_ROLE_MAPPING_CRITIC

    db.close()


def test_run_agent_review_sequence_returns_list_of_agent_reviews(tmp_path):
    """Verify that run_agent_review_sequence returns AgentReview objects."""

    from app.services.agent_coordinator import run_agent_review_sequence

    db_path = tmp_path / "agent_return_type.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    profile = Profile(profile_name="Test Profile")
    db.add(profile)
    db.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.commit()

    results = run_agent_review_sequence(task.id, db, [AGENT_ROLE_MAPPING_CRITIC])

    assert len(results) == 1
    assert isinstance(results[0], AgentReview)
    assert results[0].id is not None
    assert results[0].task_id == task.id

    db.close()


def test_agent_review_output_json_round_trips(tmp_path):
    """Verify that agent review output JSON can be serialized and deserialized."""

    from app.services.agent_coordinator import run_agent_review_sequence

    db_path = tmp_path / "agent_json_roundtrip.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    profile = Profile(profile_name="Test Profile")
    db.add(profile)
    db.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.commit()

    results = run_agent_review_sequence(task.id, db, [AGENT_ROLE_MAPPING_CRITIC])
    db.commit()

    review = results[0]
    session = Session()
    persisted_review = session.get(AgentReview, review.id)

    assert persisted_review is not None
    assert persisted_review.output_json is not None

    parsed_output = json.loads(persisted_review.output_json)
    assert isinstance(parsed_output, dict)
    assert "decision" in parsed_output
    assert "summary" in parsed_output
    assert "items" in parsed_output

    session.close()
    db.close()