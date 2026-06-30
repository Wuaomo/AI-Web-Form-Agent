"""Tests for benchmark case loading and metric scoring."""

from app.services.benchmark_runner import load_benchmark_cases, score_case


def test_load_benchmark_cases_reads_all_expected_files() -> None:
    cases = load_benchmark_cases()

    assert len(cases) == 10
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
            "reason": "profile_key_mismatch",
        },
        {
            "selector": "#submit",
            "expected_profile_key": None,
            "actual_profile_key": None,
            "reason": "missing_extraction",
        },
    ]

