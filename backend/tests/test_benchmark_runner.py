"""Tests for benchmark case loading and metric scoring."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, LlmApiUsageLog, Profile, Task
from app.services.benchmark_runner import (
    BenchmarkCase,
    SUMMARY_METRIC_KEYS,
    load_benchmark_cases,
    run_benchmarks,
    score_case,
    _run_case,
)


def test_load_benchmark_cases_reads_all_expected_files() -> None:
    cases = load_benchmark_cases()

    assert len(cases) == 15
    assert cases[0].case_id == "01_clear_student_registration"
    assert cases[0].html_path.name == "01_clear_student_registration.html"
    assert cases[0].expected["login_required"] is False


def test_score_case_calculates_extraction_mapping_and_login_metrics() -> None:
    expected = {
        "login_required": False,
        "fields": [
            {"selector": "#name", "profile_key": "full_name", "required": True},
            {"selector": "#email", "profile_key": "email", "required": True},
            {"selector": "#submit", "profile_key": None, "required": False},
        ],
    }
    actual = {
        "login_required": False,
        "fields": [
            {"selector": "#name", "profile_key": "full_name", "required": True},
            {"selector": "#email", "profile_key": "phone", "required": True},
            {"selector": "#extra", "profile_key": "github", "required": False},
        ],
        "llm_fallback_count": 1,
        "fill_success": True,
    }

    result = score_case(expected, actual)

    assert result["metrics"]["field_extraction_recall"] == 2 / 3
    assert result["metrics"]["field_extraction_precision"] == 2 / 3
    assert result["metrics"]["mapping_accuracy"] == 1 / 2
    assert result["metrics"]["required_field_coverage"] == 1.0
    assert result["metrics"]["login_detection_accuracy"] == 1.0
    assert result["metrics"]["non_fillable_rejection_rate"] == 1.0
    assert result["metrics"]["fill_success_rate"] == 1.0
    assert result["metrics"]["llm_fallback_count"] == 1
    assert result["failures"] == [
        {
            "selector": "#email",
            "expected_profile_key": "email",
            "actual_profile_key": "phone",
            "reason": "wrong_profile_key",
            "detail": 'Expected "email" but mapped to "phone".',
        },
        {
            "selector": "#submit",
            "expected_profile_key": None,
            "actual_profile_key": None,
            "reason": "field_not_extracted",
            "detail": 'Expected selector "#submit" to be extracted.',
        },
    ]


def test_score_case_emits_stable_failure_reasons_with_details() -> None:
    expected = {
        "login_required": False,
        "fields": [
            {"selector": "#email", "profile_key": "email", "required": True},
            {"selector": "#phone", "profile_key": "phone", "required": True},
            {"selector": "#submit", "profile_key": None, "required": False},
        ],
    }
    actual = {
        "login_required": False,
        "fields": [
            {"selector": "#email", "profile_key": "full_name", "required": True},
            {"selector": "#submit", "profile_key": "linkedin", "required": False},
        ],
        "llm_fallback_count": 0,
        "fill_success": True,
    }

    result = score_case(expected, actual)

    failures = result["failures"]
    assert {failure["reason"] for failure in failures} == {
        "field_not_extracted",
        "wrong_profile_key",
        "action_field_should_skip",
    }

    failures_by_selector = {failure["selector"]: failure for failure in failures}
    assert failures_by_selector["#phone"]["reason"] == "field_not_extracted"
    assert isinstance(failures_by_selector["#phone"]["detail"], str)
    assert failures_by_selector["#email"]["reason"] == "wrong_profile_key"
    assert isinstance(failures_by_selector["#email"]["detail"], str)
    assert failures_by_selector["#submit"]["reason"] == "action_field_should_skip"
    assert isinstance(failures_by_selector["#submit"]["detail"], str)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_run_benchmarks_rules_mode_produces_expected_metrics() -> None:
    case = BenchmarkCase(
        case_id="case_1",
        title="Case one",
        html_path=Path("case_1.html"),
        expected={
            "login_required": False,
            "fields": [
                {"selector": "#name", "profile_key": "full_name", "required": True},
                {"selector": "#email", "profile_key": "email", "required": True},
                {"selector": "#submit", "profile_key": None, "required": False},
            ],
        },
    )

    raw_fields = [
        {"selector": "#name", "label": "Name", "field_type": "text", "required": True},
        {"selector": "#email", "label": "Email", "field_type": "email", "required": True},
        {"selector": "#submit", "label": "Submit", "field_type": "submit", "required": False},
    ]

    def fake_match(field: FormField):
        if field.selector == "#name":
            return ("full_name", 1.0)
        if field.selector == "#email":
            return ("email", 1.0)
        return None

    with (
        patch("app.services.benchmark_runner.load_benchmark_cases", return_value=[case]),
        patch("app.services.benchmark_runner._extract_case_page_state", return_value=(raw_fields, False)),
        patch("app.services.benchmark_runner._match_profile_key", side_effect=fake_match),
    ):
        summary = run_benchmarks(mode="rules")

    assert summary.mode == "rules"
    assert summary.provider is None
    assert summary.total_cases == 1
    assert summary.summary_metrics["mapping_accuracy"] == 1.0
    assert summary.summary_metrics["required_field_coverage"] == 1.0
    assert summary.summary_metrics["login_detection_accuracy"] == 1.0


def test_run_benchmarks_averages_all_summary_metrics() -> None:
    case_one = BenchmarkCase(
        case_id="case_1",
        title="Case one",
        html_path=Path("case_1.html"),
        expected={
            "login_required": False,
            "fields": [
                {"selector": "#name", "profile_key": "full_name", "required": True},
                {"selector": "#email", "profile_key": "email", "required": True},
                {"selector": "#submit", "profile_key": None, "required": False},
            ],
        },
    )
    case_two = BenchmarkCase(
        case_id="case_2",
        title="Case two",
        html_path=Path("case_2.html"),
        expected={
            "login_required": False,
            "fields": [
                {"selector": "#name", "profile_key": "full_name", "required": True},
                {"selector": "#email", "profile_key": "email", "required": True},
                {"selector": "#submit", "profile_key": None, "required": False},
            ],
        },
    )

    actual_results = [
        {
            "login_required": False,
            "fill_success": True,
            "llm_fallback_count": 0,
            "fields": [
                {"selector": "#name", "profile_key": "full_name", "required": True},
                {"selector": "#email", "profile_key": "email", "required": True},
                {"selector": "#submit", "profile_key": None, "required": False},
            ],
        },
        {
            "login_required": True,
            "fill_success": False,
            "llm_fallback_count": 2,
            "fields": [
                {"selector": "#name", "profile_key": "full_name", "required": True},
                {"selector": "#email", "profile_key": "phone", "required": True},
            ],
        },
    ]

    with (
        patch("app.services.benchmark_runner.load_benchmark_cases", return_value=[case_one, case_two]),
        patch("app.services.benchmark_runner._run_case", side_effect=actual_results),
    ):
        summary = run_benchmarks(mode="rules")

    assert set(summary.summary_metrics) == set(SUMMARY_METRIC_KEYS)
    assert summary.summary_metrics["field_extraction_recall"] == pytest.approx(5 / 6)
    assert summary.summary_metrics["field_extraction_precision"] == pytest.approx(1.0)
    assert summary.summary_metrics["mapping_accuracy"] == pytest.approx(0.75)
    assert summary.summary_metrics["required_field_coverage"] == pytest.approx(1.0)
    assert summary.summary_metrics["non_fillable_rejection_rate"] == pytest.approx(1.0)
    assert summary.summary_metrics["login_detection_accuracy"] == pytest.approx(0.5)
    assert summary.summary_metrics["fill_success_rate"] == pytest.approx(0.5)
    assert summary.summary_metrics["llm_fallback_count"] == pytest.approx(1.0)


def test_run_benchmarks_rules_mode_has_stable_summary_and_case_result_shape() -> None:
    cases = [
        BenchmarkCase(
            case_id="case_1",
            title="Case one",
            html_path=Path("case_1.html"),
            expected={"login_required": False, "fields": []},
        ),
        BenchmarkCase(
            case_id="case_2",
            title="Case two",
            html_path=Path("case_2.html"),
            expected={"login_required": False, "fields": []},
        ),
    ]

    fake_results = [
        {
            "login_required": False,
            "fill_success": True,
            "llm_fallback_count": 0,
            "fields": [{"selector": "#name", "profile_key": "full_name", "required": True}],
        },
        {
            "login_required": False,
            "fill_success": True,
            "llm_fallback_count": 0,
            "fields": [{"selector": "#email", "profile_key": "email", "required": True}],
        },
    ]

    with (
        patch("app.services.benchmark_runner.load_benchmark_cases", return_value=cases),
        patch("app.services.benchmark_runner._run_case", side_effect=fake_results),
    ):
        summary = run_benchmarks(mode="rules")

    assert summary.total_cases == 2
    assert isinstance(summary.average_score, float)
    assert isinstance(summary.summary_metrics, dict)
    assert set(summary.summary_metrics) == set(SUMMARY_METRIC_KEYS)
    assert isinstance(summary.case_results, list)
    assert len(summary.case_results) == 2

    for result in summary.case_results:
        assert "case_id" in result
        assert "title" in result
        assert "metrics" in result
        assert "failures" in result
        assert isinstance(result["failures"], list)

def test_run_case_llm_mode_calls_map_fields_with_llm(db_session: Session) -> None:
    case = BenchmarkCase(
        case_id="case_1",
        title="Case one",
        html_path=Path("case_1.html"),
        expected={"login_required": False, "fields": []},
    )
    raw_fields = [
        {"selector": "#email", "label": "Email", "field_type": "email", "required": True},
    ]

    def fake_map_fields_with_llm(task_id: int, db: Session, provider: str):
        fields = list(
            db.scalars(
                select(FormField).where(FormField.task_id == task_id).order_by(FormField.id)
            )
        )
        for field in fields:
            field.mapped_profile_key = "email"
        return fields

    with (
        patch("app.services.benchmark_runner._extract_case_page_state", return_value=(raw_fields, False)),
        patch("app.services.benchmark_runner.map_fields_with_llm", side_effect=fake_map_fields_with_llm) as mocked_map,
    ):
        _run_case(case, mode="llm", provider="deepseek", db=db_session)

    assert mocked_map.call_args.kwargs["provider"] == "deepseek"


def test_run_case_llm_mode_converts_mapped_fields_to_actual_shape(db_session: Session) -> None:
    case = BenchmarkCase(
        case_id="case_1",
        title="Case one",
        html_path=Path("case_1.html"),
        expected={"login_required": False, "fields": []},
    )
    raw_fields = [
        {"selector": "#name", "label": "Name", "field_type": "text", "required": True},
        {"selector": "#submit", "label": "Submit", "field_type": "submit", "required": False},
    ]

    def fake_map_fields_with_llm(task_id: int, db: Session, provider: str):
        fields = list(
            db.scalars(
                select(FormField).where(FormField.task_id == task_id).order_by(FormField.id)
            )
        )
        for field in fields:
            field.mapped_profile_key = "full_name" if field.selector == "#name" else None
        return fields

    with (
        patch("app.services.benchmark_runner._extract_case_page_state", return_value=(raw_fields, False)),
        patch("app.services.benchmark_runner.map_fields_with_llm", side_effect=fake_map_fields_with_llm),
    ):
        actual = _run_case(case, mode="llm", provider="openai", db=db_session)

    assert actual["fields"] == [
        {"selector": "#name", "profile_key": "full_name", "required": True},
        {"selector": "#submit", "profile_key": None, "required": False},
    ]


def test_run_case_llm_mode_cleans_up_temporary_rows(db_session: Session) -> None:
    case = BenchmarkCase(
        case_id="case_1",
        title="Case one",
        html_path=Path("case_1.html"),
        expected={"login_required": False, "fields": []},
    )
    raw_fields = [
        {"selector": "#email", "label": "Email", "field_type": "email", "required": True},
    ]

    def fake_map_fields_with_llm(task_id: int, db: Session, provider: str):
        fields = list(
            db.scalars(
                select(FormField).where(FormField.task_id == task_id).order_by(FormField.id)
            )
        )
        for field in fields:
            field.mapped_profile_key = "email"
        return fields

    with (
        patch("app.services.benchmark_runner._extract_case_page_state", return_value=(raw_fields, False)),
        patch("app.services.benchmark_runner.map_fields_with_llm", side_effect=fake_map_fields_with_llm),
    ):
        _run_case(case, mode="llm", provider="openai", db=db_session)

    assert db_session.query(FormField).count() == 0
    assert db_session.query(Task).count() == 0
    assert db_session.query(Profile).count() == 0
    assert db_session.query(LlmApiUsageLog).count() == 0

