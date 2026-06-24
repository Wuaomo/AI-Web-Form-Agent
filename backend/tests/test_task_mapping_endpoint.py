"""Tests for the task field-mapping endpoint mode selection."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import config
from app.models import FormField, Profile, Task
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


def create_task_with_field(session: Session) -> tuple[Task, FormField]:
    """Create a task with one extracted field for endpoint tests."""

    profile = Profile(
        profile_name="Endpoint profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="MAPPING_READY",
    )
    field = FormField(
        task=task,
        label="Where can we reach you?",
        selector="#contact",
        field_type="email",
        required=True,
    )
    session.add(task)
    session.add(field)
    session.commit()
    return task, field


def test_map_fields_defaults_to_llm_mode(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-openai-key")

    with (
        patch("app.routers.tasks.map_fields_with_llm", return_value=[field]) as llm,
        patch("app.routers.tasks.map_fields_by_rules") as rules,
    ):
        response = client.post(f"/tasks/{task.id}/map-fields")

    assert response.status_code == 200
    llm.assert_called_once()
    rules.assert_not_called()


def test_map_fields_passes_selected_llm_provider(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-gemini-key")

    with patch(
        "app.routers.tasks.map_fields_with_llm",
        return_value=[field],
    ) as llm:
        response = client.post(f"/tasks/{task.id}/map-fields?provider=gemini")

    assert response.status_code == 200
    llm.assert_called_once_with(task.id, session, provider="gemini")


def test_map_fields_reports_missing_provider_api_key(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, _ = create_task_with_field(session)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", None)

    with patch("app.routers.tasks.map_fields_with_llm") as llm:
        response = client.post(f"/tasks/{task.id}/map-fields?provider=deepseek")

    assert response.status_code == 409
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]
    llm.assert_not_called()


def test_map_fields_supports_developer_rule_mode(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)

    with (
        patch("app.routers.tasks.map_fields_with_llm") as llm,
        patch("app.routers.tasks.map_fields_by_rules", return_value=[field]) as rules,
    ):
        response = client.post(f"/tasks/{task.id}/map-fields?mode=rules")

    assert response.status_code == 200
    rules.assert_called_once()
    llm.assert_not_called()


def test_confirm_mapping_rejects_missing_required_values(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = None
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 409
    assert "Required fields need values" in response.json()["detail"]
    assert "Where can we reach you?" in response.json()["detail"]


def test_confirm_mapping_allows_required_values_after_manual_entry(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "manual@example.com"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    assert response.json()["status"] == "MAPPING_READY"


def test_fill_rejects_missing_required_values_before_browser_work(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = None
    session.commit()

    response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert "Required fields need values" in response.json()["detail"]
