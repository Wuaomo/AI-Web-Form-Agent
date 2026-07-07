"""Generate copyable Markdown reports for benchmark runs."""

from collections import Counter
from typing import Any

from app.models import BenchmarkRun


def build_benchmark_markdown_report(run: BenchmarkRun) -> str:
    """Return a copyable Markdown report for one benchmark run."""

    lines: list[str] = []

    lines.append(f"# Benchmark Run #{run.id}")
    lines.append("")
    lines.append(f"**Date:** {run.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"**Mode:** {run.mode}")
    if run.provider:
        lines.append(f"**Provider:** {run.provider}")
    if run.mode_detail:
        detail = _parse_mode_detail(run.mode_detail)
        if "stress_mode" in detail:
            lines.append(f"**Stress Mode:** {detail['stress_mode']}")
        if "memory_mode" in detail:
            lines.append(f"**Memory Mode:** {detail['memory_mode']}")
        if not detail:
            lines.append(f"**Run Detail:** {run.mode_detail}")
    lines.append(f"**Duration:** {_format_duration(run.duration_ms)}")
    lines.append("")

    lines.append("## Run Summary")
    lines.append("")
    lines.append(f"- **Total Cases:** {run.total_cases}")
    lines.append(f"- **Average Score:** {_format_percent(run.average_score)}")
    lines.append(f"- **Regressions:** {run.regression_count}")
    lines.append(f"- **Improvements:** {run.improvement_count}")
    lines.append("")

    lines.append("## Summary Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for key, value in sorted(run.summary_metrics.items()):
        lines.append(f"| {_metric_label(key)} | {_format_value(key, value)} |")
    lines.append("")

    if run.regression_count > 0 or run.improvement_count > 0:
        lines.append("## Regression Summary")
        lines.append("")
        if run.regression_count > 0:
            lines.append(f"- **Regressed:** {run.regression_count} metrics")
        if run.improvement_count > 0:
            lines.append(f"- **Improved:** {run.improvement_count} metrics")
        lines.append("")

    failed_cases = [cr for cr in run.case_results if len(cr.failures) > 0]
    if failed_cases:
        lines.append("## Failed Cases")
        lines.append("")
        for case_result in failed_cases:
            lines.append(f"### {case_result.title}")
            lines.append("")
            lines.append(f"- **Case ID:** {case_result.case_id}")
            lines.append(f"- **Failures:** {len(case_result.failures)}")
            lines.append("")

            if case_result.failures:
                lines.append("| Selector | Expected | Actual | Reason |")
                lines.append("|----------|----------|--------|--------|")
                for failure in case_result.failures:
                    lines.append(
                        f"| {failure.get('selector', '')} | "
                        f"{failure.get('expected_profile_key') or '-'} | "
                        f"{failure.get('actual_profile_key') or '-'} | "
                        f"{_failure_reason_label(failure.get('reason'))} |"
                    )
                lines.append("")

    all_failures: list[dict[str, Any]] = []
    for case_result in run.case_results:
        all_failures.extend(case_result.failures)

    if all_failures:
        lines.append("## Top Failure Reasons")
        lines.append("")
        reason_counts = Counter(f["reason"] for f in all_failures)
        for reason, count in reason_counts.most_common():
            lines.append(f"- **{_failure_reason_label(reason)}:** {count}")
        lines.append("")

    return "\n".join(lines)


def _format_duration(duration_ms: int) -> str:
    if duration_ms >= 1000:
        return f"{(duration_ms / 1000):.1f}s"
    return f"{duration_ms}ms"


def _format_percent(value: float) -> str:
    return f"{round(value * 100)}%"


def _format_value(key: str, value: float) -> str:
    if key.endswith("_duration_ms"):
        return _format_duration(int(value))
    if key == "llm_fallback_count":
        return str(int(value))
    if key in {"failure_rate", "llm_cache_hit_rate", "retry_success_rate"}:
        return _format_percent(value)
    return _format_percent(value)


def _metric_label(key: str) -> str:
    label_map = {
        "field_extraction_recall": "Field Extraction Recall",
        "field_extraction_precision": "Field Extraction Precision",
        "mapping_accuracy": "Mapping Accuracy",
        "required_field_coverage": "Required Field Coverage",
        "non_fillable_rejection_rate": "Non-fillable Rejection Rate",
        "login_detection_accuracy": "Login Detection Accuracy",
        "fill_success_rate": "Fill Success Rate",
        "llm_fallback_count": "LLM Fallback Count",
        "average_case_duration_ms": "Average Case Duration",
        "p95_case_duration_ms": "P95 Case Duration",
        "llm_cache_hit_rate": "LLM Cache Hit Rate",
        "retry_success_rate": "Retry Success Rate",
        "failure_rate": "Failure Rate",
    }
    return label_map.get(key, key.replace("_", " ").title())


def _failure_reason_label(reason: str | None) -> str:
    if not reason:
        return "Unknown"
    label_map = {
        "field_not_extracted": "Field Not Extracted",
        "wrong_profile_key": "Wrong Profile Key",
        "action_field_should_skip": "Action Field Should Skip",
        "unexpected_extra_mapping": "Unexpected Extra Mapping",
        "missing_required_value": "Missing Required Value",
        "option_value_mismatch": "Option Value Mismatch",
        "low_confidence_mapping": "Low Confidence Mapping",
    }
    return label_map.get(reason, reason.replace("_", " ").title())


def _parse_mode_detail(value: str) -> dict[str, str]:
    if not value:
        return {}
    if "=" not in value:
        return {}
    parts = [part.strip() for part in value.split(";") if part.strip()]
    parsed: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key or not raw_value:
            continue
        parsed[key] = raw_value
    return parsed
