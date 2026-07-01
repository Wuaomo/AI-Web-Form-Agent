"""Benchmark case loading, execution, and metric scoring."""

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from playwright.sync_api import sync_playwright
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database import BACKEND_DIR
from app.models import FormField, LlmApiUsageLog, Profile, Task
from app.services.field_mapper import _match_profile_key, map_fields_with_llm
from app.services.form_extractor import _EXTRACT_FIELDS_SCRIPT, _LOGIN_DETECTION_SCRIPT

BENCHMARK_DIR = BACKEND_DIR / "benchmarks"
EXPECTED_DIR = BENCHMARK_DIR / "expected"


@dataclass(frozen=True)
class BenchmarkCase:
    """One benchmark fixture and its expected answers."""

    case_id: str
    title: str
    html_path: Path
    expected: dict[str, Any]


@dataclass(frozen=True)
class BenchmarkRunSummary:
    """Serializable benchmark run result used by API and tests."""

    mode: str
    provider: str | None
    total_cases: int
    average_score: float
    summary_metrics: dict[str, float]
    case_results: list[dict[str, Any]]


def load_benchmark_cases() -> list[BenchmarkCase]:
    """Read benchmark expected files and resolve their local HTML paths."""

    cases: list[BenchmarkCase] = []
    for expected_file in sorted(EXPECTED_DIR.glob("*.json")):
        data = json.loads(expected_file.read_text(encoding="utf-8"))
        html_path = (expected_file.parent / data["html_file"]).resolve()
        cases.append(
            BenchmarkCase(
                case_id=data["case_id"],
                title=data["title"],
                html_path=html_path,
                expected=data["expected"],
            )
        )
    return cases


