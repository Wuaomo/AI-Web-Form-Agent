"""Tests for execution verification agent to ensure correct interpretation of verification evidence."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_constants import (
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
    AGENT_DECISION_BLOCK,
)
from app.database import Base
from app.models import Profile, Task, FieldVerificationResult, utc_now
from app.models import (
    VERIFICATION_STATUS_VERIFIED,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_SKIPPED,
)


def test_all_required_verified_passes(tmp_path):
    """Verify that PASS is returned when all required fields are verified."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_pass_test.db"
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

    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash="abc123",
        status=VERIFICATION_STATUS_VERIFIED,
        reason=None,
    ))
    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=2,
        selector="input[name='name']",
        expected_value_hash="def456",
        actual_value_hash="def456",
        status=VERIFICATION_STATUS_VERIFIED,
        reason=None,
    ))
    db.commit()

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
            {
                "id": 2,
                "label": "Name",
                "selector": "input[name='name']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "full_name",
                "mapped_value": "John Doe",
                "confidence": 0.92,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_PASS
    assert len(result["items"]) == 0
    assert "verified successfully" in result["summary"]

    db.close()


def test_optional_mismatch_requires_review(tmp_path):
    """Verify that optional field failure produces REVIEW_REQUIRED."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_optional_test.db"
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

    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash="abc123",
        status=VERIFICATION_STATUS_VERIFIED,
        reason=None,
    ))
    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=2,
        selector="input[name='phone']",
        expected_value_hash="def456",
        actual_value_hash="xyz789",
        status=VERIFICATION_STATUS_FAILED,
        reason="VALUE_MISMATCH",
    ))
    db.commit()

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
            {
                "id": 2,
                "label": "Phone",
                "selector": "input[name='phone']",
                "field_type": "tel",
                "required": False,
                "mapped_profile_key": "phone",
                "mapped_value": "+1-555-123-4567",
                "confidence": 0.88,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "OPTIONAL_FIELD_FAILED"
    assert "Phone" in result["items"][0]["message"]

    db.close()


def test_required_mismatch_blocks(tmp_path):
    """Verify that required field failure produces BLOCK."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_required_test.db"
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

    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash="xyz789",
        status=VERIFICATION_STATUS_FAILED,
        reason="VALUE_MISMATCH",
    ))
    db.commit()

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "REQUIRED_FIELD_FAILED"
    assert "Email" in result["items"][0]["message"]

    db.close()


def test_unexpected_navigation_blocks(tmp_path):
    """Verify that unexpected page navigation produces BLOCK."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_nav_test.db"
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

    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash=None,
        status=VERIFICATION_STATUS_FAILED,
        reason="PAGE_NAVIGATED_UNEXPECTEDLY",
    ))
    db.commit()

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 2
    issue_types = [item["issue"] for item in result["items"]]
    assert "UNEXPECTED_NAVIGATION" in issue_types
    assert "REQUIRED_FIELD_FAILED" in issue_types

    db.close()


def test_sensitive_field_skipped_requires_review(tmp_path):
    """Verify that sensitive field skipped produces REVIEW_REQUIRED."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_sensitive_test.db"
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

    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash="abc123",
        status=VERIFICATION_STATUS_VERIFIED,
        reason=None,
    ))
    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=2,
        selector="input[name='password']",
        expected_value_hash=None,
        actual_value_hash=None,
        status=VERIFICATION_STATUS_SKIPPED,
        reason="SENSITIVE_FIELD_SKIPPED",
    ))
    db.commit()

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
            {
                "id": 2,
                "label": "Password",
                "selector": "input[name='password']",
                "field_type": "password",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.9,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "SENSITIVE_FIELD_SKIPPED"

    db.close()


def test_missing_verification_requires_review(tmp_path):
    """Verify that missing verification for mapped fields produces REVIEW_REQUIRED."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_missing_test.db"
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

    db.add(FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash="abc123",
        status=VERIFICATION_STATUS_VERIFIED,
        reason=None,
    ))
    db.commit()

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
            {
                "id": 2,
                "label": "Name",
                "selector": "input[name='name']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "full_name",
                "mapped_value": "John Doe",
                "confidence": 0.92,
            },
            {
                "id": 3,
                "label": "Phone",
                "selector": "input[name='phone']",
                "field_type": "tel",
                "required": False,
                "mapped_profile_key": "phone",
                "mapped_value": "+1-555-123-4567",
                "confidence": 0.88,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "MISSING_VERIFICATION"
    assert result["items"][0]["missing_count"] == 2

    db.close()


def test_no_verification_results_requires_review(tmp_path):
    """Verify that no verification results produces REVIEW_REQUIRED."""

    from app.services.execution_verification_agent import run_execution_verification_review

    db_path = tmp_path / "ev_empty_test.db"
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

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
            },
        ],
    }

    result = run_execution_verification_review(db, task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "MISSING_VERIFICATION"

    db.close()