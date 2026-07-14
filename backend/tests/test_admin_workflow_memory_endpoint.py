"""Tests for admin workflow memory governance endpoints."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base, get_db
from app.models import WorkflowMemoryItem
from app.routers.admin import router as admin_router
from app.services.retrieval_service import MEMORY_STALE_AFTER_DAYS
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING


@pytest.fixture
def test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    monkeypatch.setattr(config, "ADMIN_API_TOKEN", "secret")

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    test_app = FastAPI()
    test_app.include_router(admin_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_list_workflow_memory_shows_stale_governance(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=MEMORY_STALE_AFTER_DAYS + 1)
    item = WorkflowMemoryItem(
        memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
        workflow_type="form_fill",
        source_domain="example.com",
        field_signature="sig_portfolio",
        field_text="label: Portfolio URL\nname: portfolio\ntype: url\noptions: []",
        mapped_profile_key="github",
        created_at=old_timestamp,
        last_used_at=old_timestamp,
    )
    session.add(item)
    session.commit()

    response = client.get(
        "/admin/workflow-memory",
        headers={"X-Admin-Token": "secret"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == item.id
    assert response.json()[0]["mapped_profile_key"] == "github"
    assert response.json()[0]["source_domain"] == "example.com"
    assert response.json()[0]["source_type"] == "reviewed_memory"
    assert response.json()[0]["stale"] is True
    assert response.json()[0]["governance_status"] == "stale_review_recommended"


def test_delete_workflow_memory_removes_item(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    item = WorkflowMemoryItem(
        memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
        workflow_type="form_fill",
        source_domain="example.com",
        field_signature="sig_portfolio",
        field_text="label: Portfolio URL\nname: portfolio\ntype: url\noptions: []",
        mapped_profile_key="github",
    )
    session.add(item)
    session.commit()

    response = client.delete(
        f"/admin/workflow-memory/{item.id}",
        headers={"X-Admin-Token": "secret"},
    )

    assert response.status_code == 204
    assert session.get(WorkflowMemoryItem, item.id) is None

