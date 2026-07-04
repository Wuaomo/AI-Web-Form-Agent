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
    latency_ms: int = 0,
    fallback_used: bool = False,
    estimated_cost: float = 0.0,
    provider: str = "deepseek",
    model: str = "deepseek-v4-flash",
) -> None:
    """Persist one usage record for endpoint tests."""

    session.add(
        LlmApiUsageLog(
            task_id=task_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            cache_hit=cache_hit_tokens > 0,
            cache_hit_rate=(
                cache_hit_tokens / prompt_tokens if prompt_tokens else 0
            ),
            latency_ms=latency_ms,
            fallback_used=fallback_used,
            estimated_cost=estimated_cost,
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
    summary = response.json()["summary"]
    assert summary["task_id"] == task.id
    assert summary["request_count"] == 2
    assert summary["prompt_tokens"] == 150
    assert summary["completion_tokens"] == 30
    assert summary["total_tokens"] == 180
    assert summary["cache_hit_tokens"] == 60
    assert summary["cache_miss_tokens"] == 90
    assert summary["cache_hit_rate"] == 0.4
    assert summary["average_latency_ms"] == 0
    assert summary["p95_latency_ms"] == 0
    assert summary["fallback_count"] == 0
    assert summary["estimated_cost"] == 0.0
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
    summary = response.json()
    assert summary["task_id"] == None
    assert summary["request_count"] == 2
    assert summary["prompt_tokens"] == 300
    assert summary["completion_tokens"] == 60
    assert summary["total_tokens"] == 360
    assert summary["cache_hit_tokens"] == 150
    assert summary["cache_miss_tokens"] == 150
    assert summary["cache_hit_rate"] == 0.5
    assert summary["average_latency_ms"] == 0
    assert summary["p95_latency_ms"] == 0
    assert summary["fallback_count"] == 0
    assert summary["estimated_cost"] == 0.0


def test_llm_usage_summary_calculates_average_latency(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session)
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        latency_ms=1000,
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        latency_ms=2000,
    )

    response = client.get("/llm-usage/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["average_latency_ms"] == 1500


def test_llm_usage_summary_calculates_p95_latency(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session)
    for i in range(20):
        create_usage_log(
            session,
            task.id,
            prompt_tokens=100,
            completion_tokens=20,
            cache_hit_tokens=0,
            cache_miss_tokens=100,
            latency_ms=1000 + i * 100,
        )

    response = client.get("/llm-usage/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["p95_latency_ms"] >= 2700


def test_llm_usage_summary_counts_fallback_used(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session)
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        fallback_used=True,
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        fallback_used=False,
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        fallback_used=True,
    )

    response = client.get("/llm-usage/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["fallback_count"] == 2


def test_llm_usage_summary_sums_estimated_cost(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session)
    create_usage_log(
        session,
        task.id,
        prompt_tokens=1000,
        completion_tokens=100,
        cache_hit_tokens=0,
        cache_miss_tokens=1000,
        estimated_cost=0.01,
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=2000,
        completion_tokens=200,
        cache_hit_tokens=0,
        cache_miss_tokens=2000,
        estimated_cost=0.02,
    )

    response = client.get("/llm-usage/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["estimated_cost"] == 0.03


def test_provider_llm_usage_groups_by_provider_and_model(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session)
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=50,
        cache_miss_tokens=50,
        provider="deepseek",
        model="deepseek-v4-flash",
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=200,
        completion_tokens=40,
        cache_hit_tokens=100,
        cache_miss_tokens=100,
        provider="deepseek",
        model="deepseek-v4-flash",
    )
    create_usage_log(
        session,
        task.id,
        prompt_tokens=100,
        completion_tokens=20,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        provider="openai",
        model="gpt-4o-mini",
    )

    response = client.get("/llm-usage/providers")

    assert response.status_code == 200
    providers = response.json()
    assert len(providers) == 2

    deepseek_summary = next(p for p in providers if p["provider"] == "deepseek")
    assert deepseek_summary["model"] == "deepseek-v4-flash"
    assert deepseek_summary["request_count"] == 2
    assert deepseek_summary["cache_hit_rate"] == 0.5

    openai_summary = next(p for p in providers if p["provider"] == "openai")
    assert openai_summary["model"] == "gpt-4o-mini"
    assert openai_summary["request_count"] == 1
    assert openai_summary["cache_hit_rate"] == 0.0


def test_provider_llm_usage_returns_empty_list_when_no_data(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment

    response = client.get("/llm-usage/providers")

    assert response.status_code == 200
    assert response.json() == []
