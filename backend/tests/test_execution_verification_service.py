"""Tests for execution verification service."""

import hashlib

import pytest

from app.models import (
    VERIFICATION_STATUS_VERIFIED,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_SKIPPED,
    VERIFICATION_REASON_VALUE_MISMATCH,
    VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED,
)


def test_hash_verification_value_returns_hash():
    """Verify hash function returns SHA256 hash, not raw value."""

    from app.services.execution_verification_service import hash_verification_value

    value = "test@example.com"
    result = hash_verification_value(value)

    expected_hash = hashlib.sha256(value.encode("utf-8")).hexdigest()
    assert result == expected_hash
    assert result != value


def test_hash_verification_value_handles_none():
    """Verify hash function handles None input."""

    from app.services.execution_verification_service import hash_verification_value

    result = hash_verification_value(None)
    assert result is None


def test_hash_verification_value_handles_empty_string():
    """Verify hash function handles empty string."""

    from app.services.execution_verification_service import hash_verification_value

    result = hash_verification_value("")
    assert result is not None
    assert result == hashlib.sha256(b"").hexdigest()


def test_compare_field_value_matching_values_verify():
    """Verify matching values return VERIFIED."""

    from app.services.execution_verification_service import compare_field_value

    status, reason = compare_field_value("test@example.com", "test@example.com")
    assert status == VERIFICATION_STATUS_VERIFIED
    assert reason is None


def test_compare_field_value_mismatched_values_fail():
    """Verify mismatched values return FAILED with VALUE_MISMATCH."""

    from app.services.execution_verification_service import compare_field_value

    status, reason = compare_field_value("expected@example.com", "actual@different.com")
    assert status == VERIFICATION_STATUS_FAILED
    assert reason == VERIFICATION_REASON_VALUE_MISMATCH


def test_compare_field_value_empty_expected_skips():
    """Verify empty expected value returns SKIPPED."""

    from app.services.execution_verification_service import compare_field_value

    status, reason = compare_field_value("", "some value")
    assert status == VERIFICATION_STATUS_SKIPPED
    assert reason is None


def test_compare_field_value_none_expected_skips():
    """Verify None expected value returns SKIPPED."""

    from app.services.execution_verification_service import compare_field_value

    status, reason = compare_field_value(None, "some value")
    assert status == VERIFICATION_STATUS_SKIPPED
    assert reason is None


def test_should_skip_verification_password_field():
    """Verify password field type is skipped."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="input[type='password']",
        field_type="password",
        label="Password",
    )
    assert should_skip_verification(field) is True


def test_should_skip_verification_file_field():
    """Verify file input field type is skipped."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="input[type='file']",
        field_type="file",
        label="Upload file",
    )
    assert should_skip_verification(field) is True


def test_should_skip_verification_button_field():
    """Verify button field type is skipped."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="button",
        field_type="button",
        label="Submit",
    )
    assert should_skip_verification(field) is True


def test_should_skip_verification_otp_field_by_label():
    """Verify OTP field is skipped by label pattern."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="input[name='otp']",
        field_type="text",
        label="One-Time Password",
    )
    assert should_skip_verification(field) is True


def test_should_skip_verification_credit_card_field_by_name():
    """Verify credit card field is skipped by name pattern."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="input[name='credit_card_number']",
        field_type="text",
        label="Card Number",
    )
    assert should_skip_verification(field) is True


def test_should_skip_verification_ssn_field_by_placeholder():
    """Verify SSN field is skipped by placeholder pattern."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="input[name='tax_id']",
        field_type="text",
        label="Tax ID",
        placeholder="Enter your SSN",
    )
    assert should_skip_verification(field) is True


def test_should_skip_verification_regular_field_returns_false():
    """Verify regular text field is not skipped."""

    from app.services.execution_verification_service import should_skip_verification
    from app.models import FormField

    field = FormField(
        selector="input[name='email']",
        field_type="email",
        label="Email Address",
        placeholder="Enter email",
    )
    assert should_skip_verification(field) is False


def test_save_and_retrieve_verification_results(tmp_path):
    """Verify verification results are saved and retrieved correctly."""

    from app.database import Base
    from app.models import Profile, Task, FieldVerificationResult
    from app.services.execution_verification_service import (
        save_verification_result,
        get_verification_results_for_task,
        get_verification_summary_for_task,
        hash_verification_value,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "verification_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    save_verification_result(
        session,
        task_id=task.id,
        field_id=None,
        selector="input[name='email']",
        expected_value="test@example.com",
        actual_value="test@example.com",
        status=VERIFICATION_STATUS_VERIFIED,
    )

    save_verification_result(
        session,
        task_id=task.id,
        field_id=None,
        selector="input[name='password']",
        expected_value=None,
        actual_value=None,
        status=VERIFICATION_STATUS_SKIPPED,
        reason=VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED,
    )

    session.commit()

    results = get_verification_results_for_task(session, task.id)
    assert len(results) == 2

    verified_result = results[0]
    assert verified_result.task_id == task.id
    assert verified_result.selector == "input[name='email']"
    assert verified_result.status == VERIFICATION_STATUS_VERIFIED
    assert verified_result.reason is None
    assert verified_result.expected_value_hash == hash_verification_value("test@example.com")
    assert verified_result.actual_value_hash == hash_verification_value("test@example.com")

    skipped_result = results[1]
    assert skipped_result.selector == "input[name='password']"
    assert skipped_result.status == VERIFICATION_STATUS_SKIPPED
    assert skipped_result.reason == VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED
    assert skipped_result.expected_value_hash is None
    assert skipped_result.actual_value_hash is None

    summary = get_verification_summary_for_task(session, task.id)
    assert summary[VERIFICATION_STATUS_VERIFIED] == 1
    assert summary[VERIFICATION_STATUS_SKIPPED] == 1
    assert summary[VERIFICATION_STATUS_FAILED] == 0
    assert summary["PARTIAL"] == 0

    session.close()