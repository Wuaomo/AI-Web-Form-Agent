"""Tests for the task field-mapping endpoint mode selection."""

import json
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import config
from app.models import ActionLog, FormField, Profile, Screenshot, Task
from app.routers.tasks import router as tasks_router
from app.services.field_mapper import map_fields_with_llm
from app.services.form_extractor import ExtractedFormField


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


def create_task_without_fields(session: Session) -> Task:
    """Create a task that has not been analyzed yet."""

    profile = Profile(
        profile_name="Analysis profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="CREATED",
    )
    session.add(task)
    session.commit()
    return task


def test_map_fields_requires_llm_provider_when_no_default_is_configured(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, _ = create_task_with_field(session)
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    with patch("app.routers.tasks.map_fields_with_llm") as llm:
        response = client.post(f"/tasks/{task.id}/map-fields")

    assert response.status_code == 400
    assert "Choose an LLM provider" in response.json()["detail"]
    llm.assert_not_called()


def test_map_fields_uses_selected_deepseek_provider(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    with patch(
        "app.routers.tasks.map_fields_with_llm",
        return_value=[field],
    ) as llm:
        response = client.post(f"/tasks/{task.id}/map-fields?provider=deepseek")

    assert response.status_code == 200
    llm.assert_called_once_with(task.id, session, provider="deepseek")


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
    assert response.json()["status"] == "READY_TO_FILL"

    session.refresh(task)
    assert task.status == "READY_TO_FILL"


def test_manual_mapping_correction_skips_llm_call_for_same_form(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)

    response = client.put(
        f"/tasks/{task.id}/fields/{field.id}",
        json={"mapped_profile_key": "email"},
    )

    assert response.status_code == 200

    second_profile = Profile(
        profile_name="Second endpoint profile",
        full_name="Grace Hopper",
        email="grace@example.com",
    )
    second_task = Task(
        url="https://example.com/form",
        profile=second_profile,
        status="MAPPING_READY",
    )
    second_field = FormField(
        task=second_task,
        label="Where can we reach you?",
        selector="#contact",
        field_type="email",
        required=True,
    )
    session.add(second_task)
    session.add(second_field)
    session.commit()

    llm_json = json.dumps(
        {
            "mappings": [
                {
                    "field_id": second_field.id,
                    "mapped_profile_key": "email",
                    "confidence": 0.93,
                }
            ]
        }
    )

    with patch(
        "app.services.field_mapper._request_llm_mapping",
        return_value=llm_json,
    ) as request_mapping:
        mapped = map_fields_with_llm(second_task.id, session, provider="deepseek")

    request_mapping.assert_not_called()
    assert mapped[0].mapped_profile_key == "email"
    assert mapped[0].mapped_value == "grace@example.com"
    assert mapped[0].confidence == 1.0


def test_manual_value_can_be_saved_to_profile_custom_value_and_reused(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Preferred work location"
    field.selector = "#location"
    field.field_type = "text"
    session.commit()

    response = client.put(
        f"/tasks/{task.id}/fields/{field.id}",
        json={
            "mapped_value": "Shanghai",
            "save_to_profile": True,
            "profile_custom_key": "preferred_location",
        },
    )

    assert response.status_code == 200
    assert response.json()["mapped_profile_key"] == "custom:preferred_location"
    assert response.json()["mapped_value"] == "Shanghai"

    session.refresh(task.profile)
    assert task.profile.custom_values == {"preferred_location": "Shanghai"}

    second_task = Task(
        url="https://example.com/form",
        profile=task.profile,
        status="MAPPING_READY",
    )
    second_field = FormField(
        task=second_task,
        label="Preferred work location",
        selector="#location",
        field_type="text",
        required=True,
    )
    session.add(second_task)
    session.add(second_field)
    session.commit()

    with patch("app.services.field_mapper._request_llm_mapping") as request_mapping:
        mapped = map_fields_with_llm(second_task.id, session, provider="deepseek")

    request_mapping.assert_not_called()
    assert mapped[0].mapped_profile_key == "custom:preferred_location"
    assert mapped[0].mapped_value == "Shanghai"
    assert mapped[0].confidence == 1.0


def test_fill_rejects_missing_required_values_before_browser_work(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    task.status = "READY_TO_FILL"
    field.mapped_profile_key = "email"
    field.mapped_value = None
    session.commit()

    response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert "Required fields need values" in response.json()["detail"]


def test_fill_rejects_mapped_fields_before_user_confirms_mapping(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    session.commit()

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as fill_form:
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert response.json() == {"detail": "Review and confirm mapping before filling"}
    fill_form.assert_not_awaited()


def test_analyze_pauses_when_login_is_required(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)

    with (
        patch(
            "app.routers.tasks.extract_form_analysis",
            new=AsyncMock(
                return_value=SimpleNamespace(fields=[], login_required=True),
            ),
        ) as extract_analysis,
        patch("app.routers.tasks.prepare_login_session") as prepare_login,
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    assert response.json()["status"] == "LOGIN_REQUIRED"
    assert response.json()["form_fields"] == []
    assert extract_analysis.await_count == 1
    prepare_login.assert_not_called()

    logs = list(
        session.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step)
        )
    )
    assert [log.action for log in logs] == ["analyze_form", "login_required"]
    assert logs[-1].status == "WAITING"


def test_analyze_reuses_cached_form_analysis_for_same_url(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    first_task = create_task_without_fields(session)
    second_task = create_task_without_fields(session)
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ) as extract_analysis:
        first_response = client.post(f"/tasks/{first_task.id}/analyze")
        second_response = client.post(f"/tasks/{second_task.id}/analyze")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert extract_analysis.await_count == 1
    assert first_response.json()["form_fields"][0]["selector"] == "#email"
    assert second_response.json()["form_fields"][0]["selector"] == "#email"


def test_login_and_analyze_retries_original_url_after_manual_login(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)
    task.status = "LOGIN_REQUIRED"
    session.commit()
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
        options=[],
    )

    with (
        patch(
            "app.routers.tasks.prepare_login_session",
            new=AsyncMock(return_value=("browser-session", False)),
        ) as prepare_login,
        patch(
            "app.routers.tasks.extract_form_analysis",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    fields=[extracted_field],
                    login_required=False,
                ),
            ),
        ) as extract_analysis,
    ):
        response = client.post(f"/tasks/{task.id}/login-and-analyze")

    assert response.status_code == 200
    assert response.json()["status"] == "MAPPING_READY"
    assert response.json()["form_fields"][0]["selector"] == "#email"
    prepare_login.assert_awaited_once_with(
        url=task.url,
        profile_id=task.profile_id,
    )
    extract_analysis.assert_awaited_once_with(task.url, task.profile_id)

    logs = list(
        session.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step)
        )
    )
    assert [log.action for log in logs] == [
        "manual_login",
        "resume_after_login",
        "extract_fields",
    ]


