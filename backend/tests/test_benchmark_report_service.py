"""Tests for benchmark markdown report generation."""

import json
from datetime import datetime, timezone

import pytest

from app.models import BenchmarkRun, BenchmarkCaseResult
from app.services.benchmark_report_service import build_benchmark_markdown_report


def test_report_includes_run_id() -> None:
    run = BenchmarkRun(
        id=42,
        mode="rules",
        provider=None,
        total_cases=1,
        average_score=0.9,
        summary_metrics_json=json.dumps({}),
        duration_ms=1234,
        regression_count=0,
        improvement_count=0,
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    report = build_benchmark_markdown_report(run)

    assert "# Benchmark Run #42" in report


def test_report_includes_failed_case_title() -> None:
    run = BenchmarkRun(
        id=1,
        mode="rules",
        provider=None,
        total_cases=2,
        average_score=0.5,
        summary_metrics_json=json.dumps({}),
        duration_ms=500,
        regression_count=0,
        improvement_count=0,
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    run.case_results = [
        BenchmarkCaseResult(
            id=1,
            run_id=1,
            case_id="case_1",
            title="Test Case One",
            metrics_json=json.dumps({}),
            failures_json=json.dumps([{"selector": "#name", "reason": "field_not_extracted"}]),
        ),
        BenchmarkCaseResult(
            id=2,
            run_id=1,
            case_id="case_2",
            title="Test Case Two",
            metrics_json=json.dumps({}),
            failures_json=json.dumps([]),
        ),
    ]

    report = build_benchmark_markdown_report(run)

    assert "### Test Case One" in report


def test_report_includes_all_sections() -> None:
    run = BenchmarkRun(
        id=1,
        mode="llm",
        provider="openai",
        mode_detail="stress_mode=cache_warm;memory_mode=on",
        total_cases=3,
        average_score=0.85,
        summary_metrics_json=json.dumps({
            "field_extraction_recall": 0.9,
            "mapping_accuracy": 0.8,
            "llm_fallback_count": 1,
        }),
        duration_ms=3000,
        regression_count=1,
        improvement_count=2,
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    report = build_benchmark_markdown_report(run)

    assert "## Run Summary" in report
    assert "## Summary Metrics" in report
    assert "## Regression Summary" in report
    assert "**Memory Mode:** on" in report


def test_report_formats_duration_correctly() -> None:
    run_short = BenchmarkRun(
        id=1,
        mode="rules",
        provider=None,
        total_cases=1,
        average_score=1.0,
        summary_metrics_json=json.dumps({}),
        duration_ms=500,
        regression_count=0,
        improvement_count=0,
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    report_short = build_benchmark_markdown_report(run_short)
    assert "500ms" in report_short

    run_long = BenchmarkRun(
        id=2,
        mode="rules",
        provider=None,
        total_cases=1,
        average_score=1.0,
        summary_metrics_json=json.dumps({}),
        duration_ms=2500,
        regression_count=0,
        improvement_count=0,
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    report_long = build_benchmark_markdown_report(run_long)
    assert "2.5s" in report_long


def test_report_includes_top_failure_reasons() -> None:
    run = BenchmarkRun(
        id=1,
        mode="rules",
        provider=None,
        total_cases=1,
        average_score=0.5,
        summary_metrics_json=json.dumps({}),
        duration_ms=500,
        regression_count=0,
        improvement_count=0,
        created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    run.case_results = [
        BenchmarkCaseResult(
            id=1,
            run_id=1,
            case_id="case_1",
            title="Test Case",
            metrics_json=json.dumps({}),
            failures_json=json.dumps([
                {"selector": "#name", "reason": "field_not_extracted"},
                {"selector": "#email", "reason": "wrong_profile_key"},
                {"selector": "#phone", "reason": "field_not_extracted"},
            ]),
        ),
    ]

    report = build_benchmark_markdown_report(run)

    assert "## Top Failure Reasons" in report
    assert "Field Not Extracted" in report
    assert "Wrong Profile Key" in report
