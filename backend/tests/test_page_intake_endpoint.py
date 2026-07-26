"""Tests for the page intake analyze endpoint."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import TaskCheckpoint
from app.routers.page_intake import router as page_intake_router
from app.services.page_intake_service import (
    PageIntakeEvidence,
    PageIntakeResult,
)
from app.workflow_constants import CHECKPOINT_FAILED, CHECKPOINT_SUCCESS


def build_environment() -> tuple[TestClient, Session]:
    """Build an isolated API environment for page intake endpoint tests."""

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
    app.include_router(page_intake_router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def _sample_result() -> PageIntakeResult:
    """Build a sample PageIntakeResult for testing."""

    return PageIntakeResult(
        page_type="questionnaire",
        recommended_workflow="security_questionnaire",
        confidence=0.85,
        summary="Detected questionnaire page with 0 field(s). Recommended workflow: security_questionnaire.",
        risk_flags=[],
        blocked_reasons=[],
        evidence=[
            PageIntakeEvidence(
                source="page_text",
                text="matched: security",
                reason="Page text contains security/compliance questionnaire signals",
            )
        ],
    )


def test_analyze_endpoint_returns_intake_result() -> None:
    """POST /page-intake/analyze returns a PageIntakeResponse on success."""

    client, session = build_environment()

    mock_result = _sample_result()
    with patch(
        "app.routers.page_intake.analyze_page_intake",
        new_callable=AsyncMock,
        return_value=mock_result,
    ), patch(
        "app.routers.page_intake.safe_create_span", return_value=None
    ), patch(
        "app.routers.page_intake.safe_finish_span",
    ):
        response = client.post(
            "/page-intake/analyze",
            json={
                "url": "https://example.com/security",
                "profile_id": 1,
                "user_goal": "review this questionnaire",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "page_type" in data
    assert "recommended_workflow" in data
    assert "risk_flags" in data
    assert "evidence" in data
    assert data["page_type"] == "questionnaire"
    assert data["recommended_workflow"] == "security_questionnaire"

    session.close()


def test_analyze_endpoint_writes_checkpoint_on_success() -> None:
    """POST /page-intake/analyze writes a SUCCESS checkpoint when task_id is provided."""

    client, session = build_environment()

    mock_result = _sample_result()
    with patch(
        "app.routers.page_intake.analyze_page_intake",
        new_callable=AsyncMock,
        return_value=mock_result,
    ), patch(
        "app.routers.page_intake.safe_create_span", return_value=None
    ), patch(
        "app.routers.page_intake.safe_finish_span",
    ):
        response = client.post(
            "/page-intake/analyze",
            json={
                "url": "https://example.com/security",
                "profile_id": 1,
                "user_goal": "review this questionnaire",
                "task_id": 42,
            },
        )

    assert response.status_code == 200

    checkpoint = session.scalar(
        select(TaskCheckpoint).where(
            TaskCheckpoint.task_id == 42,
            TaskCheckpoint.stage == "PAGE_INTAKE",
        )
    )
    assert checkpoint is not None
    assert checkpoint.status == CHECKPOINT_SUCCESS

    session.close()


def test_analyze_endpoint_returns_500_and_writes_failed_checkpoint() -> None:
    """POST /page-intake/analyze returns 500 and writes FAILED checkpoint on service error."""

    client, session = build_environment()

    with patch(
        "app.routers.page_intake.analyze_page_intake",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ), patch(
        "app.routers.page_intake.safe_create_span", return_value=None
    ), patch(
        "app.routers.page_intake.safe_finish_span",
    ):
        response = client.post(
            "/page-intake/analyze",
            json={
                "url": "https://example.com/security",
                "profile_id": 1,
                "user_goal": "review this questionnaire",
                "task_id": 42,
            },
        )

    assert response.status_code == 500

    checkpoint = session.scalar(
        select(TaskCheckpoint).where(
            TaskCheckpoint.task_id == 42,
            TaskCheckpoint.stage == "PAGE_INTAKE",
        )
    )
    assert checkpoint is not None
    assert checkpoint.status == CHECKPOINT_FAILED

    session.close()