def test_analyze_persists_field_options_for_review(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Application",
        section_title="Preferences",
        label="Preferred location",
        selector="#remote",
        field_type="radio",
        placeholder=None,
        name="location",
        html_id="remote",
        current_value=None,
        required=True,
        options=[
            {"label": "Remote", "value": "remote", "selector": "#remote"},
            {"label": "Office", "value": "office", "selector": "#office"},
        ],
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    assert response.json()["form_fields"][0]["options"] == [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
        {"label": "Office", "value": "office", "selector": "#office"},
    ]

    saved_field = session.get(FormField, response.json()["form_fields"][0]["id"])
    assert saved_field is not None
    assert saved_field.options == [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
        {"label": "Office", "value": "office", "selector": "#office"},
    ]


def test_list_screenshots_omits_missing_files(
    test_environment: tuple[TestClient, Session],
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)
    screenshots_dir = tmp_path / "screenshots"
    screenshots_dir.mkdir()
    existing_file = screenshots_dir / "existing.png"
    existing_file.write_bytes(b"image")
    monkeypatch.setattr("app.routers.tasks.BACKEND_DIR", tmp_path, raising=False)

    session.add_all(
        [
            Screenshot(
                task_id=task.id,
                file_path="screenshots/missing.png",
                stage="missing",
            ),
            Screenshot(
                task_id=task.id,
                file_path="screenshots/existing.png",
                stage="existing",
            ),
        ]
    )
    session.commit()

    response = client.get(f"/tasks/{task.id}/screenshots")

    assert response.status_code == 200
    assert [item["stage"] for item in response.json()] == ["existing"]
