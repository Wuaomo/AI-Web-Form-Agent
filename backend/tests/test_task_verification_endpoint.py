"""Tests for verification result persistence during form filling."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import FormField, Profile, Task, FieldVerificationResult
from app.routers.tasks import router as tasks_router


@pytest.fixture
def test_environment() -> Generator[tuple[TestClient, Session], None, None]:
    """Provide an isolated API client and in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    test_app = FastAPI()
    test_app.include_router(tasks_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_task_with_fields(session: Session, required: bool = True) -> tuple[Task, list[FormField]]:
    """Create a task with mapped fields ready for filling."""

    profile = Profile(
        profile_name="Verification test profile",
        full_name="Test User",
        email="test@example.com",
    )
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        status="READY_TO_FILL",
    )
    session.add(task)
    session.flush()

    fields = [
        FormField(
            task_id=task.id,
            label="Email",
            selector="#email",
            field_type="email",
            required=required,
            mapped_profile_key="email",
            mapped_value="test@example.com",
            confidence=1.0,
        ),
        FormField(
            task_id=task.id,
            label="Name",
            selector="#name",
            field_type="text",
            required=False,
            mapped_profile_key="full_name",
            mapped_value="Test User",
            confidence=1.0,
        ),
    ]
    session.add_all(fields)
    session.commit()
    return task, fields


def create_task_with_sensitive_field(session: Session) -> tuple[Task, list[FormField]]:
    """Create a task with a password field that should be skipped."""

    profile = Profile(
        profile_name="Sensitive test profile",
        email="test@example.com",
    )
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        status="READY_TO_FILL",
    )
    session.add(task)
    session.flush()

    fields = [
        FormField(
            task_id=task.id,
            label="Email",
            selector="#email",
            field_type="email",
            required=True,
            mapped_profile_key="email",
            mapped_value="test@example.com",
            confidence=1.0,
        ),
        FormField(
            task_id=task.id,
            label="Password",
            selector="#password",
            field_type="password",
            required=True,
            mapped_value="secret123",
            confidence=1.0,
        ),
    ]
    session.add_all(fields)
    session.commit()
    return task, fields