def _fields_by_selector(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index field dictionaries by selector."""

    return {
        field["selector"]: field
        for field in fields
        if isinstance(field.get("selector"), str)
    }


def _ratio(numerator: int, denominator: int) -> float:
    """Return a zero-safe ratio."""

    return numerator / denominator if denominator else 1.0


def score_case(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    """Compare one actual benchmark result with expected answers."""

    expected_fields = expected.get("fields", [])
    actual_fields = actual.get("fields", [])
    expected_by_selector = _fields_by_selector(expected_fields)
    actual_by_selector = _fields_by_selector(actual_fields)

    expected_selectors = set(expected_by_selector)
    actual_selectors = set(actual_by_selector)
    extracted_expected_selectors = expected_selectors & actual_selectors

    mappable_expected = [
        field
        for field in expected_fields
        if field.get("profile_key") is not None
        and field["selector"] in actual_by_selector
    ]
    correct_mappings = 0
    failures: list[dict[str, Any]] = []
    for expected_field in expected_fields:
        selector = expected_field["selector"]
        expected_profile_key = expected_field.get("profile_key")
        actual_field = actual_by_selector.get(selector)
        actual_profile_key = (
            actual_field.get("profile_key") if actual_field is not None else None
        )

        if actual_field is None:
            failures.append(
                {
                    "selector": selector,
                    "expected_profile_key": expected_profile_key,
                    "actual_profile_key": None,
                    "reason": "missing_extraction",
                }
            )
            continue

        if expected_profile_key is None:
            if actual_profile_key is not None:
                failures.append(
                    {
                        "selector": selector,
                        "expected_profile_key": None,
                        "actual_profile_key": actual_profile_key,
                        "reason": "should_not_map",
                    }
                )
            continue

        if actual_profile_key == expected_profile_key:
            correct_mappings += 1
        else:
            failures.append(
                {
                    "selector": selector,
                    "expected_profile_key": expected_profile_key,
                    "actual_profile_key": actual_profile_key,
                    "reason": "profile_key_mismatch",
                }
            )

    required_expected = [
        field for field in expected_fields if field.get("required") is True
    ]
    required_covered = [
        field
        for field in required_expected
        if field["selector"] in actual_by_selector
    ]
    non_fillable_expected = [
        field for field in expected_fields if field.get("profile_key") is None
    ]
    non_fillable_rejected = [
        field
        for field in non_fillable_expected
        if actual_by_selector.get(field["selector"], {}).get("profile_key") is None
    ]

    metrics = {
        "field_extraction_recall": _ratio(
            len(extracted_expected_selectors),
            len(expected_selectors),
        ),
        "field_extraction_precision": _ratio(
            len(extracted_expected_selectors),
            len(actual_selectors),
        ),
        "mapping_accuracy": _ratio(correct_mappings, len(mappable_expected)),
        "required_field_coverage": _ratio(
            len(required_covered),
            len(required_expected),
        ),
        "non_fillable_rejection_rate": _ratio(
            len(non_fillable_rejected),
            len(non_fillable_expected),
        ),
        "login_detection_accuracy": (
            1.0
            if bool(actual.get("login_required"))
            == bool(expected.get("login_required"))
            else 0.0
        ),
        "fill_success_rate": 1.0 if actual.get("fill_success") else 0.0,
        "llm_fallback_count": int(actual.get("llm_fallback_count", 0)),
    }
    return {"metrics": metrics, "failures": failures}


def _benchmark_profile() -> Profile:
    return Profile(
        profile_name="Benchmark profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="555-0100",
        university="Analytical University",
        major="Computer Science",
        linkedin="https://linkedin.example/ada",
        github="https://github.example/ada",
        self_intro="I build reliable analytical engines.",
    )


def _actual_fields_from_rules(
    raw_fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    profile = _benchmark_profile()
    actual_fields: list[dict[str, Any]] = []
    for raw_field in raw_fields:
        field = FormField(
            task=Task(url="file://benchmark", profile=profile),
            label=raw_field.get("label"),
            selector=raw_field["selector"],
            field_type=raw_field.get("field_type"),
            placeholder=raw_field.get("placeholder"),
            name=raw_field.get("name"),
            html_id=raw_field.get("html_id"),
            form_title=raw_field.get("form_title"),
            section_title=raw_field.get("section_title"),
            required=bool(raw_field.get("required")),
        )
        match = _match_profile_key(field)
        actual_fields.append(
            {
                "selector": raw_field["selector"],
                "profile_key": match[0] if match else None,
                "required": bool(raw_field.get("required")),
            }
        )
    return actual_fields


def _actual_fields_from_llm(
    raw_fields: list[dict[str, Any]],
    provider: str,
    db: Session,
) -> list[dict[str, Any]]:
    profile = _benchmark_profile()
    db.add(profile)
    db.flush()

    task = Task(
        url="file://benchmark",
        description="__benchmark_run__",
        profile_id=profile.id,
        status="CREATED",
    )
    db.add(task)
    db.flush()

    for raw_field in raw_fields:
        field = FormField(
            task_id=task.id,
            label=raw_field.get("label"),
            selector=raw_field["selector"],
            field_type=raw_field.get("field_type"),
            placeholder=raw_field.get("placeholder"),
            name=raw_field.get("name"),
            html_id=raw_field.get("html_id"),
            form_title=raw_field.get("form_title"),
            section_title=raw_field.get("section_title"),
            required=bool(raw_field.get("required")),
        )
        db.add(field)
    db.flush()

    try:
        mapped_fields = map_fields_with_llm(task.id, db=db, provider=provider)
        actual_fields = [
            {
                "selector": field.selector,
                "profile_key": field.mapped_profile_key,
                "required": bool(field.required),
            }
            for field in mapped_fields
        ]
        return actual_fields
    finally:
        db.execute(delete(FormField).where(FormField.task_id == task.id))
        db.execute(delete(LlmApiUsageLog).where(LlmApiUsageLog.task_id == task.id))
        db.execute(delete(Task).where(Task.id == task.id))
        db.execute(delete(Profile).where(Profile.id == profile.id))
        db.commit()


def _extract_case_page_state(case: BenchmarkCase) -> tuple[list[dict[str, Any]], bool]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2200})
        page.goto(case.html_path.as_uri(), wait_until="domcontentloaded")
        raw_fields = page.locator(
            'input:not([type="hidden"]), textarea, select'
        ).evaluate_all(_EXTRACT_FIELDS_SCRIPT)
        login_required = bool(page.evaluate(_LOGIN_DETECTION_SCRIPT))
        browser.close()

    return raw_fields, login_required


def _run_case(
    case: BenchmarkCase,
    *,
    mode: str = "rules",
    provider: str | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Execute one local HTML benchmark fixture."""

    raw_fields, login_required = _extract_case_page_state(case)

    llm_fallback_count = 0
    if mode == "llm":
        if db is None:
            raise ValueError("LLM benchmarks require a database session")
        if not provider:
            raise ValueError("LLM benchmarks require a provider")
        fields = _actual_fields_from_llm(raw_fields, provider, db)
        # TODO: Detect fallback-to-rules inside map_fields_with_llm and record llm_fallback_count.
    else:
        fields = _actual_fields_from_rules(raw_fields)

    return {
        "login_required": login_required,
        "fields": fields,
        "llm_fallback_count": llm_fallback_count,
        "fill_success": True,
    }


def _average_metrics(case_results: list[dict[str, Any]]) -> dict[str, float]:
    """Average numeric metrics across all case results."""

    if not case_results:
        return {}

    metric_names = case_results[0]["metrics"].keys()
    return {
        name: mean(float(result["metrics"][name]) for result in case_results)
        for name in metric_names
    }


def run_benchmarks(
    mode: str = "rules",
    provider: str | None = None,
    db: Session | None = None,
) -> BenchmarkRunSummary:
    """Run all benchmark cases and optionally persist the results."""

    case_results: list[dict[str, Any]] = []
    for case in load_benchmark_cases():
        actual = _run_case(case, mode=mode, provider=provider, db=db)
        scored = score_case(case.expected, actual)
        case_results.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "metrics": scored["metrics"],
                "failures": scored["failures"],
            }
        )

    summary_metrics = _average_metrics(case_results)
    average_score = mean(
        [
            summary_metrics.get("field_extraction_recall", 0.0),
            summary_metrics.get("mapping_accuracy", 0.0),
            summary_metrics.get("required_field_coverage", 0.0),
            summary_metrics.get("login_detection_accuracy", 0.0),
        ]
    )
    summary = BenchmarkRunSummary(
        mode=mode,
        provider=provider,
        total_cases=len(case_results),
        average_score=average_score,
        summary_metrics=summary_metrics,
        case_results=case_results,
    )

    if db is not None:
        from app.models import BenchmarkCaseResult, BenchmarkRun

        run = BenchmarkRun(
            mode=mode,
            provider=provider,
            total_cases=summary.total_cases,
            average_score=summary.average_score,
            summary_metrics_json=json.dumps(summary.summary_metrics),
        )
        db.add(run)
        db.flush()
        for result in case_results:
            db.add(
                BenchmarkCaseResult(
                    run_id=run.id,
                    case_id=result["case_id"],
                    title=result["title"],
                    metrics_json=json.dumps(result["metrics"]),
                    failures_json=json.dumps(result["failures"]),
                )
            )
        db.commit()

    return summary
