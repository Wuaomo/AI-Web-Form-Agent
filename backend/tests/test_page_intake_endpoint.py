"""Tests for the page intake analyze endpoint."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Profile, Task, TaskCheckpoint
from app.routers.page_intake import router as page_intake_router
from app.services.page_intake_service import (
    PageIntakeEvidence,
    PageIntakeResult,
)
from app.workflow_constants import CHECKPOINT_FAILED, CHECKPOINT_SUCCESS

TEST_URL = "https://example.com/security"
TEST_PROFILE_ID = 1
TEST_USER_GOAL = "review this questionnaire"


def build_environment() -> tuple[TestClient, Session, Engine]:
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

    return TestClient(app), session, engine


def _create_profile_and_task(session: Session) -> tuple[Profile, Task]:
    """Create a Profile and a matching Task in the test database."""

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.flush()

    task = Task(
        url=TEST_URL,
        profile_id=profile.id,
        workflow_type="security_questionnaire",
    )
    session.add(task)
    session.flush()
    session.commit()

    return profile, task


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


def test_preview_mode_returns_200_without_span_or_checkpoint() -> None:
    """POST without task_id returns 200 and does not create span or checkpoint."""

    client, session, engine = build_environment()

    mock_result = _sample_result()
    mock_safe_create_span = MagicMock(return_value=None)
    mock_safe_finish_span = MagicMock()

    with patch(
        "app.routers.page_intake.analyze_page_intake",
        new_callable=AsyncMock,
        return_value=mock_result,
    ), patch(
        "app.routers.page_intake.safe_create_span", mock_safe_create_span
    ), patch(
        "app.routers.page_intake.safe_finish_span", mock_safe_finish_span
    ):
        response = client.post(
            "/page-intake/analyze",
            json={
                "url": TEST_URL,
                "profile_id": TEST_PROFILE_ID,
                "user_goal": TEST_USER_GOAL,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["page_type"] == "questionnaire"
    assert data["recommended_workflow"] == "security_questionnaire"

    mock_safe_create_span.assert_not_called()
    mock_safe_finish_span.assert_not_called()

    session.close()
    with Session(engine) as verify_session:
        checkpoint_count = len(list(verify_session.scalars(select(TaskCheckpoint))))
        assert checkpoint_count == 0



def test_unknown_task_id_returns_404() -> None:
    """POST with non-existent task_id returns 404 Task not found."""

    client, session, _engine = build_environment()

    response = client.post(
        "/page-intake/analyze",
        json={
            "url": TEST_URL,
            "profile_id": TEST_PROFILE_ID,
            "user_goal": TEST_USER_GOAL,
            "task_id": 999,
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    session.close()


def test_mismatched_task_url_returns_400() -> None:
    """POST with task_id whose url does not match request returns 400."""

    client, session, _engine = build_environment()
    _profile, task = _create_profile_and_task(session)

    response = client.post(
        "/page-intake/analyze",
        json={
            "url": "https://example.com/different",
            "profile_id": task.profile_id,
            "user_goal": TEST_USER_GOAL,
            "task_id": task.id,
        },
    )

    assert response.status_code == 400

    session.close()


def test_mismatched_task_profile_returns_400() -> None:
    """POST with task_id whose profile_id does not match request returns 400."""

    client, session, _engine = build_environment()
    profile, task = _create_profile_and_task(session)

    response = client.post(
        "/page-intake/analyze",
        json={
            "url": task.url,
            "profile_id": profile.id + 99,
            "user_goal": TEST_USER_GOAL,
            "task_id": task.id,
        },
    )

    assert response.status_code == 400

    session.close()


def test_matching_task_writes_success_checkpoint() -> None:
    """POST with matching task_id writes a PAGE_INTAKE SUCCESS checkpoint."""

    client, session, engine = build_environment()
    _profile, task = _create_profile_and_task(session)

    mock_result = _sample_result()
    with patch(
        "app.routers.page_intake.analyze_page_intake",
        new_callable=AsyncMock,
        return_value=mock_result,
    ), patch(
        "app.routers.page_intake.safe_create_span", return_value="span-1"
    ), patch(
        "app.routers.page_intake.safe_finish_span",
    ):
        response = client.post(
            "/page-intake/analyze",
            json={
                "url": task.url,
                "profile_id": task.profile_id,
                "user_goal": TEST_USER_GOAL,
                "task_id": task.id,
            },
        )

    assert response.status_code == 200

    task_id = task.id
    session.close()
    with Session(engine) as verify_session:
        checkpoint = verify_session.scalar(
            select(TaskCheckpoint).where(
                TaskCheckpoint.task_id == task_id,
                TaskCheckpoint.stage == "PAGE_INTAKE",
            )
        )
        assert checkpoint is not None
        assert checkpoint.status == CHECKPOINT_SUCCESS


def test_matching_task_returns_500_and_writes_failed_checkpoint() -> None:
    """POST with matching task_id and service error returns 500 and writes FAILED checkpoint."""

    client, session, engine = build_environment()
    _profile, task = _create_profile_and_task(session)

    with patch(
        "app.routers.page_intake.analyze_page_intake",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ), patch(
        "app.routers.page_intake.safe_create_span", return_value="span-1"
    ), patch(
        "app.routers.page_intake.safe_finish_span",
    ):
        response = client.post(
            "/page-intake/analyze",
            json={
                "url": task.url,
                "profile_id": task.profile_id,
                "user_goal": TEST_USER_GOAL,
                "task_id": task.id,
            },
        )

    assert response.status_code == 500

    task_id = task.id
    session.close()
    with Session(engine) as verify_session:
        checkpoint = verify_session.scalar(
            select(TaskCheckpoint).where(
                TaskCheckpoint.task_id == task_id,
                TaskCheckpoint.stage == "PAGE_INTAKE",
            )
        )
        assert checkpoint is not None
        assert checkpoint.status == CHECKPOINT_FAILED
