"""Tests for benchmark run API endpoints."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.routers.benchmarks import router as benchmarks_router
from app.services.benchmark_runner import BenchmarkRunSummary


@pytest.fixture
def test_environment() -> Generator[tuple[TestClient, Session], None, None]:
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
    test_app.include_router(benchmarks_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_run_benchmark_persists_and_returns_results(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, _ = test_environment
    summary = BenchmarkRunSummary(
        mode="rules",
        provider=None,
        total_cases=1,
        average_score=0.75,
        summary_metrics={"mapping_accuracy": 0.5},
        case_results=[
            {
                "case_id": "case_1",
                "title": "Case one",
                "metrics": {"mapping_accuracy": 0.5},
                "failures": [
                    {
                        "selector": "#email",
                        "expected_profile_key": "email",
                        "actual_profile_key": "phone",
                        "reason": "profile_key_mismatch",
                    }
                ],
            }
        ],
    )

    with patch(
        "app.routers.benchmarks.run_benchmarks",
        return_value=summary,
    ):
        response = client.post("/benchmarks/run")

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "rules"
    assert body["total_cases"] == 1
    assert body["case_results"][0]["case_id"] == "case_1"

    list_response = client.get("/benchmarks/runs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["average_score"] == 0.75

    detail_response = client.get(f"/benchmarks/runs/{body['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["case_results"][0]["failures"][0]["selector"] == "#email"

