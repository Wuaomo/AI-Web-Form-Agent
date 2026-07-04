"""Tests for benchmark metric comparison service."""

import pytest

from app.services.benchmark_comparison_service import compare_summary_metrics


def test_higher_accuracy_metric_is_improved():
    """Verify higher accuracy metric is classified as improved."""

    current = {"mapping_accuracy": 0.95}
    baseline = {"mapping_accuracy": 0.90}

    result = compare_summary_metrics(current, baseline)

    assert "mapping_accuracy" in result
    assert result["mapping_accuracy"]["classification"] == "improved"
    assert result["mapping_accuracy"]["delta"] == pytest.approx(0.05)


def test_lower_accuracy_metric_is_regressed():
    """Verify lower accuracy metric is classified as regressed."""

    current = {"mapping_accuracy": 0.85}
    baseline = {"mapping_accuracy": 0.90}

    result = compare_summary_metrics(current, baseline)

    assert "mapping_accuracy" in result
    assert result["mapping_accuracy"]["classification"] == "regressed"
    assert result["mapping_accuracy"]["delta"] == pytest.approx(-0.05)


def test_difference_below_tolerance_is_unchanged():
    """Verify difference below tolerance is classified as unchanged."""

    current = {"field_extraction_recall": 0.9005}
    baseline = {"field_extraction_recall": 0.9000}

    result = compare_summary_metrics(current, baseline)

    assert "field_extraction_recall" in result
    assert result["field_extraction_recall"]["classification"] == "unchanged"


def test_missing_baseline_metric_is_new():
    """Verify metric present in current but missing from baseline is classified as new."""

    current = {"new_metric": 0.80}
    baseline = {"existing_metric": 0.90}

    result = compare_summary_metrics(current, baseline)

    assert "new_metric" in result
    assert result["new_metric"]["classification"] == "new"
    assert result["new_metric"]["baseline_value"] is None


def test_missing_current_metric_is_missing():
    """Verify metric present in baseline but missing from current is classified as missing."""

    current = {"existing_metric": 0.90}
    baseline = {"existing_metric": 0.90, "missing_metric": 0.85}

    result = compare_summary_metrics(current, baseline)

    assert "missing_metric" in result
    assert result["missing_metric"]["classification"] == "missing"
    assert result["missing_metric"]["current_value"] is None


def test_lower_fallback_count_is_improved():
    """Verify lower fallback count is classified as improved."""

    current = {"llm_fallback_count": 2}
    baseline = {"llm_fallback_count": 5}

    result = compare_summary_metrics(current, baseline)

    assert "llm_fallback_count" in result
    assert result["llm_fallback_count"]["classification"] == "improved"
    assert result["llm_fallback_count"]["delta"] == -3


def test_higher_fallback_count_is_regressed():
    """Verify higher fallback count is classified as regressed."""

    current = {"llm_fallback_count": 5}
    baseline = {"llm_fallback_count": 2}

    result = compare_summary_metrics(current, baseline)

    assert "llm_fallback_count" in result
    assert result["llm_fallback_count"]["classification"] == "regressed"
    assert result["llm_fallback_count"]["delta"] == 3


def test_multiple_metrics_classified_correctly():
    """Verify multiple metrics are classified correctly in a single comparison."""

    current = {
        "field_extraction_recall": 0.92,
        "mapping_accuracy": 0.88,
        "required_field_coverage": 1.0,
        "llm_fallback_count": 1,
        "new_metric": 0.75,
    }
    baseline = {
        "field_extraction_recall": 0.90,
        "mapping_accuracy": 0.92,
        "required_field_coverage": 1.0,
        "llm_fallback_count": 3,
        "old_metric": 0.80,
    }

    result = compare_summary_metrics(current, baseline)

    assert result["field_extraction_recall"]["classification"] == "improved"
    assert result["mapping_accuracy"]["classification"] == "regressed"
    assert result["required_field_coverage"]["classification"] == "unchanged"
    assert result["llm_fallback_count"]["classification"] == "improved"
    assert result["new_metric"]["classification"] == "new"
    assert result["old_metric"]["classification"] == "missing"


def test_custom_tolerance():
    """Verify custom tolerance threshold works correctly."""

    current = {"mapping_accuracy": 0.91}
    baseline = {"mapping_accuracy": 0.90}

    result_strict = compare_summary_metrics(current, baseline, tolerance=0.005)
    result_relaxed = compare_summary_metrics(current, baseline, tolerance=0.02)

    assert result_strict["mapping_accuracy"]["classification"] == "improved"
    assert result_relaxed["mapping_accuracy"]["classification"] == "unchanged"


def test_empty_metrics():
    """Verify comparison handles empty metric dictionaries."""

    result = compare_summary_metrics({}, {})
    assert result == {}

    result_current_only = compare_summary_metrics({"metric": 0.5}, {})
    assert result_current_only["metric"]["classification"] == "new"

    result_baseline_only = compare_summary_metrics({}, {"metric": 0.5})
    assert result_baseline_only["metric"]["classification"] == "missing"