def test_fill_creates_verified_results(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify successful fill creates VERIFIED verification results."""

    client, session = test_environment
    task, fields = create_task_with_fields(session)

    from app.services.browser_executor import FieldVerificationData
    from app.models import VERIFICATION_STATUS_VERIFIED

    mock_verification_data = [
        FieldVerificationData(
            field_id=fields[0].id,
            selector="#email",
            expected_value="test@example.com",
            actual_value="test@example.com",
            status=VERIFICATION_STATUS_VERIFIED,
        ),
        FieldVerificationData(
            field_id=fields[1].id,
            selector="#name",
            expected_value="Test User",
            actual_value="Test User",
            status=VERIFICATION_STATUS_VERIFIED,
        ),
    ]

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as mock_fill:
        mock_fill.return_value = (AsyncMock(), mock_verification_data)
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "WAITING_APPROVAL"

    verification_results = list(
        session.scalars(
            select(FieldVerificationResult)
            .where(FieldVerificationResult.task_id == task.id)
            .order_by(FieldVerificationResult.id)
        )
    )
    assert len(verification_results) == 2
    assert verification_results[0].field_id == fields[0].id
    assert verification_results[0].selector == "#email"
    assert verification_results[0].status == VERIFICATION_STATUS_VERIFIED
    assert verification_results[0].expected_value_hash is not None
    assert verification_results[0].actual_value_hash is not None

    assert verification_results[1].field_id == fields[1].id
    assert verification_results[1].selector == "#name"
    assert verification_results[1].status == VERIFICATION_STATUS_VERIFIED


def test_fill_creates_failed_result_for_missing_selector(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify fill creates FAILED result when field cannot be read."""

    client, session = test_environment
    task, fields = create_task_with_fields(session)

    from app.services.browser_executor import FieldVerificationData
    from app.models import (
        VERIFICATION_STATUS_FAILED,
        VERIFICATION_REASON_SELECTOR_NOT_FOUND,
    )

    mock_verification_data = [
        FieldVerificationData(
            field_id=fields[0].id,
            selector="#email",
            expected_value="test@example.com",
            actual_value=None,
            status=VERIFICATION_STATUS_FAILED,
            reason=VERIFICATION_REASON_SELECTOR_NOT_FOUND,
            message="Could not read field value after fill",
        ),
        FieldVerificationData(
            field_id=fields[1].id,
            selector="#name",
            expected_value="Test User",
            actual_value="Test User",
            status="VERIFIED",
        ),
    ]

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as mock_fill:
        mock_fill.return_value = (AsyncMock(), mock_verification_data)
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 500

    task_refreshed = session.get(Task, task.id)
    assert task_refreshed.status == "FAILED"

    verification_results = list(
        session.scalars(
            select(FieldVerificationResult)
            .where(FieldVerificationResult.task_id == task.id)
            .order_by(FieldVerificationResult.id)
        )
    )
    assert len(verification_results) == 2
    assert verification_results[0].status == VERIFICATION_STATUS_FAILED
    assert verification_results[0].reason == VERIFICATION_REASON_SELECTOR_NOT_FOUND
    assert verification_results[1].status == "VERIFIED"


def test_fill_skips_sensitive_password_field(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify sensitive password fields are blocked before fill execution."""

    client, session = test_environment
    task, fields = create_task_with_sensitive_field(session)

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as mock_fill:
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert response.json()["detail"] == "Required fields were blocked by policy: Password"
    mock_fill.assert_not_awaited()

    verification_results = list(
        session.scalars(
            select(FieldVerificationResult)
            .where(FieldVerificationResult.task_id == task.id)
            .order_by(FieldVerificationResult.id)
        )
    )
    assert verification_results == []


def test_fill_deletes_previous_verification_results(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify previous verification results are cleared before new fill attempt."""

    client, session = test_environment
    task, fields = create_task_with_fields(session)

    old_verification = FieldVerificationResult(
        task_id=task.id,
        field_id=fields[0].id,
        selector="#email",
        expected_value_hash="old_hash_1",
        actual_value_hash="old_hash_1",
        status="VERIFIED",
    )
    session.add(old_verification)
    session.commit()

    from app.services.browser_executor import FieldVerificationData
    from app.models import VERIFICATION_STATUS_VERIFIED

    mock_verification_data = [
        FieldVerificationData(
            field_id=fields[0].id,
            selector="#email",
            expected_value="test@example.com",
            actual_value="test@example.com",
            status=VERIFICATION_STATUS_VERIFIED,
        ),
    ]

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as mock_fill:
        mock_fill.return_value = (AsyncMock(), mock_verification_data)
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 200

    verification_results = list(
        session.scalars(
            select(FieldVerificationResult)
            .where(FieldVerificationResult.task_id == task.id)
        )
    )
    assert len(verification_results) == 1
    assert verification_results[0].expected_value_hash != "old_hash_1"


def test_get_verification_results_returns_ordered_results(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify verification results endpoint returns ordered results."""

    client, session = test_environment
    task, fields = create_task_with_fields(session)

    from app.models import VERIFICATION_STATUS_VERIFIED, VERIFICATION_STATUS_SKIPPED

    result1 = FieldVerificationResult(
        task_id=task.id,
        field_id=fields[0].id,
        selector="#email",
        expected_value_hash="hash1",
        actual_value_hash="hash1",
        status=VERIFICATION_STATUS_VERIFIED,
    )
    result2 = FieldVerificationResult(
        task_id=task.id,
        field_id=fields[1].id,
        selector="#name",
        expected_value_hash="hash2",
        actual_value_hash="hash2",
        status=VERIFICATION_STATUS_VERIFIED,
    )
    result3 = FieldVerificationResult(
        task_id=task.id,
        field_id=None,
        selector="#password",
        expected_value_hash=None,
        actual_value_hash=None,
        status=VERIFICATION_STATUS_SKIPPED,
        reason="SENSITIVE_FIELD_SKIPPED",
    )
    session.add_all([result1, result2, result3])
    session.commit()

    response = client.get(f"/tasks/{task.id}/verification-results")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 3
    assert data[0]["field_id"] == fields[0].id
    assert data[0]["selector"] == "#email"
    assert data[0]["status"] == VERIFICATION_STATUS_VERIFIED
    assert data[0]["reason"] is None

    assert data[1]["field_id"] == fields[1].id
    assert data[1]["selector"] == "#name"
    assert data[1]["status"] == VERIFICATION_STATUS_VERIFIED

    assert data[2]["field_id"] is None
    assert data[2]["selector"] == "#password"
    assert data[2]["status"] == VERIFICATION_STATUS_SKIPPED
    assert data[2]["reason"] == "SENSITIVE_FIELD_SKIPPED"


def test_get_verification_results_missing_task_returns_404(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify verification results endpoint returns 404 for missing task."""

    client, _ = test_environment

    response = client.get("/tasks/999/verification-results")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"
