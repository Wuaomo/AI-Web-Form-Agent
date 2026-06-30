"""Tests for LLM usage reporting endpoints."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import LlmApiUsageLog, Profile, Task
from app.routers.llm_usage import router as llm_usage_router
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
    test_app.include_router(llm_usage_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_task(session: Session) -> Task:
    """Create a task for usage reporting tests."""

    profile = Profile(profile_name="Usage profile")
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="MAPPING_READY",
    )
    session.add(task)
    session.commit()
    return task


def create_usage_log(
    session: Session,
    task_id: int,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int,
    cache_miss_tokens: int,
) -> None:
    """Persist one usage record for endpoint tests."""

    session.add(
        LlmApiUsageLog(
            task_id=task_id,
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            cache_hit=cache_hit_tokens > 0,
            cache_hit_rate=(
                cache_hit_tokens / prompt_tokens if prompt_tokens else 0
            ),
        )
    )
    session.commit()


def test_task_llm_usage_returns_items_and_summary(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session)
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=60,
        cache_miss_tokens=40,
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=50,
        completion_tokens=10,
        cache_hit_tokens=0,
        cache_miss_tokens=50,
    )

    response = client.get(f"/tasks/{task.id}/llm-usage")

    assert response.status_code == 200
    assert response.json()["summary"] == {
        "task_id": task.id,
        "request_count": 2,
        "prompt_tokens": 150,
        "completion_tokens": 30,
        "total_tokens": 180,
        "cache_hit_tokens": 60,
        "cache_miss_tokens": 90,
        "cache_hit_rate": 0.4,
    }
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0]["provider"] == "deepseek"


def test_global_llm_usage_summary_aggregates_all_tasks(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    first_task = create_task(session)
    second_task = create_task(session)
    create_usage_log(
        session,
        first_task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=50,
        cache_miss_tokens=50,
    )
    create_usage_log(
        session,
        second_task.id,
        prompt_tokens=200,
        completion_tokens=40,
        cache_hit_tokens=100,
        cache_miss_tokens=100,
    )

    response = client.get("/llm-usage/summary")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": None,
        "request_count": 2,
        "prompt_tokens": 300,
        "completion_tokens": 60,
        "total_tokens": 360,
        "cache_hit_tokens": 150,
        "cache_miss_tokens": 150,
        "cache_hit_rate": 0.5,
    }
