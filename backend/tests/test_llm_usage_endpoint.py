"""Tests for per-task LLM usage reporting."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import LLMApiUsageLog, Profile, Task
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


def test_list_task_llm_usage_returns_usage_rows(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    profile = Profile(profile_name="Usage profile", email="ada@example.com")
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="MAPPING_READY",
    )
    session.add(task)
    session.commit()
    usage_log = LLMApiUsageLog(
        task_id=task.id,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_tokens=979,
        completion_tokens=197,
        total_tokens=1176,
        cache_hit_tokens=0,
        cache_miss_tokens=979,
        cache_hit=False,
        cache_hit_rate=0.0,
    )
    session.add(usage_log)
    session.commit()

    response = client.get(f"/tasks/{task.id}/llm-usage")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": usage_log.id,
            "task_id": task.id,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "prompt_tokens": 979,
            "completion_tokens": 197,
            "total_tokens": 1176,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 979,
            "cache_hit": False,
            "cache_hit_rate": 0.0,
            "created_at": usage_log.created_at.isoformat(),
        }
    ]


def test_list_task_llm_usage_returns_404_for_missing_task(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, _ = test_environment

    response = client.get("/tasks/999/llm-usage")

    assert response.status_code == 404
