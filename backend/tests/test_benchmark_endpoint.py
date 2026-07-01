"""Tests for benchmark run API endpoints."""

import json
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import BenchmarkCaseResult, BenchmarkRun
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


def _persist_summary(session: Session, summary: BenchmarkRunSummary) -> None:
    run = BenchmarkRun(
        mode=summary.mode,
        provider=summary.provider,
        total_cases=summary.total_cases,
        average_score=summary.average_score,
        summary_metrics_json=json.dumps(summary.summary_metrics),
    )
    session.add(run)
    session.flush()
    for result in summary.case_results:
        session.add(
            BenchmarkCaseResult(
                run_id=run.id,
                case_id=result["case_id"],
                title=result["title"],
                metrics_json=json.dumps(result["metrics"]),
                failures_json=json.dumps(result["failures"]),
            )
        )
    session.commit()


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

    def fake_run_benchmarks(*, mode: str, provider: str | None, db: Session) -> BenchmarkRunSummary:
        assert mode == "rules"
        assert provider is None
        _persist_summary(db, summary)
        return summary

    with patch("app.routers.benchmarks.run_benchmarks", side_effect=fake_run_benchmarks):
        response = client.post("/benchmarks/run")

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "rules"
    assert body["provider"] is None
    assert body["total_cases"] == 1
    assert body["case_results"][0]["case_id"] == "case_1"

    list_response = client.get("/benchmarks/runs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["average_score"] == 0.75

    detail_response = client.get(f"/benchmarks/runs/{body['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["case_results"][0]["failures"][0]["selector"] == "#email"


def test_run_benchmark_rules_mode_succeeds(test_environment: tuple[TestClient, Session]) -> None:
    client, session = test_environment
    summary = BenchmarkRunSummary(
        mode="rules",
        provider=None,
        total_cases=0,
        average_score=1.0,
        summary_metrics={},
        case_results=[],
    )

    def fake_run_benchmarks(*, mode: str, provider: str | None, db: Session) -> BenchmarkRunSummary:
        assert mode == "rules"
        assert provider is None
        _persist_summary(db, summary)
        return summary

    with patch("app.routers.benchmarks.run_benchmarks", side_effect=fake_run_benchmarks):
        response = client.post("/benchmarks/run", json={"mode": "rules", "provider": "openai"})

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "rules"
    assert body["provider"] is None

    persisted = session.query(BenchmarkRun).order_by(BenchmarkRun.id.desc()).first()
    assert persisted is not None
    assert persisted.mode == "rules"
    assert persisted.provider is None


def test_run_benchmark_empty_body_defaults_to_rules(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, _ = test_environment
    summary = BenchmarkRunSummary(
        mode="rules",
        provider=None,
        total_cases=0,
        average_score=1.0,
        summary_metrics={},
        case_results=[],
    )

    def fake_run_benchmarks(*, mode: str, provider: str | None, db: Session) -> BenchmarkRunSummary:
        assert mode == "rules"
        assert provider is None
        _persist_summary(db, summary)
        return summary

    with patch("app.routers.benchmarks.run_benchmarks", side_effect=fake_run_benchmarks):
        response = client.post("/benchmarks/run")

    assert response.status_code == 201
    assert response.json()["mode"] == "rules"


def test_run_benchmark_llm_without_provider_fails(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, _ = test_environment
    response = client.post("/benchmarks/run", json={"mode": "llm"})
    assert response.status_code == 400


def test_run_benchmark_llm_with_unconfigured_provider_returns_409(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, _ = test_environment

    with (
        patch("app.routers.benchmarks.resolve_llm_provider", return_value="openai"),
        patch("app.routers.benchmarks.is_provider_configured", return_value=False),
        patch("app.routers.benchmarks.get_provider_setup_hint", return_value="Set OPENAI_API_KEY"),
        patch("app.routers.benchmarks.run_benchmarks") as mocked_runner,
    ):
        response = client.post("/benchmarks/run", json={"mode": "llm", "provider": "openai"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Set OPENAI_API_KEY"
    mocked_runner.assert_not_called()


def test_run_benchmark_llm_with_configured_provider_calls_runner(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, _ = test_environment
    summary = BenchmarkRunSummary(
        mode="llm",
        provider="openai",
        total_cases=0,
        average_score=1.0,
        summary_metrics={},
        case_results=[],
    )

    def fake_run_benchmarks(*, mode: str, provider: str | None, db: Session) -> BenchmarkRunSummary:
        assert mode == "llm"
        assert provider == "openai"
        _persist_summary(db, summary)
        return summary

    with (
        patch("app.routers.benchmarks.resolve_llm_provider", return_value="openai"),
        patch("app.routers.benchmarks.is_provider_configured", return_value=True),
        patch("app.routers.benchmarks.run_benchmarks", side_effect=fake_run_benchmarks) as mocked_runner,
    ):
        response = client.post("/benchmarks/run", json={"mode": "llm", "provider": "openai"})

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "llm"
    assert body["provider"] == "openai"
    assert mocked_runner.call_args.kwargs["mode"] == "llm"
    assert mocked_runner.call_args.kwargs["provider"] == "openai"
    assert mocked_runner.call_args.kwargs["db"] is not None

