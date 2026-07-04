"""Benchmark metric comparison and regression detection."""

from typing import Literal

Classification = Literal["improved", "regressed", "unchanged", "new", "missing"]


def compare_summary_metrics(
    current: dict[str, float],
    baseline: dict[str, float],
    tolerance: float = 0.001,
) -> dict[str, dict[str, float | str]]:
    """Compare metric dictionaries and classify each metric.

    Args:
        current: Current benchmark run metrics.
        baseline: Baseline benchmark run metrics for comparison.
        tolerance: Minimum delta to consider a metric changed.

    Returns:
        Dictionary mapping metric names to classification results.
    """

    higher_is_better = {
        "field_extraction_recall",
        "field_extraction_precision",
        "mapping_accuracy",
        "required_field_coverage",
        "non_fillable_rejection_rate",
        "login_detection_accuracy",
        "fill_success_rate",
    }
    lower_is_better = {
    "llm_fallback_count",
    "average_case_duration_ms",
    "p95_case_duration_ms",
    "failure_rate",
}

    result: dict[str, dict[str, float | str]] = {}

    all_keys = set(current.keys()) | set(baseline.keys())

    for key in all_keys:
        current_value = current.get(key)
        baseline_value = baseline.get(key)

        if current_value is None:
            result[key] = {
                "classification": "missing",
                "current_value": None,
                "baseline_value": baseline_value,
                "delta": None,
            }
            continue

        if baseline_value is None:
            result[key] = {
                "classification": "new",
                "current_value": current_value,
                "baseline_value": None,
                "delta": None,
            }
            continue

        delta = current_value - baseline_value
        abs_delta = abs(delta)

        if abs_delta <= tolerance:
            classification: Classification = "unchanged"
        elif key in higher_is_better:
            classification = "improved" if delta > 0 else "regressed"
        elif key in lower_is_better:
            classification = "improved" if delta < 0 else "regressed"
        else:
            classification = "improved" if delta > 0 else "regressed"

        result[key] = {
            "classification": classification,
            "current_value": current_value,
            "baseline_value": baseline_value,
            "delta": delta,
        }

    return result